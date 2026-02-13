"""
Run comparison logic.

Compares 2-3 past research runs side-by-side, finding overlapping suburbs
and computing metric deltas.
"""
import logging
from pathlib import Path
from typing import Optional

from models.comparison import (
    RunSummary, SuburbDelta, SuburbRunMetrics, ComparisonResult
)
from models.run_result import RunResult
from reporting.exports import reconstruct_run_result

logger = logging.getLogger(__name__)


class ComparisonError(Exception):
    """Raised when comparison fails."""
    pass


def compute_run_summary(run_result: RunResult) -> RunSummary:
    """
    Create a RunSummary from a RunResult.

    Args:
        run_result: Complete run result

    Returns:
        RunSummary with key metadata
    """
    return RunSummary(
        run_id=run_result.run_id,
        timestamp=run_result.timestamp.isoformat(),
        dwelling_type=run_result.user_input.dwelling_type,
        max_price=run_result.user_input.max_median_price,
        regions=run_result.user_input.regions,
        suburb_count=len(run_result.suburbs),
        provider=run_result.user_input.provider,
    )


def _suburb_key(name: str, state: str) -> str:
    """Create a normalized key for suburb matching."""
    return f"{name.strip().lower()}|{state.strip().lower()}"


def find_overlapping_suburbs(
    runs: list[RunResult],
) -> tuple[list[SuburbDelta], dict[str, list[str]]]:
    """
    Find suburbs that appear in multiple runs and compute deltas.

    Args:
        runs: List of RunResult objects to compare

    Returns:
        Tuple of (overlapping suburbs with metrics, unique suburbs per run)
    """
    # Build suburb -> run metrics mapping
    suburb_runs: dict[str, dict[str, SuburbRunMetrics]] = {}
    suburb_display: dict[str, tuple[str, str]] = {}  # key -> (name, state)

    for run in runs:
        for report in run.suburbs:
            m = report.metrics
            key = _suburb_key(m.identification.name, m.identification.state)
            suburb_display[key] = (m.identification.name, m.identification.state)

            if key not in suburb_runs:
                suburb_runs[key] = {}

            suburb_runs[key][run.run_id] = SuburbRunMetrics(
                run_id=run.run_id,
                median_price=m.market_current.median_price,
                growth_score=m.growth_projections.growth_score,
                composite_score=m.growth_projections.composite_score,
                risk_score=m.growth_projections.risk_score,
                projected_5yr=m.growth_projections.projected_growth_pct.get(5, 0.0),
                rank=report.rank,
            )

    # Split into overlapping and unique
    overlapping = []
    unique_per_run: dict[str, list[str]] = {run.run_id: [] for run in runs}

    for key, run_metrics in suburb_runs.items():
        name, state = suburb_display[key]
        if len(run_metrics) >= 2:
            # Appears in multiple runs
            delta = SuburbDelta(
                suburb_name=name,
                state=state,
                run_metrics=[
                    run_metrics[run.run_id]
                    for run in runs
                    if run.run_id in run_metrics
                ],
            )
            overlapping.append(delta)
        else:
            # Unique to one run
            run_id = list(run_metrics.keys())[0]
            unique_per_run[run_id].append(f"{name}, {state}")

    # Sort overlapping by first run's composite score (descending)
    overlapping.sort(
        key=lambda d: d.run_metrics[0].composite_score if d.run_metrics else 0,
        reverse=True,
    )

    return overlapping, unique_per_run


def compare_runs(
    run_ids: list[str],
    output_base: Path,
) -> ComparisonResult:
    """
    Compare 2-3 past research runs.

    Args:
        run_ids: List of 2-3 run IDs to compare
        output_base: Base output directory containing run folders

    Returns:
        ComparisonResult with overlapping suburbs and deltas

    Raises:
        ComparisonError: If runs can't be loaded or invalid count
    """
    if len(run_ids) < 2 or len(run_ids) > 3:
        raise ComparisonError("Comparison requires 2 or 3 run IDs")

    # Load runs
    runs: list[RunResult] = []
    for run_id in run_ids:
        run_dir = output_base / run_id
        if not run_dir.exists():
            raise ComparisonError(f"Run directory not found: {run_id}")

        run_result = reconstruct_run_result(run_id, run_dir)
        if run_result is None:
            raise ComparisonError(
                f"Cannot load run {run_id}: run_metadata.json not found or invalid"
            )
        runs.append(run_result)

    # Compute summaries
    summaries = [compute_run_summary(r) for r in runs]

    # Find overlapping suburbs
    overlapping, unique_per_run = find_overlapping_suburbs(runs)

    return ComparisonResult(
        run_summaries=summaries,
        overlapping_suburbs=overlapping,
        unique_per_run=unique_per_run,
    )
