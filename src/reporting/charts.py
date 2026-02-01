"""
Chart generation for suburb reports using matplotlib.
"""
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Optional

from models.suburb_metrics import SuburbMetrics, TimePoint
from models.run_result import SuburbReport

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)
plt.rcParams['font.size'] = 10


def generate_price_history_chart(
    metrics: SuburbMetrics,
    output_path: Path
) -> bool:
    """
    Generate price history line chart.

    Args:
        metrics: SuburbMetrics with price_history data
        output_path: Path to save the chart PNG

    Returns:
        True if chart was generated, False if no data
    """
    price_history = metrics.market_history.price_history

    if not price_history or len(price_history) < 2:
        return False

    # Extract data
    years = [tp.year for tp in price_history]
    prices = [tp.value for tp in price_history]

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot line
    ax.plot(years, prices, marker='o', linewidth=2, markersize=8, color='#2E86AB')

    # Formatting
    ax.set_xlabel('Year', fontsize=12, fontweight='bold')
    ax.set_ylabel('Median Price (AUD)', fontsize=12, fontweight='bold')
    ax.set_title(
        f'Price History - {metrics.get_display_name()}',
        fontsize=14,
        fontweight='bold',
        pad=20
    )

    # Format y-axis as currency
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Grid
    ax.grid(True, alpha=0.3)

    # Tight layout
    plt.tight_layout()

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    return True


def generate_dom_history_chart(
    metrics: SuburbMetrics,
    output_path: Path
) -> bool:
    """
    Generate days on market history chart.

    Args:
        metrics: SuburbMetrics with dom_history data
        output_path: Path to save the chart PNG

    Returns:
        True if chart was generated, False if no data
    """
    dom_history = metrics.market_history.dom_history

    if not dom_history or len(dom_history) < 2:
        return False

    years = [tp.year for tp in dom_history]
    days = [tp.value for tp in dom_history]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(years, days, marker='s', linewidth=2, markersize=8, color='#A23B72')

    ax.set_xlabel('Year', fontsize=12, fontweight='bold')
    ax.set_ylabel('Days on Market', fontsize=12, fontweight='bold')
    ax.set_title(
        f'Days on Market Trend - {metrics.get_display_name()}',
        fontsize=14,
        fontweight='bold',
        pad=20
    )

    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    return True


def generate_growth_projection_chart(
    metrics: SuburbMetrics,
    output_path: Path
) -> bool:
    """
    Generate growth projection chart with confidence intervals.

    Args:
        metrics: SuburbMetrics with growth projections
        output_path: Path to save the chart PNG

    Returns:
        True if chart was generated
    """
    growth_data = metrics.growth_projections.projected_growth_pct

    if not growth_data:
        return False

    # Sort by year
    years = sorted(growth_data.keys())
    growth_pct = [growth_data[y] for y in years]

    # Get confidence intervals if available
    ci_data = metrics.growth_projections.confidence_intervals
    ci_low = [ci_data.get(y, (0, 0))[0] for y in years] if ci_data else None
    ci_high = [ci_data.get(y, (0, 0))[1] for y in years] if ci_data else None

    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot main line
    ax.plot(years, growth_pct, marker='o', linewidth=3, markersize=10,
            color='#18A558', label='Projected Growth', zorder=3)

    # Plot confidence interval
    if ci_low and ci_high and any(ci_low) and any(ci_high):
        ax.fill_between(years, ci_low, ci_high, alpha=0.2, color='#18A558',
                        label='Confidence Interval')

    ax.set_xlabel('Years from Now', fontsize=12, fontweight='bold')
    ax.set_ylabel('Projected Growth (%)', fontsize=12, fontweight='bold')
    ax.set_title(
        f'Growth Projections - {metrics.get_display_name()}',
        fontsize=14,
        fontweight='bold',
        pad=20
    )

    # Format y-axis as percentage
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1f}%'))

    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left', fontsize=10)

    # Add data labels
    for x, y in zip(years, growth_pct):
        ax.annotate(f'{y:.1f}%', (x, y), textcoords="offset points",
                   xytext=(0, 10), ha='center', fontsize=9, fontweight='bold')

    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    return True


