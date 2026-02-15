"""
FastAPI web server for Australian Property Research application.

Provides a browser-based interface for running property research.
"""
import sys
import copy
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.inputs import UserInput
from models.run_result import RunResult
from app import run_research_pipeline
from config import settings, regions_data
from research.perplexity_client import (
    PerplexityRateLimitError, PerplexityAuthError, PerplexityAPIError
)
from research.anthropic_client import (
    AnthropicRateLimitError, AnthropicAuthError, AnthropicAPIError
)

# Combined error tuples
API_CREDIT_AUTH_ERRORS = (
    PerplexityRateLimitError, PerplexityAuthError,
    AnthropicRateLimitError, AnthropicAuthError,
)
API_GENERAL_ERRORS = (PerplexityAPIError, AnthropicAPIError)

# Initialize FastAPI app
app = FastAPI(
    title="Australian Property Research",
    description="AI-powered property investment research for Australian real estate",
    version="1.4.0"
)


# Global exception handler to sanitize all error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and sanitize before responding."""
    from security.sanitization import sanitize_text
    import logging
    import traceback

    # Log the full sanitized traceback
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {sanitize_text(str(exc))}")
    logger.error(traceback.format_exc())

    # Sanitize error message before including in HTTP response
    sanitized_msg = sanitize_text(str(exc))

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": sanitized_msg,
            "error_code": getattr(exc, "error_code", "UNKNOWN")
        }
    )

# Templates directory
template_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))

# Static files directory
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Output directory for reports
output_base = Path(__file__).parent.parent.parent.parent / "runs"
output_base.mkdir(exist_ok=True)

# In-memory storage for active runs
active_runs = {}
completed_runs = {}

# Thread pool for background tasks
executor = ThreadPoolExecutor(max_workers=2)


class RunStatus(BaseModel):
    """Status of a research run."""
    run_id: str
    status: str
    user_input: Optional[dict] = None
    suburbs_count: int = 0
    output_dir: Optional[str] = None
    error_message: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None


