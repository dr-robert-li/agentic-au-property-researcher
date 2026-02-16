"""
Main application orchestrator for Australian Property Research.
Coordinates the entire research pipeline from discovery to report generation.
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from models.inputs import UserInput
from models.run_result import RunResult
from research.suburb_discovery import discover_suburbs, parallel_discover_suburbs, get_discovery_summary
from research.suburb_research import batch_research_suburbs, parallel_research_suburbs
from research.ranking import rank_suburbs, get_ranking_summary
from reporting.html_renderer import generate_all_reports, copy_static_assets
from security.exceptions import ACCOUNT_ERRORS, TRANSIENT_ERRORS
# Backward compatibility: keep provider-specific imports for isinstance checks
from research.perplexity_client import (
    PerplexityRateLimitError, PerplexityAuthError, PerplexityAPIError
)
from research.anthropic_client import (
    AnthropicRateLimitError, AnthropicAuthError, AnthropicAPIError
)

# Use the new exception hierarchy tuples (inherits old types)
API_CREDIT_AUTH_ERRORS = ACCOUNT_ERRORS
API_GENERAL_ERRORS = TRANSIENT_ERRORS


def run_research_pipeline(
    user_input: UserInput,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    resume_from: Optional[str] = None
) -> RunResult:
    """
    Execute the complete research pipeline.

    Args:
        user_input: User input parameters
        progress_callback: Optional callback for progress updates (used by web UI)

    Returns:
        Complete RunResult with all reports
    """
    def _progress(message: str, percent: float = 0.0):
        """Report progress to both stdout and callback."""
        print(message)
        if progress_callback:
            progress_callback(message, percent)

    print("\n" + "="*80)
    print("🏘️  AUSTRALIAN PROPERTY RESEARCH PIPELINE")
    print("="*80)
    print(f"\nRun ID: {user_input.run_id}")
    print(f"Provider: {user_input.get_provider_display()}")
    print(f"Regions: {', '.join(user_input.regions)}")
    print(f"Dwelling Type: {user_input.dwelling_type}")
    print(f"Max Price: ${user_input.max_median_price:,.0f}")
    print(f"Target Suburbs: {user_input.num_suburbs}")
    print("\n" + "="*80)

    # Create run result
    run_result = RunResult(
        run_id=user_input.run_id,
        user_input=user_input,
        status="running"
    )

    try:
        # Initialize checkpoint manager
        from research.checkpoints import CheckpointManager
        from models.suburb_metrics import SuburbMetrics

        checkpoint_mgr = CheckpointManager(user_input.run_id, settings.CHECKPOINT_DIR)
        candidates = None
        completed_suburbs = set()
        metrics_list = []

        # Resume from checkpoint if requested
        if resume_from:
            _progress(f"Attempting to resume run: {resume_from}")

            # Try loading discovery checkpoint
            discovery_state = checkpoint_mgr.load_latest_checkpoint("discovery")
            if discovery_state:
                from research.suburb_discovery import SuburbCandidate
                candidates = [SuburbCandidate(d) for d in discovery_state["candidates"]]
                _progress(f"Resumed discovery: {len(candidates)} candidates from checkpoint")

            # Try loading research checkpoint
            research_state = checkpoint_mgr.load_latest_checkpoint("research")
            if research_state:
                completed_suburbs = set(research_state.get("completed_suburbs", []))
                # SuburbMetrics is Pydantic v2: use model_validate() to reconstruct from dict
                metrics_list = [SuburbMetrics.model_validate(d) for d in research_state.get("metrics_list", [])]
                _progress(f"Resumed research: {len(completed_suburbs)} suburbs already completed")

        # Step 1: Discover suburbs
        if candidates is None:
            print("\n📍 STEP 1: SUBURB DISCOVERY")
            print("-" * 80)
            _progress(f"Discovering suburbs matching criteria (targeting {user_input.num_suburbs} suburbs)...", 0)
            candidates = parallel_discover_suburbs(
                user_input,
                max_results=int(user_input.num_suburbs * settings.DISCOVERY_MULTIPLIER),
                progress_callback=progress_callback,
            )

            if not candidates:
                _progress("No suburbs found matching criteria", 0)
                run_result.status = "failed"
                run_result.error_message = "No qualifying suburbs found"
                return run_result

            _progress(f"Found {len(candidates)} qualifying suburb candidates (need {user_input.num_suburbs})", 20)
            print("\n" + get_discovery_summary(candidates))

            # Save discovery checkpoint
            checkpoint_mgr.save_checkpoint("discovery", {
                "candidates": [c.to_dict() for c in candidates]
            })
            _progress("Discovery checkpoint saved", 20)
        else:
            print("\n📍 STEP 1: SUBURB DISCOVERY (RESUMED)")
            print("-" * 80)
            _progress(f"Skipping discovery (loaded {len(candidates)} candidates from checkpoint)", 20)

        # Step 2: Detailed research
        print("\n🔬 STEP 2: DETAILED RESEARCH")
        print("-" * 80)
        research_count = min(len(candidates), int(user_input.num_suburbs * settings.RESEARCH_MULTIPLIER))

        # Filter out completed suburbs if resuming
        if completed_suburbs:
            original_count = len(candidates)
            candidates = [c for c in candidates if f"{c.name}_{c.state}" not in completed_suburbs]
            _progress(f"Skipping {original_count - len(candidates)} already-completed suburbs")

        if len(candidates) == 0:
            _progress(f"All suburbs already researched (loaded {len(metrics_list)} from checkpoint)", 80)
        else:
            _progress(f"Starting detailed research on {research_count} suburbs (to select top {user_input.num_suburbs})...", 20)

            # Process in batches of 5 with checkpoints after each batch
            research_candidates = candidates[:research_count]
            batch_size = 5
            total_batches = (len(research_candidates) + batch_size - 1) // batch_size

            for batch_start in range(0, len(research_candidates), batch_size):
                batch = research_candidates[batch_start:batch_start + batch_size]
                batch_num = batch_start // batch_size + 1
                # Calculate percent: research phase is 20-80%, so 60% range
                percent = 20 + (60 * batch_num / total_batches)
                _progress(f"Researching batch {batch_num}: suburbs {batch_start + 1}-{batch_start + len(batch)} of {len(research_candidates)}", percent)

                batch_metrics = parallel_research_suburbs(
                    batch,
                    user_input.dwelling_type,
                    user_input.max_median_price,
                    max_suburbs=len(batch),
                    provider=user_input.provider,
                    progress_callback=progress_callback
                )

                for m in batch_metrics:
                    completed_suburbs.add(f"{m.identification.name}_{m.identification.state}")
                    metrics_list.append(m)

                # Checkpoint after each batch
                # SuburbMetrics is Pydantic v2: use .model_dump() for serialization
                checkpoint_mgr.save_checkpoint("research", {
                    "completed_suburbs": list(completed_suburbs),
                    "metrics_list": [m.model_dump() for m in metrics_list]
                }, sequence=len(completed_suburbs))
                _progress(f"Checkpoint saved: {len(completed_suburbs)} suburbs completed", percent)

        if not metrics_list:
            _progress("Research failed for all suburbs", 0)
            run_result.status = "failed"
            run_result.error_message = "Research failed"
            return run_result

        _progress(f"Research complete: {len(metrics_list)} suburbs analyzed", 80)

        # Step 3: Ranking
        print("\n📊 STEP 3: RANKING & ANALYSIS")
        print("-" * 80)
        _progress(f"Ranking {len(metrics_list)} suburbs by composite score...", 80)
        reports = rank_suburbs(
            metrics_list,
            ranking_method="composite_score",
            top_n=user_input.num_suburbs
        )

        run_result.suburbs = reports
        _progress(f"Selected top {len(reports)} suburbs for reports", 85)
        if len(reports) < user_input.num_suburbs:
            _progress(f"Note: Only {len(reports)} suburbs available (requested {user_input.num_suburbs})", 85)
        print("\n" + get_ranking_summary(reports))

        # Step 4: Report generation
        print("\n📝 STEP 4: REPORT GENERATION")
        print("-" * 80)
        _progress(f"Generating reports for {len(reports)} suburbs...", 90)
        output_dir = settings.OUTPUT_DIR / user_input.run_id
        run_result.output_dir = output_dir

        # Copy static assets
        copy_static_assets(output_dir)

        # Generate all reports
        generated_files = generate_all_reports(run_result, output_dir)

        # Update status
        run_result.status = "completed"
        _progress("Reports generated successfully", 100)

        print("\n" + "="*80)
        print("✅ RESEARCH PIPELINE COMPLETE!")
        print("="*80)
        print(f"\n📁 Reports saved to: {output_dir}")
        print(f"🌐 Open in browser: file://{output_dir.absolute()}/index.html")
        print("\n" + "="*80)

        return run_result

    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrupted by user")
        run_result.status = "cancelled"
        return run_result

    except API_CREDIT_AUTH_ERRORS as e:
        # Handle API credit/auth errors with specific messaging
        from security.sanitization import sanitize_text
        sanitized_message = sanitize_text(str(e))
        print(f"\n\n{'='*80}")
        print(sanitized_message)
        print(f"{'='*80}\n")
        run_result.status = "failed"
        run_result.error_message = sanitized_message
        return run_result

    except API_GENERAL_ERRORS as e:
        # Handle general API errors
        from security.sanitization import sanitize_text
        sanitized_message = sanitize_text(str(e))
        print(f"\n\n{'='*80}")
        print(f"❌ API ERROR")
        print(f"{'='*80}")
        print(sanitized_message)
        print(f"{'='*80}\n")
        run_result.status = "failed"
        run_result.error_message = sanitized_message
        return run_result

    except Exception as e:
        from security.sanitization import sanitize_text
        sanitized_message = sanitize_text(str(e))
        print(f"\n\n{'='*80}")
        print(f"❌ PIPELINE FAILED")
        print(f"{'='*80}")
        print(f"Error: {sanitized_message}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        print(f"{'='*80}\n")
        run_result.status = "failed"
        run_result.error_message = sanitized_message
        return run_result


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Australian Property Research - AI-Powered Suburb Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (uses default provider)
  python -m src.app --max-price 700000 --dwelling-type house

  # Use Anthropic Claude as provider
  python -m src.app --max-price 700000 --dwelling-type house --provider anthropic

  # Use Perplexity with specific region
  python -m src.app --regions "South East Queensland" --max-price 800000 --dwelling-type apartment --provider perplexity

  # Multiple regions
  python -m src.app --regions "South East Queensland" "Northern NSW" --max-price 650000 --dwelling-type house --num-suburbs 10
        """
    )

    parser.add_argument(
        "--max-price",
        type=float,
        required=True,
        help="Maximum median price threshold (AUD)"
    )

    parser.add_argument(
        "--dwelling-type",
        type=str,
        choices=["house", "apartment", "townhouse"],
        required=True,
        help="Type of dwelling to search for"
    )

    parser.add_argument(
        "--regions",
        nargs="+",
        default=["South East Queensland"],
        help='Region(s) to search. Default: "South East Queensland"'
    )

    parser.add_argument(
        "--num-suburbs",
        type=int,
        default=5,
        help="Number of top suburbs to include in report (default: 5)"
    )

    parser.add_argument(
        "--provider",
        type=str,
        choices=settings.AVAILABLE_PROVIDERS,
        default=settings.DEFAULT_PROVIDER,
        help=f"AI research provider (available: {', '.join(settings.AVAILABLE_PROVIDERS)}; default: {settings.DEFAULT_PROVIDER})"
    )

    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Custom run ID (default: auto-generated timestamp)"
    )

    parser.add_argument(
        "--export-pdf",
        action="store_true",
        help="Automatically generate PDF report after completion"
    )

    parser.add_argument(
        "--export-xlsx",
        action="store_true",
        help="Automatically generate Excel report after completion"
    )

    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear all cached research data and exit"
    )

    parser.add_argument(
        "--compare",
        nargs="+",
        metavar="RUN_ID",
        help="Compare 2-3 past runs side-by-side (provide run IDs)"
    )

    parser.add_argument(
        "--resume",
        type=str,
        metavar="RUN_ID",
        default=None,
        help="Resume an interrupted run from its last checkpoint (provide the run_id)"
    )

    args = parser.parse_args()

    # Handle --clear-cache
    if args.clear_cache:
        from research.cache import get_cache
        cache = get_cache()
        stats = cache.stats()
        print(f"Cache stats: {stats['discovery_count']} discovery, {stats['research_count']} research entries")
        print(f"Total size: {stats['total_size_bytes']:,} bytes")
        count = cache.clear()
        print(f"Cleared {count} cache entries.")
        sys.exit(0)

    # Handle --compare
    if args.compare:
        run_ids = args.compare
        if len(run_ids) < 2 or len(run_ids) > 3:
            print("Error: --compare requires 2 or 3 run IDs")
            sys.exit(1)
        from research.comparison import compare_runs
        from reporting.comparison_renderer import generate_comparison_report
        try:
            comparison = compare_runs(run_ids, settings.OUTPUT_DIR)
            output_dir = settings.OUTPUT_DIR / f"compare_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
            report_path = generate_comparison_report(comparison, output_dir)
            print(f"\n✅ Comparison report generated: {report_path}")
            print(f"🌐 Open in browser: file://{report_path.absolute()}")
        except Exception as e:
            print(f"❌ Comparison failed: {e}")
            sys.exit(1)
        sys.exit(0)

    # Handle --resume
    if args.resume:
        user_input = UserInput(
            max_median_price=args.max_price,
            dwelling_type=args.dwelling_type,
            regions=args.regions,
            num_suburbs=args.num_suburbs,
            provider=args.provider,
            run_id=args.resume,  # Use the provided run_id
            interface_mode="cli"
        )
        run_result = run_research_pipeline(user_input, resume_from=args.resume)
        if run_result.status == "completed":
            sys.exit(0)
        else:
            sys.exit(1)

    # Validate num_suburbs
    if args.num_suburbs > 25:
        print("\n⚠️  WARNING: You requested more than 25 suburbs.")
        print("This will take significantly longer and use more API credits.")
        response = input("Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return

    # Create user input
    user_input = UserInput(
        max_median_price=args.max_price,
        dwelling_type=args.dwelling_type,
        regions=args.regions,
        num_suburbs=args.num_suburbs,
        provider=args.provider,
        run_id=args.run_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        interface_mode="cli"
    )

    # Run pipeline
    run_result = run_research_pipeline(user_input)

    # Generate exports if requested
    if run_result.status == "completed":
        if args.export_pdf:
            try:
                from reporting.exports import generate_pdf_export
                pdf_path = generate_pdf_export(run_result, run_result.output_dir)
                print(f"📄 PDF exported: {pdf_path}")
            except Exception as e:
                print(f"❌ PDF export failed: {e}")

        if args.export_xlsx:
            try:
                from reporting.exports import generate_excel_export
                xlsx_path = generate_excel_export(run_result, run_result.output_dir)
                print(f"📊 Excel exported: {xlsx_path}")
            except Exception as e:
                print(f"❌ Excel export failed: {e}")

    # Exit with appropriate code
    if run_result.status == "completed":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