def generate_comparison_chart(
    reports: list[SuburbReport],
    output_path: Path,
    metric: str = '5yr_growth'
) -> bool:
    """
    Generate comparison bar chart across suburbs.

    Args:
        reports: List of SuburbReport objects
        output_path: Path to save the chart PNG
        metric: Metric to compare ('5yr_growth', 'growth_score', 'composite_score')

    Returns:
        True if chart was generated
    """
    if not reports:
        return False

    # Extract data based on metric
    suburb_names = []
    values = []

    for report in reports[:15]:  # Limit to top 15 for readability
        suburb_names.append(report.metrics.identification.name)

        if metric == '5yr_growth':
            values.append(report.metrics.growth_projections.projected_growth_pct.get(5, 0))
        elif metric == 'growth_score':
            values.append(report.metrics.growth_projections.growth_score)
        elif metric == 'composite_score':
            values.append(report.metrics.growth_projections.composite_score)
        else:
            values.append(0)

    # Create horizontal bar chart
    fig, ax = plt.subplots(figsize=(10, max(6, len(suburb_names) * 0.4)))

    # Create bars with gradient color
    colors = plt.cm.viridis_r([(v - min(values)) / (max(values) - min(values) + 0.001)
                                for v in values])
    bars = ax.barh(suburb_names, values, color=colors, edgecolor='black', linewidth=0.5)

    # Labels
    if metric == '5yr_growth':
        xlabel = '5-Year Projected Growth (%)'
        title = 'Top Suburbs by 5-Year Growth Projection'
        fmt = lambda x: f'{x:.1f}%'
    elif metric == 'growth_score':
        xlabel = 'Growth Score (0-100)'
        title = 'Top Suburbs by Growth Score'
        fmt = lambda x: f'{x:.1f}'
    else:  # composite_score
        xlabel = 'Composite Score (0-100)'
        title = 'Top Suburbs by Composite Score (Growth + Risk)'
        fmt = lambda x: f'{x:.1f}'

    ax.set_xlabel(xlabel, fontsize=12, fontweight='bold')
    ax.set_ylabel('Suburb', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

    # Add value labels
    for i, (bar, value) in enumerate(zip(bars, values)):
        ax.text(value + max(values) * 0.01, i, fmt(value),
                va='center', fontsize=9, fontweight='bold')

    ax.grid(True, axis='x', alpha=0.3)

    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    return True


def generate_all_suburb_charts(
    report: SuburbReport,
    charts_dir: Path
) -> dict[str, str]:
    """
    Generate all charts for a suburb report.

    Args:
        report: SuburbReport object
        charts_dir: Directory to save charts

    Returns:
        Dictionary mapping chart names to filenames
    """
    metrics = report.metrics
    slug = metrics.get_slug()
    generated_charts = {}

    # Price history chart
    price_chart_path = charts_dir / f"price_history_{slug}.png"
    if generate_price_history_chart(metrics, price_chart_path):
        generated_charts['price_history'] = price_chart_path.name

    # DOM history chart
    dom_chart_path = charts_dir / f"dom_history_{slug}.png"
    if generate_dom_history_chart(metrics, dom_chart_path):
        generated_charts['dom_history'] = dom_chart_path.name

    # Growth projection chart
    growth_chart_path = charts_dir / f"growth_projection_{slug}.png"
    if generate_growth_projection_chart(metrics, growth_chart_path):
        generated_charts['growth_projection'] = growth_chart_path.name

    return generated_charts


def generate_overview_charts(
    reports: list[SuburbReport],
    charts_dir: Path
) -> dict[str, str]:
    """
    Generate overview charts comparing all suburbs.

    Args:
        reports: List of all SuburbReport objects
        charts_dir: Directory to save charts

    Returns:
        Dictionary mapping chart names to filenames
    """
    generated_charts = {}

    # 5-year growth comparison
    growth_chart_path = charts_dir / "overview_5yr_growth.png"
    if generate_comparison_chart(reports, growth_chart_path, metric='5yr_growth'):
        generated_charts['5yr_growth_comparison'] = growth_chart_path.name

    # Growth score comparison
    score_chart_path = charts_dir / "overview_growth_score.png"
    if generate_comparison_chart(reports, score_chart_path, metric='growth_score'):
        generated_charts['growth_score_comparison'] = score_chart_path.name

    # Composite score comparison
    composite_chart_path = charts_dir / "overview_composite_score.png"
    if generate_comparison_chart(reports, composite_chart_path, metric='composite_score'):
        generated_charts['composite_score_comparison'] = composite_chart_path.name

    return generated_charts