def run_pipeline_background(run_id: str, user_input: UserInput):
    """
    Run the research pipeline in the background.

    Args:
        run_id: Unique run identifier
        user_input: User input parameters
    """
    try:
        # Update status
        active_runs[run_id]["status"] = "running"

        def progress_callback(message: str):
            """Append progress step to active run."""
            if run_id in active_runs:
                active_runs[run_id].setdefault("steps", []).append({
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                })

        # Run pipeline
        result = run_research_pipeline(user_input, progress_callback=progress_callback)

        # Update completed runs
        completed_runs[run_id] = {
            "run_id": run_id,
            "status": result.status,
            "user_input": user_input.model_dump(),
            "suburbs_count": len(result.suburbs),
            "output_dir": str(result.output_dir) if result.output_dir else None,
            "error_message": result.error_message,
            "started_at": active_runs[run_id]["started_at"],
            "completed_at": datetime.now().isoformat()
        }

        # Remove from active
        if run_id in active_runs:
            del active_runs[run_id]

    except API_CREDIT_AUTH_ERRORS as e:
        # Handle API credit/auth errors with specific messaging
        from security.sanitization import sanitize_text
        error_msg = sanitize_text(str(e))
        completed_runs[run_id] = {
            "run_id": run_id,
            "status": "failed",
            "user_input": user_input.model_dump(),
            "suburbs_count": 0,
            "output_dir": None,
            "error_message": error_msg,
            "started_at": active_runs[run_id]["started_at"],
            "completed_at": datetime.now().isoformat()
        }

        if run_id in active_runs:
            del active_runs[run_id]

    except API_GENERAL_ERRORS as e:
        # Handle general API errors
        from security.sanitization import sanitize_text
        error_msg = sanitize_text(f"API Error: {str(e)}")
        completed_runs[run_id] = {
            "run_id": run_id,
            "status": "failed",
            "user_input": user_input.model_dump(),
            "suburbs_count": 0,
            "output_dir": None,
            "error_message": error_msg,
            "started_at": active_runs[run_id]["started_at"],
            "completed_at": datetime.now().isoformat()
        }

        if run_id in active_runs:
            del active_runs[run_id]

    except Exception as e:
        # Handle other errors
        from security.sanitization import sanitize_text
        error_msg = sanitize_text(str(e))
        completed_runs[run_id] = {
            "run_id": run_id,
            "status": "failed",
            "user_input": user_input.model_dump(),
            "suburbs_count": 0,
            "output_dir": None,
            "error_message": error_msg,
            "started_at": active_runs[run_id]["started_at"],
            "completed_at": datetime.now().isoformat()
        }

        if run_id in active_runs:
            del active_runs[run_id]


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with research form."""
    return templates.TemplateResponse(
        "web_index.html",
        {
            "request": request,
            "regions": list(regions_data.REGIONS.keys()),
            "dwelling_types": ["house", "apartment", "townhouse"],
            "providers": settings.AVAILABLE_PROVIDERS,
            "default_provider": settings.DEFAULT_PROVIDER,
        }
    )


@app.post("/run")
async def start_run(
    background_tasks: BackgroundTasks,
    max_price: float = Form(...),
    dwelling_type: str = Form(...),
    regions: List[str] = Form(...),
    num_suburbs: int = Form(5),
    provider: str = Form(None),
):
    """Start a new research run."""
    # Generate run ID
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Validate provider
    if provider not in settings.AVAILABLE_PROVIDERS:
        provider = settings.DEFAULT_PROVIDER

    # Create user input
    user_input = UserInput(
        max_median_price=max_price,
        dwelling_type=dwelling_type,
        regions=regions,
        num_suburbs=num_suburbs,
        provider=provider,
        run_id=run_id,
        interface_mode="gui"
    )

    # Add to active runs
    active_runs[run_id] = {
        "run_id": run_id,
        "status": "starting",
        "user_input": user_input.model_dump(),
        "started_at": datetime.now().isoformat(),
        "steps": []
    }

    # Start background task
    background_tasks.add_task(run_pipeline_background, run_id, user_input)

    # Redirect to status page
    return RedirectResponse(f"/status/{run_id}", status_code=303)


@app.get("/status/{run_id}", response_class=HTMLResponse)
async def run_status(request: Request, run_id: str):
    """Show status of a research run."""
    # Check if run exists
    if run_id in active_runs:
        status = active_runs[run_id]
    elif run_id in completed_runs:
        status = completed_runs[run_id]
    else:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": f"Run {run_id} not found"}
        )

    return templates.TemplateResponse(
        "run_status.html",
        {"request": request, "status": status}
    )


@app.get("/api/status/{run_id}")
async def api_run_status(run_id: str):
    """API endpoint for run status (for AJAX polling)."""
    if run_id in active_runs:
        # Return a snapshot copy to avoid thread-safety issues
        data = copy.deepcopy(active_runs[run_id])
    elif run_id in completed_runs:
        data = completed_runs[run_id]
    else:
        data = {"error": "Run not found"}

    return JSONResponse(
        content=data,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
    )


@app.get("/runs", response_class=HTMLResponse)
async def list_runs(request: Request):
    """List all research runs."""
    # Get all runs from filesystem
    runs = []
    if output_base.exists():
        for run_dir in sorted(output_base.iterdir(), reverse=True):
            if run_dir.is_dir():
                index_file = run_dir / "index.html"
                if index_file.exists():
                    runs.append({
                        "run_id": run_dir.name,
                        "path": str(run_dir),
                        "created": datetime.fromtimestamp(run_dir.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    })

    return templates.TemplateResponse(
        "runs_list.html",
        {"request": request, "runs": runs, "active_runs": active_runs}
    )


@app.get("/view/{run_id}/{path:path}")
async def view_report(run_id: str, path: str = "index.html"):
    """View a generated report."""
    report_path = output_base / run_id / path

    if not report_path.exists():
        return HTMLResponse(f"Report not found: {path}", status_code=404)

    # Serve the file
    return FileResponse(report_path)


@app.get("/export/{run_id}/{format}")
async def export_report(run_id: str, format: str):
    """Generate and serve a PDF or Excel export."""
    if format not in ('pdf', 'xlsx'):
        return HTMLResponse("Invalid format. Use 'pdf' or 'xlsx'.", status_code=400)

    run_dir = output_base / run_id
    if not run_dir.exists() or not (run_dir / "index.html").exists():
        return HTMLResponse(f"Run {run_id} not found.", status_code=404)

    # Determine expected output filename
    if format == 'pdf':
        export_path = run_dir / f"report_{run_id}.pdf"
    else:
        export_path = run_dir / f"report_{run_id}.xlsx"

    # Generate if not already cached
    if not export_path.exists():
        from reporting.exports import (
            generate_pdf_export, generate_excel_export,
            reconstruct_run_result, ExportError
        )

        # Try to reconstruct RunResult from metadata file
        run_result = reconstruct_run_result(run_id, run_dir)

        if run_result is None:
            return HTMLResponse(
                "Cannot export: run metadata not found. "
                "This run was created before export support was added.",
                status_code=404
            )

        try:
            if format == 'pdf':
                export_path = generate_pdf_export(run_result, run_dir)
            else:
                export_path = generate_excel_export(run_result, run_dir)
        except ExportError as e:
            return HTMLResponse(f"Export failed: {str(e)}", status_code=500)
        except Exception as e:
            return HTMLResponse(f"Export error: {str(e)}", status_code=500)

    # Serve the file
    media_type = (
        "application/pdf" if format == "pdf"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return FileResponse(
        path=str(export_path),
        media_type=media_type,
        filename=export_path.name
    )


def _get_completed_runs():
    """Get list of completed runs from filesystem."""
    runs = []
    if output_base.exists():
        for run_dir in sorted(output_base.iterdir(), reverse=True):
            if run_dir.is_dir() and not run_dir.name.startswith("compare_"):
                index_file = run_dir / "index.html"
                if index_file.exists():
                    runs.append({
                        "run_id": run_dir.name,
                        "path": str(run_dir),
                        "created": datetime.fromtimestamp(
                            run_dir.stat().st_mtime
                        ).strftime("%Y-%m-%d %H:%M:%S"),
                    })
    return runs


@app.get("/compare", response_class=HTMLResponse)
async def compare_select(request: Request):
    """Show run selection page for comparison."""
    runs = _get_completed_runs()
    return templates.TemplateResponse(
        "compare_select.html",
        {"request": request, "runs": runs, "error": None}
    )


@app.post("/compare")
async def compare_submit(
    request: Request,
    run_ids: List[str] = Form(...),
):
    """Generate comparison report for selected runs."""
    if len(run_ids) < 2 or len(run_ids) > 3:
        runs = _get_completed_runs()
        return templates.TemplateResponse(
            "compare_select.html",
            {
                "request": request,
                "runs": runs,
                "error": "Please select 2 or 3 runs to compare.",
            }
        )

    try:
        from research.comparison import compare_runs, ComparisonError
        from reporting.comparison_renderer import generate_comparison_report

        comparison = compare_runs(run_ids, output_base)
        compare_id = f"compare_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        compare_dir = output_base / compare_id
        generate_comparison_report(comparison, compare_dir)
        return RedirectResponse(f"/compare/{compare_id}", status_code=303)
    except Exception as e:
        runs = _get_completed_runs()
        return templates.TemplateResponse(
            "compare_select.html",
            {"request": request, "runs": runs, "error": str(e)}
        )


@app.get("/compare/{compare_id}", response_class=HTMLResponse)
async def view_comparison(compare_id: str):
    """View a comparison report."""
    report_path = output_base / compare_id / "index.html"
    if not report_path.exists():
        return HTMLResponse("Comparison report not found.", status_code=404)
    return FileResponse(report_path)


@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics."""
    from research.cache import get_cache
    cache = get_cache()
    return cache.stats()


@app.post("/cache/clear")
async def cache_clear():
    """Clear the research cache."""
    from research.cache import get_cache
    cache = get_cache()
    count = cache.clear()
    return {"cleared": count}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from research.cache import get_cache
    cache = get_cache()
    cache_info = cache.stats()
    return {
        "status": "healthy",
        "available_providers": settings.AVAILABLE_PROVIDERS,
        "default_provider": settings.DEFAULT_PROVIDER,
        "active_runs": len(active_runs),
        "completed_runs": len(completed_runs),
        "cache_entries": cache_info["total_entries"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
