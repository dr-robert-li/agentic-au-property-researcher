"""
HTML report rendering using Jinja2 templates.
"""
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

from models.inputs import UserInput
from models.run_result import RunResult, SuburbReport
from research.ranking import calculate_comparison_stats
from reporting.charts import generate_all_suburb_charts, generate_overview_charts


def get_template_env() -> Environment:
    """Get Jinja2 environment with templates loaded."""
    template_dir = Path(__file__).parent.parent / "ui" / "web" / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(['html', 'xml'])
    )
    return env


def render_overview_report(
    run_result: RunResult,
    output_dir: Path
) -> Path:
    """
    Render the overview/index HTML report.

    Args:
        run_result: RunResult with all suburb reports
        output_dir: Directory to save the HTML file

    Returns:
        Path to generated index.html
    """
    env = get_template_env()
    template = env.get_template('index.html')

    # Calculate statistics
    stats = calculate_comparison_stats(run_result.suburbs)

    # Prepare template data
    context = {
        'run_id': run_result.run_id,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'regions': run_result.user_input.regions,
        'dwelling_type': run_result.user_input.dwelling_type,
        'max_price': run_result.user_input.max_median_price,
        'total_suburbs': len(run_result.suburbs),
        'top_n': run_result.user_input.num_suburbs,
        'reports': run_result.get_top_suburbs(),
        'stats': stats,
        'overview_charts': {}
    }

    # Generate overview charts
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    print("Generating overview charts...")
    overview_charts = generate_overview_charts(run_result.suburbs, charts_dir)
    context['overview_charts'] = overview_charts

    # Render HTML
    html = template.render(**context)

    # Save file
    output_path = output_dir / "index.html"
    output_path.write_text(html, encoding='utf-8')

    print(f"✓ Overview report saved: {output_path}")
    return output_path


def render_suburb_report(
    report: SuburbReport,
    output_dir: Path
) -> Path:
    """
    Render a single suburb HTML report.

    Args:
        report: SuburbReport to render
        output_dir: Directory to save the HTML file

    Returns:
        Path to generated HTML file
    """
    env = get_template_env()
    template = env.get_template('suburb_report.html')

    # Generate charts for this suburb
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating charts for {report.metrics.get_display_name()}...")
    charts = generate_all_suburb_charts(report, charts_dir)
    report.charts = charts

    # Prepare template data
    context = {
        'suburb': report.metrics,
        'rank': report.rank,
        'charts': charts,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # Render HTML
    html = template.render(**context)

    # Save file
    suburbs_dir = output_dir / "suburbs"
    suburbs_dir.mkdir(parents=True, exist_ok=True)

    slug = report.metrics.get_slug()
    output_path = suburbs_dir / f"{slug}.html"
    output_path.write_text(html, encoding='utf-8')

    print(f"✓ Suburb report saved: {output_path.name}")
    return output_path


def generate_all_reports(run_result: RunResult, output_dir: Path) -> dict:
    """
    Generate all HTML reports for a research run.

    Args:
        run_result: Complete RunResult object
        output_dir: Base output directory

    Returns:
        Dictionary with paths to generated files
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Generating HTML Reports")
    print(f"{'='*60}")
    print(f"Output directory: {output_dir}")
    print(f"Total suburbs: {len(run_result.suburbs)}")

    generated_files = {
        'index': None,
        'suburbs': []
    }

    # Generate overview report
    print(f"\n1. Generating overview report...")
    index_path = render_overview_report(run_result, output_dir)
    generated_files['index'] = index_path

    # Generate individual suburb reports
    print(f"\n2. Generating {len(run_result.suburbs)} suburb reports...")
    for i, report in enumerate(run_result.suburbs, 1):
        print(f"   [{i}/{len(run_result.suburbs)}] {report.metrics.get_display_name()}")
        suburb_path = render_suburb_report(report, output_dir)
        generated_files['suburbs'].append(suburb_path)

    print(f"\n{'='*60}")
    print(f"✓ Report generation complete!")
    print(f"{'='*60}")
    print(f"Generated files:")
    print(f"  - Overview: {index_path}")
    print(f"  - Suburbs: {len(generated_files['suburbs'])} reports")
    print(f"  - Charts: {len(list((output_dir / 'charts').glob('*.png')))} images")
    print(f"\nOpen in browser: file://{index_path.absolute()}")

    return generated_files


def copy_static_assets(output_dir: Path):
    """
    Copy CSS and other static assets to output directory.

    Args:
        output_dir: Output directory for the run
    """
    import shutil

    # Source static directory
    static_src = Path(__file__).parent.parent / "ui" / "web" / "static"
    static_dest = output_dir / "static"

    if static_src.exists():
        shutil.copytree(static_src, static_dest, dirs_exist_ok=True)
        print(f"✓ Static assets copied to {static_dest}")
    else:
        print(f"! Warning: Static assets not found at {static_src}")
