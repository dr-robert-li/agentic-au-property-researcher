# Architecture

**Analysis Date:** 2026-02-15

## Pattern Overview

**Overall:** Layered Pipeline Architecture with Orchestrator Pattern

**Key Characteristics:**
- Sequential stages (discovery → research → ranking → reporting)
- Parallel execution within each stage using ThreadPoolExecutor
- Abstraction of research provider (Perplexity, Anthropic) via pluggable clients
- Dual UI layer (FastAPI web server + CLI with prompt_toolkit)
- File-based caching to reduce API calls
- Pydantic models for data validation and type safety

## Layers

**UI Layer (Presentation):**
- Purpose: Handle user interaction via web browser or CLI
- Location: `src/ui/web/` and `src/ui/cli/`
- Contains: FastAPI server (`server.py`), CLI prompts (`interactive.py`), HTML templates (`templates/`)
- Depends on: Models, App orchestrator, Config
- Used by: Web browsers, CLI terminals

**Orchestration Layer:**
- Purpose: Coordinate the complete research pipeline from input to output
- Location: `src/app.py`
- Contains: `run_research_pipeline()` function that sequences discovery → research → ranking → reporting
- Depends on: Research layer, Reporting layer, Models
- Used by: UI layer, CLI interface, web server

**Research Layer:**
- Purpose: Execute AI research via external APIs, manage data transformations, cache results
- Location: `src/research/`
- Contains:
  - `suburb_discovery.py`: Parallel discovery of candidate suburbs
  - `suburb_research.py`: Detailed per-suburb research with parallel batch processing
  - `ranking.py`: Rank suburbs by composite scores
  - `perplexity_client.py`: Perplexity API wrapper with error handling
  - `anthropic_client.py`: Anthropic Claude API wrapper
  - `cache.py`: File-based JSON cache with TTL support
  - `comparison.py`: Compare multiple research runs
- Depends on: Models, Config, external APIs (Perplexity, Anthropic)
- Used by: Orchestrator, Reporting layer

**Models Layer:**
- Purpose: Define data structures and schemas
- Location: `src/models/`
- Contains:
  - `inputs.py`: `UserInput` model (price, region, dwelling type, etc.)
  - `suburb_metrics.py`: Complete `SuburbMetrics` with 7 nested models (identification, market, demographics, infrastructure, growth, etc.)
  - `run_result.py`: `RunResult` and `SuburbReport` for pipeline output
  - `comparison.py`: Comparison data structures
- Depends on: Pydantic
- Used by: All layers

**Reporting Layer:**
- Purpose: Generate HTML reports, charts, PDF/Excel exports
- Location: `src/reporting/`
- Contains:
  - `html_renderer.py`: Render overview and suburb-level HTML via Jinja2
  - `charts.py`: Generate matplotlib charts (price history, growth projections, comparison bar charts)
  - `exports.py`: PDF and Excel export coordination
  - `pdf_exporter.py`: HTML to PDF conversion with wkhtmltopdf
  - `excel_exporter.py`: Suburb data to XLSX export
  - `comparison_renderer.py`: Side-by-side comparison reports
- Depends on: Models, Jinja2, matplotlib, reportlab/wkhtmltopdf
- Used by: Orchestrator

**Config Layer:**
- Purpose: Manage environment variables, API keys, constants, paths
- Location: `src/config/`
- Contains:
  - `settings.py`: Load `.env`, define output dir, API timeouts, parallel workers
  - `regions_data.py`: Region/state definitions, multi-region filter descriptions
- Depends on: python-dotenv, os, pathlib
- Used by: All layers

## Data Flow

**Main Pipeline (run_research_pipeline in `src/app.py`):**

1. **Input Validation** → Create `UserInput` from CLI args or form data
2. **Suburb Discovery** → `parallel_discover_suburbs()` calls Perplexity once per region group
   - Input: `UserInput` (max price, dwelling type, regions, target N)
   - Process: Region description built, deep-research call to Perplexity
   - Output: List of `SuburbCandidate` (N×5 candidates for filtering)
3. **Detailed Research** → `parallel_research_suburbs()` research up to N×3 candidates
   - Input: `SuburbCandidate` objects
   - Process: Each suburb researched in parallel (max 3 workers), JSON response parsed into `SuburbMetrics`
   - Output: List of `SuburbMetrics` with all market/demographic/growth data
4. **Ranking** → `rank_suburbs()` sorts by composite_score, selects top N
   - Input: `SuburbMetrics` list
   - Process: Calculate growth_score, risk_score, composite_score; sort and assign ranks
   - Output: List of `SuburbReport` (with rank field populated)
5. **Report Generation** → `generate_all_reports()` renders HTML and charts
   - Input: `RunResult` with ranked suburbs
   - Process: Generate overview index.html + per-suburb HTML; create matplotlib charts
   - Output: Timestamped directory with index.html, suburbs/, charts/, static/
6. **Export (optional)** → `generate_pdf_export()` or `generate_excel_export()`
   - Input: `RunResult` or reconstructed from metadata
   - Process: Render to PDF via wkhtmltopdf or to XLSX via openpyxl
   - Output: report_{run_id}.pdf or report_{run_id}.xlsx

**Caching Flow:**

- Each API call key is hashed and checked against cache index
- Cache TTL: 24 hours (discovery), 7 days (research) by default
- Cache maintained in `cache/` directory with `cache_index.json` metadata
- Cache hit returns parsed JSON; cache miss calls API and stores result

