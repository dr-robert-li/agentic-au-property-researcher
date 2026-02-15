# Codebase Structure

**Analysis Date:** 2026-02-15

## Directory Layout

```
agentic-re-researcher/
├── src/                       # Main application code
│   ├── __init__.py
│   ├── app.py                 # Main orchestrator: run_research_pipeline()
│   ├── config/                # Configuration and settings
│   │   ├── __init__.py
│   │   ├── settings.py        # Load .env, API keys, timeouts, paths
│   │   └── regions_data.py    # Region/state definitions, region descriptions
│   ├── models/                # Data models (Pydantic)
│   │   ├── __init__.py
│   │   ├── inputs.py          # UserInput model
│   │   ├── suburb_metrics.py  # SuburbMetrics and nested models
│   │   ├── run_result.py      # RunResult, SuburbReport
│   │   └── comparison.py      # Comparison models
│   ├── research/              # Research pipeline (discovery, research, ranking, caching)
│   │   ├── __init__.py
│   │   ├── perplexity_client.py     # Perplexity API wrapper
│   │   ├── anthropic_client.py      # Anthropic Claude API wrapper
│   │   ├── suburb_discovery.py      # parallel_discover_suburbs()
│   │   ├── suburb_research.py       # parallel_research_suburbs()
│   │   ├── ranking.py               # rank_suburbs()
│   │   ├── cache.py                 # ResearchCache, caching logic
│   │   └── comparison.py            # compare_runs()
│   ├── reporting/             # Report generation (HTML, charts, exports)
│   │   ├── __init__.py
│   │   ├── html_renderer.py         # Jinja2 template rendering
│   │   ├── charts.py                # matplotlib chart generation
│   │   ├── exports.py               # PDF/Excel export coordination
│   │   ├── pdf_exporter.py          # HTML to PDF via wkhtmltopdf
│   │   ├── excel_exporter.py        # XLSX export via openpyxl
│   │   └── comparison_renderer.py   # Side-by-side comparison HTML
│   └── ui/                    # User interfaces (web and CLI)
│       ├── __init__.py
│       ├── web/               # FastAPI web server
│       │   ├── __init__.py
│       │   ├── server.py      # FastAPI app, routes, background tasks
│       │   ├── static/        # Static assets (CSS, JS)
│       │   │   ├── css/
│       │   │   └── js/
│       │   └── templates/     # Jinja2 HTML templates
│       │       ├── base.html
│       │       ├── web_index.html      # Home form
│       │       ├── run_status.html     # Progress page
│       │       ├── runs_list.html      # Past runs
│       │       ├── suburb_report.html  # Per-suburb template
│       │       ├── index.html          # Overview (generated)
│       │       ├── compare_select.html # Comparison selection
│       │       ├── compare_report.html # Comparison results
│       │       └── error.html
│       └── cli/               # CLI interface
│           ├── __init__.py
│           └── interactive.py # Interactive prompts (prompt_toolkit, rich)
├── tests/                     # Test suite (pytest)
│   ├── test_*.py              # Unit and integration tests
│   └── conftest.py            # Pytest fixtures
├── runs/                      # Output directory for run results (created at runtime)
│   └── {run_id}/              # Timestamped run folder
│       ├── index.html         # Overview report
│       ├── suburbs/           # Suburb-level reports
│       │   └── {suburb_slug}.html
│       ├── charts/            # Generated PNG/SVG charts
│       ├── static/            # CSS/JS assets for this run
│       ├── metadata.json      # Run metadata for reconstruction
│       └── report_{run_id}.pdf / .xlsx  # Optional exports
├── cache/                     # Research cache (created at runtime)
│   ├── cache_index.json       # Cache metadata
│   └── *.json                 # Individual cached responses
├── run_web.py                 # Script: Start web server + open browser
├── validate_setup.py          # Script: Test Perplexity/Anthropic connectivity
├── requirements.txt           # Python dependencies
├── .env                       # API keys and config (not in git)
├── .env.example               # Template for .env
├── .gitignore                 # Exclude .env, cache/, runs/, __pycache__
├── CLAUDE.md                  # Project specification
├── README.md                  # User guide
├── CHANGELOG.md               # Version history
├── CONTRIBUTING.md            # Development guide
├── LICENSE                    # MIT license
└── .planning/                 # GSD planning directory (not in main src)
    └── codebase/
        ├── ARCHITECTURE.md    # (this file)
        ├── STRUCTURE.md       # (this file)
        ├── CONVENTIONS.md     # (if quality focus)
        ├── TESTING.md         # (if quality focus)
        ├── STACK.md           # (if tech focus)
        ├── INTEGRATIONS.md    # (if tech focus)
        └── CONCERNS.md        # (if concerns focus)
```

