"""
HTML report generation for run comparisons.
"""
import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models.comparison import ComparisonResult

logger = logging.getLogger(__name__)


def generate_comparison_report(
    comparison: ComparisonResult,
    output_dir: Path,
) -> Path:
    """
    Generate an HTML comparison report.

    Args:
        comparison: ComparisonResult with all comparison data
        output_dir: Directory to save the report

    Returns:
        Path to the generated index.html
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    template_dir = Path(__file__).parent.parent / "ui" / "web" / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )

    template = env.get_template("compare_report.html")

    html = template.render(
        comparison=comparison,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    report_path = output_dir / "index.html"
    report_path.write_text(html, encoding="utf-8")

    logger.info("Comparison report generated: %s", report_path)
    return report_path