**Comparison Flow:**

- `compare_runs()` loads 2-3 completed runs from `runs/{run_id}/metadata.json`
- Reconstructs `RunResult` objects, computes side-by-side statistics
- `generate_comparison_report()` renders side-by-side HTML with diff highlights

## Key Abstractions

**UserInput:**
- Purpose: Encapsulate user search parameters with validation
- Examples: `src/models/inputs.py`
- Pattern: Pydantic BaseModel with field validators for regions, num_suburbs

**SuburbMetrics:**
- Purpose: Normalized representation of all suburb research data
- Examples: `src/models/suburb_metrics.py`
- Pattern: Composite Pydantic model (7 nested models: Identification, MarketMetricsCurrent, MarketMetricsHistory, PhysicalConfig, Demographics, Infrastructure, GrowthProjections)

**SuburbCandidate:**
- Purpose: Lightweight result from discovery phase (not yet fully researched)
- Examples: `src/research/suburb_discovery.py` lines 46-60
- Pattern: Data class with fields extracted from Perplexity JSON response

**SuburbReport:**
- Purpose: Combines metrics with rendering artifacts (narrative HTML, chart filenames)
- Examples: `src/models/run_result.py` lines 13-25
- Pattern: Pydantic model wrapping SuburbMetrics, includes rank and chart paths

**RunResult:**
- Purpose: Container for complete pipeline output (all suburbs + metadata + status)
- Examples: `src/models/run_result.py` lines 28-65
- Pattern: Pydantic model with optional output_dir, status tracking, error messages

**Research Clients:**
- Purpose: Abstract API differences between Perplexity and Anthropic
- Examples: `src/research/perplexity_client.py`, `src/research/anthropic_client.py`
- Pattern: Class-based client with `call_deep_research()` method; factory function `get_client(provider)` returns correct instance

**AccountErrorSignal:**
- Purpose: Thread-safe flag for propagating account-level errors (rate limits, auth) across parallel workers
- Examples: `src/research/suburb_discovery.py` lines 25-43
- Pattern: Singleton-like class with lock-protected `_error` and `is_set` property

## Entry Points

**Web Server:**
- Location: `src/ui/web/server.py`
- Triggers: `python run_web.py` or `python -m src.ui.web.server`
- Responsibilities:
  - FastAPI app initialization with Jinja2 template support
  - Route handlers: GET `/` (home form), POST `/run` (start research), GET `/status/{run_id}`, GET `/runs` (list all)
  - Background task execution for pipeline via ThreadPoolExecutor
  - File serving for generated reports and exports

**CLI:**
- Location: `src/app.py::main()`
- Triggers: `python -m src.app --max-price 700000 --dwelling-type house`
- Responsibilities:
  - Parse command-line arguments (price, dwelling type, regions, suburbs, provider, exports)
  - Call `run_research_pipeline(user_input)` synchronously
  - Handle special modes: `--clear-cache`, `--compare {run_ids}`

**Interactive CLI:**
- Location: `src/ui/cli/interactive.py::run_interactive_cli()`
- Triggers: Invoked from web UI or custom launcher
- Responsibilities:
  - Prompt for price, dwelling type, regions (with autocomplete), num suburbs
  - Rich console output with tables and panels
  - Progress display via rich.progress

## Error Handling

**Strategy:** Differentiate between account-level errors (stop immediately) and transient errors (retry or skip individual items)

**Patterns:**

**Account-level Errors** (stop all work):
- `PerplexityRateLimitError`: Raised when API credit exhausted or rate limited
- `PerplexityAuthError`: Raised when API key invalid or inactive
- `AnthropicRateLimitError` / `AnthropicAuthError`: Equivalent for Anthropic
- Handling: Caught at top level in `run_research_pipeline()`, set `run_result.status = "failed"`, return early
- Location: `src/app.py` lines 163-170

**Transient Errors** (skip item, continue):
- `PerplexityAPIError` / `AnthropicAPIError`: Timeouts, server errors, JSON parse failures
- Handling: Caught in parallel loops, signal added to error set, worker skips suburb, continues batch
- Location: `src/research/suburb_research.py` lines 35-40

**Validation Errors:**
- Pydantic raises `ValidationError` if input fields invalid (negative price, invalid region)
- User-facing validators in CLI: `PriceValidator`, `NumSuburbsValidator`
- Location: `src/ui/cli/interactive.py` lines 30-63

**JSON Parse Failures:**
- API returns invalid JSON or missing required fields
- Caught in `parse_suburb_json()`, logged, suburbs marked as failed
- Retry logic: 3 max retries with exponential backoff

## Cross-Cutting Concerns

**Logging:**
- Approach: Python logging module, logger per module via `logging.getLogger(__name__)`
- Console output via `print()` for user-facing progress
- Progress callback mechanism passed through pipeline for real-time updates to web UI

**Validation:**
- Input validation: Pydantic models with field validators (UserInput, SuburbMetrics)
- CLI validation: prompt_toolkit validators (PriceValidator, NumSuburbsValidator)
- Region validation: Check against `REGIONS` dict in `regions_data.py`

**Authentication:**
- Approach: Load API keys from `.env` at startup (settings.py)
- Perplexity SDK handles auth internally; errors caught and wrapped in custom exceptions
- Anthropic SDK similarly wrapped
- No token refresh; assume keys are long-lived or pre-validated
