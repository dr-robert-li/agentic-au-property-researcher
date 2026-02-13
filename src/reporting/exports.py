"""
Export orchestration for PDF and Excel report generation.

Provides public API for generating exports and reconstructing
RunResult from saved metadata for past runs.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from models.run_result import RunResult
from reporting.pdf_exporter import generate_pdf
from reporting.excel_exporter import generate_excel

logger = logging.getLogger(__name__)


class ExportError(Exception):
    """Raised when export generation fails."""
    pass


def generate_pdf_export(run_result: RunResult, output_dir: Path) -> Path:
    """
    Generate a PDF report for a completed research run.

    Args:
        run_result: Complete RunResult with all suburb reports
        output_dir: The run's output directory (contains charts/, suburbs/, etc.)

    Returns:
        Path to the generated PDF file

    Raises:
        ExportError: If PDF generation fails
    """
    pdf_path = output_dir / f"report_{run_result.run_id}.pdf"
    try:
        generate_pdf(run_result, output_dir, pdf_path)
    except Exception as e:
        raise ExportError(f"PDF generation failed: {e}") from e
    logger.info(f"PDF exported: {pdf_path}")
    return pdf_path


def generate_excel_export(run_result: RunResult, output_dir: Path) -> Path:
    """
    Generate an Excel workbook for a completed research run.

    Args:
        run_result: Complete RunResult with all suburb reports
        output_dir: The run's output directory

    Returns:
        Path to the generated .xlsx file

    Raises:
        ExportError: If Excel generation fails
    """
    xlsx_path = output_dir / f"report_{run_result.run_id}.xlsx"
    try:
        generate_excel(run_result, xlsx_path)
    except Exception as e:
        raise ExportError(f"Excel generation failed: {e}") from e
    logger.info(f"Excel exported: {xlsx_path}")
    return xlsx_path


def reconstruct_run_result(run_id: str, output_dir: Path) -> Optional[RunResult]:
    """
    Reconstruct a RunResult from a saved run directory.

    Reads run_metadata.json saved alongside HTML reports so that
    exports can be triggered on past runs.

    Args:
        run_id: The run identifier
        output_dir: Path to the run's output directory

    Returns:
        Reconstructed RunResult, or None if metadata file not found
    """
    metadata_path = output_dir / "run_metadata.json"
    if not metadata_path.exists():
        return None

    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
        return RunResult.model_validate(data)
    except Exception as e:
        logger.warning(f"Failed to reconstruct RunResult for {run_id}: {e}")
        return None
