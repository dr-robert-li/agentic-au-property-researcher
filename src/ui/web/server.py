"""
FastAPI web server for Australian Property Research application.

Provides a browser-based interface for running property research.
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.inputs import UserInput
from models.run_result import RunResult
from app import run_research_pipeline
from config import regions_data
from research.perplexity_client import (
    PerplexityRateLimitError, PerplexityAuthError, PerplexityAPIError
)

# Initialize FastAPI app
app = FastAPI(
    title="Australian Property Research",
    description="AI-powered property investment research for Australian real estate",
    version="0.1.0"
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

        # Run pipeline
        result = run_research_pipeline(user_input)

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

    except (PerplexityRateLimitError, PerplexityAuthError) as e:
        # Handle API credit/auth errors with specific messaging
        error_msg = (
            f"{str(e)}\n\n"
            f"Please check your API credit balance at:\n"
            f"https://www.perplexity.ai/account/api/billing"
        )
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

    except PerplexityAPIError as e:
        # Handle general API errors
        error_msg = (
            f"Perplexity API Error: {str(e)}\n\n"
            f"Check your API status and credits at:\n"
            f"https://www.perplexity.ai/account/api/billing"
        )
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
        completed_runs[run_id] = {
            "run_id": run_id,
            "status": "failed",
            "user_input": user_input.model_dump(),
            "suburbs_count": 0,
            "output_dir": None,
            "error_message": str(e),
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
            "dwelling_types": ["house", "apartment", "townhouse"]
        }
    )


@app.post("/run")
async def start_run(
    background_tasks: BackgroundTasks,
    max_price: float = Form(...),
    dwelling_type: str = Form(...),
    regions: List[str] = Form(...),
    num_suburbs: int = Form(5)
):
    """Start a new research run."""
    # Generate run ID
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Create user input
    user_input = UserInput(
        max_median_price=max_price,
        dwelling_type=dwelling_type,
        regions=regions,
        num_suburbs=num_suburbs,
        run_id=run_id,
        interface_mode="gui"
    )

    # Add to active runs
    active_runs[run_id] = {
        "run_id": run_id,
        "status": "starting",
        "user_input": user_input.model_dump(),
        "started_at": datetime.now().isoformat()
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
        return active_runs[run_id]
    elif run_id in completed_runs:
        return completed_runs[run_id]
    else:
        return {"error": "Run not found"}


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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_runs": len(active_runs),
        "completed_runs": len(completed_runs)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
