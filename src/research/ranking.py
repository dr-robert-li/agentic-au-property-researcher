"""
Suburb ranking and analysis logic.
"""
from typing import Optional, Literal
from models.suburb_metrics import SuburbMetrics
from models.run_result import SuburbReport

try:
    from config import settings
except ImportError:
    settings = None

# Default quality weights if settings not available
_DEFAULT_QUALITY_WEIGHTS = {
    "high": 1.0,
    "medium": 0.95,
    "low": 0.85,
    "fallback": 0.70
}


def calculate_quality_adjusted_score(metrics: SuburbMetrics) -> float:
    """
    Apply quality penalty to composite score.

    Args:
        metrics: SuburbMetrics object with data_quality field

    Returns:
        Quality-adjusted composite score
    """
    base_score = metrics.growth_projections.composite_score

    # Get quality weights from settings or use defaults
    if settings and hasattr(settings, 'RANKING_QUALITY_WEIGHTS'):
        weights = settings.RANKING_QUALITY_WEIGHTS
    else:
        weights = _DEFAULT_QUALITY_WEIGHTS

    # Apply quality weight
    weight = weights.get(metrics.data_quality, 0.95)
    return base_score * weight


def rank_suburbs(
    metrics_list: list[SuburbMetrics],
    ranking_method: Literal["growth_score", "composite_score", "5yr_growth", "quality_adjusted"] = "quality_adjusted",
    top_n: Optional[int] = None
) -> list[SuburbReport]:
    """
    Rank suburbs and create SuburbReport objects with rankings.

    Args:
        metrics_list: List of SuburbMetrics to rank
        ranking_method: Method to use for ranking
            - "growth_score": Rank by raw growth potential
            - "composite_score": Rank by growth adjusted for risk
            - "5yr_growth": Rank by 5-year projected growth percentage
            - "quality_adjusted": Rank by quality-adjusted composite score (default)
        top_n: Return only top N suburbs (None = all)

    Returns:
        List of SuburbReport objects ranked and numbered
    """
    if not metrics_list:
        return []

    # Create SuburbReport objects
    reports = [SuburbReport(metrics=m) for m in metrics_list]

    # Sort based on ranking method
    if ranking_method == "growth_score":
        reports.sort(key=lambda r: r.metrics.growth_projections.growth_score, reverse=True)
    elif ranking_method == "5yr_growth":
        reports.sort(key=lambda r: r.metrics.growth_projections.projected_growth_pct.get(5, 0), reverse=True)
    elif ranking_method == "composite_score":
        reports.sort(key=lambda r: r.metrics.growth_projections.composite_score, reverse=True)
    else:  # quality_adjusted (default)
        reports.sort(key=lambda r: calculate_quality_adjusted_score(r.metrics), reverse=True)

    # Assign rankings
    for i, report in enumerate(reports, 1):
        report.rank = i

    # Limit to top N if specified
    if top_n:
        reports = reports[:top_n]

    return reports


def get_ranking_summary(reports: list[SuburbReport]) -> str:
    """
    Get a text summary of ranked suburbs.

    Args:
        reports: List of ranked SuburbReport objects

    Returns:
        Formatted summary string
    """
    if not reports:
        return "No suburbs ranked"

    lines = [
        "SUBURB RANKINGS",
        "=" * 80,
        ""
    ]

    # Header
    lines.append(f"{'Rank':<6} {'Suburb':<30} {'Price':<12} {'Growth':<10} {'Risk':<10} {'Score':<10}")
    lines.append("-" * 80)

    # Data rows
    for report in reports:
        m = report.metrics
        lines.append(
            f"{report.rank:<6} "
            f"{m.get_display_name():<30} "
            f"${m.market_current.median_price:>10,.0f} "
            f"{m.growth_projections.growth_score:>9.1f} "
            f"{m.growth_projections.risk_score:>9.1f} "
            f"{m.growth_projections.composite_score:>9.1f}"
        )

    lines.append("")
    lines.append(f"Total suburbs ranked: {len(reports)}")

    return "\n".join(lines)


def calculate_comparison_stats(reports: list[SuburbReport]) -> dict:
    """
    Calculate comparative statistics across ranked suburbs.

    Args:
        reports: List of SuburbReport objects

    Returns:
        Dictionary of statistics
    """
    if not reports:
        return {}

    prices = [r.metrics.market_current.median_price for r in reports]
    growth_scores = [r.metrics.growth_projections.growth_score for r in reports]
    composite_scores = [r.metrics.growth_projections.composite_score for r in reports]
    five_yr_growth = [r.metrics.growth_projections.projected_growth_pct.get(5, 0) for r in reports]

    stats = {
        "total_suburbs": len(reports),
        "price_range": {
            "min": min(prices),
            "max": max(prices),
            "avg": sum(prices) / len(prices),
            "median": sorted(prices)[len(prices) // 2]
        },
        "growth_score_range": {
            "min": min(growth_scores),
            "max": max(growth_scores),
            "avg": sum(growth_scores) / len(growth_scores)
        },
        "composite_score_range": {
            "min": min(composite_scores),
            "max": max(composite_scores),
            "avg": sum(composite_scores) / len(composite_scores)
        },
        "five_year_growth_range": {
            "min": min(five_yr_growth),
            "max": max(five_yr_growth),
            "avg": sum(five_yr_growth) / len(five_yr_growth)
        },
        "top_suburb": reports[0].metrics.get_display_name() if reports else None,
        "price_leaders": sorted(reports, key=lambda r: r.metrics.market_current.median_price)[:3],
        "growth_leaders": sorted(reports, key=lambda r: r.metrics.growth_projections.growth_score, reverse=True)[:3]
    }

    return stats


def filter_by_criteria(
    metrics_list: list[SuburbMetrics],
    min_growth_score: Optional[float] = None,
    max_risk_score: Optional[float] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    states: Optional[list[str]] = None
) -> list[SuburbMetrics]:
    """
    Filter suburbs by various criteria.

    Args:
        metrics_list: List of SuburbMetrics to filter
        min_growth_score: Minimum growth score (0-100)
        max_risk_score: Maximum acceptable risk score (0-100)
        min_price: Minimum median price
        max_price: Maximum median price
        states: List of acceptable state codes

    Returns:
        Filtered list of SuburbMetrics
    """
    filtered = metrics_list.copy()

    if min_growth_score is not None:
        filtered = [m for m in filtered if m.growth_projections.growth_score >= min_growth_score]

    if max_risk_score is not None:
        filtered = [m for m in filtered if m.growth_projections.risk_score <= max_risk_score]

    if min_price is not None:
        filtered = [m for m in filtered if m.market_current.median_price >= min_price]

    if max_price is not None:
        filtered = [m for m in filtered if m.market_current.median_price <= max_price]

    if states:
        filtered = [m for m in filtered if m.identification.state in states]

    return filtered
