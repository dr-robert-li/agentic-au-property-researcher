"""
Main application orchestrator for Australian Property Research.
Coordinates the entire research pipeline from discovery to report generation.
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from models.inputs import UserInput
from models.run_result import RunResult
from research.suburb_discovery import discover_suburbs, get_discovery_summary
from research.suburb_research import batch_research_suburbs
from research.ranking import rank_suburbs, get_ranking_summary
from reporting.html_renderer import generate_all_reports, copy_static_assets
from research.perplexity_client import (
    PerplexityRateLimitError, PerplexityAuthError, PerplexityAPIError
)
from research.anthropic_client import (
    AnthropicRateLimitError, AnthropicAuthError, AnthropicAPIError
)

# Combined error tuples for handling
API_CREDIT_AUTH_ERRORS = (
    PerplexityRateLimitError, PerplexityAuthError,
    AnthropicRateLimitError, AnthropicAuthError,
)
API_GENERAL_ERRORS = (PerplexityAPIError, AnthropicAPIError)


def run_research_pipeline(user_input: UserInput) -> RunResult:
    """
    Execute the complete research pipeline.

    Args:
        user_input: User input parameters

    Returns:
        Complete RunResult with all reports
    """
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
        # Step 1: Discover suburbs
        print("\n📍 STEP 1: SUBURB DISCOVERY")
        print("-" * 80)
        candidates = discover_suburbs(user_input, max_results=user_input.num_suburbs * 3)

        if not candidates:
            print("✗ No suburbs found matching criteria")
            run_result.status = "failed"
            run_result.error_message = "No qualifying suburbs found"
            return run_result

        print("\n" + get_discovery_summary(candidates))

        # Step 2: Detailed research
        print("\n🔬 STEP 2: DETAILED RESEARCH")
        print("-" * 80)
        metrics_list = batch_research_suburbs(
            candidates,
            user_input.dwelling_type,
            user_input.max_median_price,
            max_suburbs=min(len(candidates), user_input.num_suburbs * 2),  # Research 2x for ranking
            provider=user_input.provider
        )

        if not metrics_list:
            print("✗ Research failed for all suburbs")
            run_result.status = "failed"
            run_result.error_message = "Research failed"
            return run_result

        # Step 3: Ranking
        print("\n📊 STEP 3: RANKING & ANALYSIS")
        print("-" * 80)
        reports = rank_suburbs(
            metrics_list,
            ranking_method="composite_score",
            top_n=user_input.num_suburbs
        )

        run_result.suburbs = reports
        print("\n" + get_ranking_summary(reports))

        # Step 4: Report generation
        print("\n📝 STEP 4: REPORT GENERATION")
        print("-" * 80)
        output_dir = settings.OUTPUT_DIR / user_input.run_id
        run_result.output_dir = output_dir

        # Copy static assets
        copy_static_assets(output_dir)

        # Generate all reports
        generated_files = generate_all_reports(run_result, output_dir)

        # Update status
        run_result.status = "completed"

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
        print(f"\n\n{'='*80}")
        print(str(e))
        print(f"{'='*80}\n")
        run_result.status = "failed"
        run_result.error_message = str(e)
        return run_result

    except API_GENERAL_ERRORS as e:
        # Handle general API errors
        print(f"\n\n{'='*80}")
        print(f"❌ API ERROR")
        print(f"{'='*80}")
        print(str(e))
        print(f"{'='*80}\n")
        run_result.status = "failed"
        run_result.error_message = str(e)
        return run_result

    except Exception as e:
        print(f"\n\n{'='*80}")
        print(f"❌ PIPELINE FAILED")
        print(f"{'='*80}")
        print(f"Error: {e}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        print(f"{'='*80}\n")
        run_result.status = "failed"
        run_result.error_message = str(e)
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

    args = parser.parse_args()

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

    # Exit with appropriate code
    if run_result.status == "completed":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