## Directory Purposes

**src/**
- Purpose: All source code for the application
- Contains: Python modules organized by functional layer
- Key files: Entry point is `src/app.py` (CLI) or `run_web.py` (web server)

**src/config/**
- Purpose: Centralized configuration and environment management
- Contains: Settings loaded from `.env`, region data structures
- Key files:
  - `settings.py`: Load PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, paths, timeouts, provider selection
  - `regions_data.py`: REGIONS dict with predefined Australian regions/states

**src/models/**
- Purpose: Data models for type safety and validation
- Contains: Pydantic BaseModel subclasses
- Key files:
  - `inputs.py`: UserInput captures max_median_price, dwelling_type, regions, num_suburbs, provider
  - `suburb_metrics.py`: SuburbMetrics (7 nested models) with all research results
  - `run_result.py`: RunResult (top-level container) and SuburbReport (ranked suburb with rank/charts)

**src/research/**
- Purpose: AI research execution and data transformation
- Contains: API clients, discovery/research/ranking pipeline, caching, comparison
- Key files:
  - `perplexity_client.py`: PerplexityClient wrapper, custom exceptions (PerplexityRateLimitError, PerplexityAuthError)
  - `suburb_discovery.py`: parallel_discover_suburbs() using ThreadPoolExecutor
  - `suburb_research.py`: parallel_research_suburbs() for detailed per-suburb research
  - `cache.py`: ResearchCache with file-based JSON storage and TTL

**src/reporting/**
- Purpose: Generate HTML reports, charts, and exports
- Contains: Jinja2 rendering, matplotlib chart generation, PDF/Excel export
- Key files:
  - `html_renderer.py`: render_overview_report(), render_suburb_report() using Jinja2 Environment
  - `charts.py`: generate_price_history_chart(), generate_growth_projection_chart(), etc.
  - `exports.py`: generate_pdf_export(), generate_excel_export() with metadata reconstruction

**src/ui/web/**
- Purpose: FastAPI-based web interface
- Contains: HTTP routes, background task execution, template rendering
- Key files:
  - `server.py`: FastAPI app, routes (GET /, POST /run, GET /status/{run_id}, GET /runs)
  - `templates/`: Jinja2 templates for forms, progress, reports
  - `static/`: CSS and JavaScript for web UI

**src/ui/cli/**
- Purpose: Interactive command-line interface
- Contains: prompt_toolkit prompts, rich console formatting, progress display
- Key files:
  - `interactive.py`: PriceValidator, NumSuburbsValidator, print_welcome(), regional autocomplete

**tests/**
- Purpose: Automated testing (unit, integration)
- Contains: pytest test files
- Pattern: Test files named test_*.py parallel src structure

**runs/**
- Purpose: Output directory for research run results (created at runtime)
- Contains: Timestamped folders with generated reports
- Structure per run:
  - `index.html`: Overview with ranking table and summary charts
  - `suburbs/{suburb_slug}.html`: Per-suburb detailed reports
  - `charts/`: PNG files (price history, growth projection, comparison bars)
  - `static/`: CSS/JS assets copied to each run
  - `metadata.json`: Run metadata for reconstruction/comparison

**cache/**
- Purpose: Store API responses to reduce costs and improve responsiveness
- Contains: JSON cache files and index
- Files:
  - `cache_index.json`: Index of all cached entries with TTL metadata
  - `{hash}.json`: Individual cached API responses

## Key File Locations

**Entry Points:**

- `src/app.py`: CLI entry point — `main()` function with argparse
  - Usage: `python -m src.app --max-price 700000 --dwelling-type house`
  - Triggers: `run_research_pipeline(user_input)`

- `run_web.py`: Web server launcher
  - Usage: `python run_web.py`
  - Opens http://127.0.0.1:8000 in browser
  - Serves FastAPI app from `src/ui/web/server.py`

- `src/ui/web/server.py`: FastAPI application
  - Routes: `GET /`, `POST /run`, `GET /status/{run_id}`, `GET /runs`
  - Triggered by: Web browsers, form submissions

**Configuration:**

- `src/config/settings.py`: Load `.env`, define PERPLEXITY_API_KEY, ANTHROPIC_API_KEY, paths, timeouts
- `src/config/regions_data.py`: Region definitions (REGIONS dict), build_region_filter_description()

**Core Logic:**

- `src/app.py::run_research_pipeline()`: Main orchestrator (lines 36-194)
  - Steps: discovery → research → ranking → reporting
  - Progress callbacks for web UI updates

- `src/research/suburb_discovery.py::parallel_discover_suburbs()`: Parallel region-based discovery
  - Uses: ThreadPoolExecutor with DISCOVERY_MAX_WORKERS
  - Handles: AccountErrorSignal for rate limit propagation

- `src/research/suburb_research.py::parallel_research_suburbs()`: Parallel detailed research
  - Uses: ThreadPoolExecutor with RESEARCH_MAX_WORKERS
  - Retries: 3 max retries for transient errors

- `src/research/ranking.py::rank_suburbs()`: Sort by composite_score, assign ranks

**Testing:**

- `tests/test_end_to_end.py`: Full pipeline test
- `tests/test_perplexity.py`: Perplexity client tests
- `tests/test_charts.py`: Chart generation tests
- `tests/test_cache.py`: Cache functionality tests

## Naming Conventions

**Files:**

- Python modules: `lowercase_with_underscores.py`
  - Examples: `suburb_discovery.py`, `html_renderer.py`, `interactive.py`

- HTML templates: `descriptive_name.html`
  - Examples: `web_index.html`, `suburb_report.html`, `compare_report.html`

- Generated reports in runs/: `index.html`, `{suburb_slug}.html`
  - Examples: `acacia-ridge-qld.html` (from `get_slug()` method)

- Chart files in runs/charts/: `{chart_type}_{suburb_slug}.png`
  - Examples: `price_history_acacia-ridge-qld.png`, `growth_projection_acacia-ridge-qld.png`

**Directories:**

- Functional areas: lowercase plural or descriptive
  - Examples: `config/`, `models/`, `research/`, `reporting/`, `ui/`

- UI sub-areas: `web/`, `cli/` (lowercase, indicates transport/interface type)

- Generated output: `runs/` and `cache/` (lowercase, indicates data artifacts)

**Python Classes:**

- PascalCase for classes
  - Examples: `UserInput`, `SuburbMetrics`, `SuburbReport`, `PerplexityClient`, `ResearchCache`

- Exception classes end in `Error` or `Exception`
  - Examples: `PerplexityRateLimitError`, `PerplexityAuthError`, `PerplexityAPIError`

**Python Functions:**

- `snake_case` for functions
  - Examples: `discover_suburbs()`, `parallel_research_suburbs()`, `rank_suburbs()`, `generate_all_reports()`

**Environment Variables:**

- SCREAMING_SNAKE_CASE
  - Examples: `PERPLEXITY_API_KEY`, `OUTPUT_DIR`, `CACHE_ENABLED`, `DISCOVERY_MAX_WORKERS`

## Where to Add New Code

**New Feature (E.g., Add SMS Alerts):**

1. **Model**: Define input/output in `src/models/`
   - Example: `src/models/inputs.py` add `phone_number: Optional[str]` to UserInput

2. **Research/Logic**: Implement feature in appropriate layer
   - Example: Add `src/research/notifications.py` with `send_sms_alert()`

3. **Integration**: Call from orchestrator
   - Example: Call in `src/app.py::run_research_pipeline()` at step 4 (after reports generated)

4. **UI**: Add to web form and CLI
   - Example: Add input field to `src/ui/web/templates/web_index.html`
   - Example: Add prompt in `src/ui/cli/interactive.py`

5. **Tests**: Write tests in `tests/test_new_feature.py`

**New API Provider (E.g., OpenAI):**

1. **Client Wrapper**: Create `src/research/openai_client.py`
   - Pattern: Follow `perplexity_client.py` structure
   - Implement: `OpenAIClient` class with `call_deep_research()` method
   - Implement: Custom exceptions `OpenAIRateLimitError`, `OpenAIAuthError`

2. **Settings**: Register provider in `src/config/settings.py`
   - Add: `OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")`
   - Add: `"openai"` to `AVAILABLE_PROVIDERS` if key present

3. **Discovery/Research**: Update discovery/research functions to support provider
   - In `suburb_discovery.py`: `client = get_client(user_input.provider)`
   - In `suburb_research.py`: `client = get_client(provider)`

4. **Tests**: Write provider-specific tests in `tests/test_openai.py`

**New Chart Type (E.g., Auction Clearance Trend):**

1. **Chart Function**: Add to `src/reporting/charts.py`
   - Pattern: Follow `generate_price_history_chart()` structure
   - Input: `SuburbMetrics` and `output_path`
   - Return: `bool` (True if data available, False if missing)

2. **Template Integration**: Reference in `src/ui/web/templates/suburb_report.html`
   - Add: `<img src="./charts/{{ charts.clearance_trend }}" alt="Clearance Trend">`

3. **Renderer**: Call in `src/reporting/html_renderer.py::render_suburb_report()`
   - Add: `generate_clearance_trend_chart()` call to `generate_all_suburb_charts()` loop

4. **Tests**: Add test in `tests/test_charts.py`

**New Comparison Metric:**

1. **Model**: Add field to `src/models/comparison.py`
   - Example: `median_price_growth_ranks: dict[str, list[int]]`

2. **Calculation**: Implement in `src/research/comparison.py::compare_runs()`
   - Extract and compute metric across runs

3. **Template**: Reference in `src/ui/web/templates/compare_report.html`
   - Add: HTML table row for metric

4. **Tests**: Add test in `tests/test_comparison.py`

**New Suburb Data Field (E.g., Walkability Score):**

1. **Model**: Add to `src/models/suburb_metrics.py`
   - Example: Add `walkability_score: Optional[float]` to `Infrastructure` model

2. **Research Prompt**: Update prompt in `src/research/suburb_research.py::research_suburb()`
   - Include: `"walkability_score": ...` in returned JSON structure

3. **Template**: Reference in `src/ui/web/templates/suburb_report.html`
   - Add: `<p>Walkability: {{ metrics.infrastructure.walkability_score }}/10</p>`

4. **Tests**: Add test in `tests/test_research_suburb.py`

## Special Directories

**runs/** (Output):
- Purpose: Store timestamped research run results
- Generated: At runtime by `generate_all_reports()`
- Committed: No (add to `.gitignore`)
- Cleanup: Manual deletion of old runs or via `--clear-runs` script (not yet implemented)

**cache/** (Cache):
- Purpose: Store API responses to reduce costs
- Generated: At runtime by `ResearchCache.store()`
- Committed: No (add to `.gitignore`)
- Cleanup: Via CLI flag `python -m src.app --clear-cache`

**.planning/codebase/** (GSD Docs):
- Purpose: Architecture and design documentation for GSD orchestrator
- Generated: By GSD `/gsd:map-codebase` command
- Committed: Yes (these docs help future phases)
- Files:
  - `ARCHITECTURE.md`: Layers, data flow, abstractions
  - `STRUCTURE.md`: Directory layout, file locations, naming
  - `CONVENTIONS.md`: Code style, patterns (if quality focus)
  - `TESTING.md`: Test patterns, coverage (if quality focus)
  - `STACK.md`: Technology versions (if tech focus)
  - `INTEGRATIONS.md`: External APIs (if tech focus)
  - `CONCERNS.md`: Technical debt, issues (if concerns focus)
