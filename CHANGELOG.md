# Changelog

All notable changes to the Australian Property Research project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- No additional features planned at this time

## [1.7.1] - 2026-02-14

### Fixed
- **PDF Unicode Crash**: Fixed `fpdf2` crash when API-generated text contains Unicode characters (en-dash, em-dash, smart quotes, etc.) outside Helvetica's Latin-1 range
  - Added `_sanitize()` function that replaces 9 common Unicode characters with ASCII equivalents
  - Overrode `cell()` and `multi_cell()` in `PropertyReportPDF` subclass as a catch-all — all text is sanitized before reaching `fpdf2`, regardless of which data field it comes from
  - Characters handled: en-dash (U+2013), em-dash (U+2014), smart single/double quotes (U+2018/19/1C/1D), ellipsis (U+2026), bullet (U+2022), non-breaking space (U+00A0)

### Added
- **PDF Unicode Regression Tests**: 3 new test functions in `tests/test_exports.py`
  - `test_pdf_sanitize_function`: Unit tests for `_sanitize()` covering all 9 character replacements, ASCII passthrough, and mixed strings
  - `test_pdf_cell_override_sanitizes`: Verifies `cell()` and `multi_cell()` overrides sanitize positional and keyword text arguments
  - `test_pdf_realworld_unicode_data`: End-to-end PDF generation with Unicode patterns from actual API data (en-dashes in infrastructure, smart quotes in risk analysis)
- Strengthened existing `test_security_unicode_handling` to strictly assert PDF success (previously tolerated failures)

### Changed
- `src/reporting/pdf_exporter.py`: Added `_sanitize()` and `PropertyReportPDF.cell()`/`multi_cell()` overrides

## [1.7.0] - 2026-02-13

### Added
- **Parallel Discovery**: Multi-region suburb discovery runs concurrently instead of sequentially
  - `parallel_discover_suburbs()` splits multi-region and "All Australia" queries into per-region parallel calls using `ThreadPoolExecutor`
  - Single-region requests delegate directly to `discover_suburbs()` with no threading overhead
  - Results merged and deduplicated by `(name, state)` across regions
  - `AccountErrorSignal` class provides thread-safe propagation of auth/rate-limit errors across workers
  - Partial results preserved: if some regions fail, successful regions still contribute candidates
- **Parallel Research**: Per-suburb detailed research runs concurrently
  - `parallel_research_suburbs()` researches multiple suburbs in parallel using `ThreadPoolExecutor`
  - Order-preserving: results returned in original candidate order
  - Account-level errors (auth/rate-limit) stop all workers but return partial results (not raised)
  - Transient failures use fallback metrics — no slots lost
- **Thread-Safe Cache**: `ResearchCache` now uses `threading.RLock` for concurrent access safety
  - All public methods (`get`, `put`, `invalidate`, `clear`, `stats`) wrapped with reentrant lock
- **Parallel Execution Settings**: 4 new environment-configurable settings
  - `DISCOVERY_MAX_WORKERS` (default: 4) — max parallel region discovery workers
  - `RESEARCH_MAX_WORKERS` (default: 3) — max parallel suburb research workers
  - `DISCOVERY_TIMEOUT` (default: 120s) — timeout per region discovery call
  - `RESEARCH_TIMEOUT` (default: 240s) — timeout per suburb research call
- **Unit Tests**: 14 new parallel pipeline tests (`tests/test_parallel.py`)
  - AccountErrorSignal (3): initial state, set works, first-error-wins
  - Parallel discovery (5): single-region delegation, multi-region merge, deduplication, All Australia split, partial failure
  - Parallel research (4): all succeed, order preserved, transient fallback, account error partial results
  - Cache thread safety (2): concurrent writes, concurrent read+write

### Changed
- `src/research/suburb_discovery.py`: Added `AccountErrorSignal`, `_discover_for_single_region()`, `parallel_discover_suburbs()`; timeout now uses `settings.DISCOVERY_TIMEOUT`
- `src/research/suburb_research.py`: Added `parallel_research_suburbs()`; timeout now uses `settings.RESEARCH_TIMEOUT`
- `src/research/cache.py`: Added `threading.RLock` for thread safety
- `src/config/settings.py`: Added 4 parallel execution settings
- `src/app.py`: Wired up `parallel_discover_suburbs()` and `parallel_research_suburbs()` in pipeline

## [1.6.0] - 2026-02-13

### Added
- **Cache Management on Home Page**: Cache stats and clear button on the web UI landing page
  - Displays discovery cache count, research cache count, and total entries
  - "Clear Cache" button calls `POST /cache/clear` with visual feedback
  - Stats auto-load on page load via `GET /cache/stats`
  - Button auto-disables when cache is empty
- **Unit Tests**: 18 new cache resilience and UI tests (`test_cache_resilience.py`)
  - `_coerce_to_str_list` tests (6): string pass-through, dict coercion, mixed types, empty list, empty values, complex transport dicts
  - `_parse_metrics_from_json` tests (6): minimal valid data, bad market_history, bad demographics, infrastructure with dicts, bad growth projections, all sections bad
  - Cached data path tests (2): invalid cache triggers re-fetch, valid cache skips API
  - Web UI structural tests (4): cache section presence, stats display, server endpoints, try/except in cached path

### Fixed
- **Cached Data Resilience**: Invalid cached research data no longer crashes the pipeline
  - Wrapped cached code path in try/except — if `_parse_metrics_from_json` fails on cached data, the invalid entry is automatically invalidated and the suburb is re-fetched from the API
  - Previously, corrupted or incompatible cached data (e.g. dicts where strings were expected) would raise an unhandled exception

### Changed
- `src/research/suburb_research.py`: Cached data path now wrapped in try/except with `cache.invalidate()` fallback
- `src/ui/web/templates/web_index.html`: Added cache management card with stats grid and clear button
- Updated footer version to 1.6.0

## [1.5.0] - 2026-02-13

### Changed
- **Test Organization**: Moved all test files from project root into `tests/` directory
  - Moved 9 test files: `test_cache.py`, `test_charts.py`, `test_comparison.py`, `test_discovery.py`, `test_exports.py`, `test_models.py`, `test_perplexity.py`, `test_pipeline.py`, `test_research_ranking.py`
  - Updated `sys.path.insert` in all test files to use `parent.parent / "src"` for correct module resolution
  - Updated hardcoded source paths in `test_pipeline.py` structural tests
- **API Response Resilience**: Improved parsing of LLM API responses in `suburb_research.py`
  - Added `_coerce_to_str_list()` helper to convert mixed-type lists (dicts, strings) returned by AI providers into `list[str]`
  - Rewrote `_parse_metrics_from_json()` with section-isolated parsing — each section (market_history, physical_config, demographics, infrastructure, growth_projections) is parsed independently so one bad section doesn't lose all other researched data
  - Infrastructure list fields (`current_transport`, `future_transport`, `current_infrastructure`, `planned_infrastructure`) are now coerced before Pydantic validation
  - Only `identification` and `market_current` sections are required; all others fall back to empty defaults on parse failure

### Fixed
- Fixed Pydantic validation errors when API returns dicts instead of strings for infrastructure fields (e.g. `{'mode': 'bus', 'name': 'Route 520'}` instead of `"Route 520 (bus)"`)
- Fixed overview report CSS not loading (added `css_base: '.'` to overview report template context)

## [1.4.0] - 2026-02-13

### Added
- **Pipeline Resilience**: Batch research now survives transient API errors instead of stopping the entire run
  - Split `API_FATAL_ERRORS` into `API_ACCOUNT_ERRORS` (auth/rate-limit — stops batch) and `API_TRANSIENT_ERRORS` (general API errors — skips suburb, uses fallback metrics, continues)
  - `_create_fallback_metrics()` generates placeholder SuburbMetrics for suburbs that fail research, preserving growth signals from discovery
  - Generic exceptions (JSON parse errors, etc.) also use fallback and continue
  - Increased discovery multiplier from 3x to 5x and research multiplier from 2x to 3x to ensure enough candidates survive filtering
  - Price filter logging: shows when and how many candidates are removed by price filtering
- **Progress Visibility**: Real-time step-by-step progress in web UI during research runs
  - `progress_callback: Optional[Callable[[str], None]]` parameter threaded through `run_research_pipeline()` and `batch_research_suburbs()`
  - `_progress()` helper in pipeline that both prints to stdout and calls the callback
  - Web server creates callback that appends `{"message", "timestamp"}` dicts to `active_runs[run_id]["steps"]`
  - Status page renders progress steps with checkmarks, messages, and timestamps
  - Steps auto-scroll to latest entry on each 5-second poll cycle
  - Progress messages at all key stages: discovery, per-suburb research, ranking, report generation
- **Unit Tests**: 22 new pipeline tests (`test_pipeline.py`)
  - Error type splitting (3 tests)
  - Batch resilience (7 tests: transient continue, account stop, generic continue, all transient, max_suburbs)
  - Progress callback (4 tests: per-suburb calls, transient error reporting, account error reporting, no-callback compatibility)
  - Fallback metrics (2 tests: correct creation, growth signal preservation)
  - Structural tests (6 tests: pipeline helper, discovery logging, server steps init, server callback, multipliers)

### Changed
- `src/research/suburb_research.py`: Split error handling; `batch_research_suburbs` now accepts `progress_callback` parameter
- `src/research/suburb_discovery.py`: Added price filter count logging in both cached and fresh API paths
- `src/app.py`: Added `progress_callback` parameter to `run_research_pipeline()`, `_progress()` helper, increased multipliers
- `src/ui/web/server.py`: Steps list initialization in active runs, progress callback creation in background task
- `src/ui/web/templates/run_status.html`: Progress steps display section with auto-updating JavaScript

### Dependencies
- Added `python-multipart>=0.0.6` (required by FastAPI for form data handling)

## [1.3.0] - 2026-02-13

### Added
- **Historical Data Caching** (`src/research/cache.py`): File-based JSON cache to avoid redundant API calls
  - Discovery cache keyed by `(price_bucket, dwelling_type, sorted_regions)` with configurable TTL (default 24 hours)
  - Per-suburb research cache keyed by `(suburb_name, state, dwelling_type)` with configurable TTL (default 7 days)
  - Price bucketing to nearest $50k for improved cache hit rates
  - SHA256-based deterministic cache keys with JSON data files
  - `cache_index.json` metadata tracking with automatic corrupt-index recovery
  - Singleton `get_cache()` factory with `CacheConfig` dataclass
  - Transparent integration: callers (app.py, server.py) unchanged; cache checks wrap API calls in discovery/research modules
  - Logs cache HIT/MISS at info level for observability
- **Cache Controls**:
  - CLI: `--clear-cache` flag to clear cache, display stats, and exit
  - Web UI: `GET /cache/stats` and `POST /cache/clear` API endpoints
  - Interactive CLI: cache stats displayed at startup when entries exist
  - Health endpoint (`GET /health`) now includes `cache_entries` count
- **Cache Configuration** via environment variables:
  - `CACHE_ENABLED` (default: true) — enable/disable caching
  - `CACHE_DISCOVERY_TTL` (default: 86400) — discovery cache TTL in seconds
  - `CACHE_RESEARCH_TTL` (default: 604800) — research cache TTL in seconds
- **Run Comparison Mode** (`src/research/comparison.py`): Compare 2-3 past research runs side-by-side
  - Overlap detection by normalized `(name.lower(), state.lower())` matching
  - Per-suburb metric deltas: median price, growth score, composite score, 5-year projected growth
  - Unique suburbs per run identification
  - Run configuration comparison (provider, dwelling type, max price, regions, suburb count)
  - Loads past runs via existing `reconstruct_run_result()` infrastructure
- **Comparison Data Models** (`src/models/comparison.py`):
  - `RunSummary`, `SuburbRunMetrics`, `SuburbDelta`, `ComparisonResult` Pydantic models
  - `price_delta` and `score_delta` computed properties on `SuburbDelta`
- **Comparison Report Renderer** (`src/reporting/comparison_renderer.py`):
  - Generates standalone comparison HTML reports via Jinja2
  - Output to `runs/compare_{timestamp}/index.html`
- **Comparison UI**:
  - Web: `GET /compare` run selection page with checkbox validation (2-3 runs)
  - Web: `POST /compare` generates comparison and redirects to report
  - Web: `GET /compare/{compare_id}` serves comparison report
  - Web: "Compare Runs" button on runs list page
  - CLI: `--compare RUN_ID [RUN_ID ...]` flag for command-line comparison
- **Comparison Templates**:
  - `compare_select.html` — run selection with JavaScript validation
  - `compare_report.html` — self-contained comparison report with summary stats, config table, overlapping suburbs, unique suburbs
- **Unit Tests**: 66 tests
  - `test_cache.py`: 41 tests covering key generation, price bucketing, put/get, TTL, invalidation, clear, stats, edge cases, integration
  - `test_comparison.py`: 25 tests covering models, run summary computation, overlap detection, filesystem reconstruction, rendering

### Changed
- `src/research/suburb_discovery.py`: Checks cache before API call; caches discovery results after successful parse
- `src/research/suburb_research.py`: Checks cache before API call; caches per-suburb research results after successful parse
- `src/ui/web/server.py`: Added comparison endpoints, cache endpoints, helper `_get_completed_runs()` (excludes compare_ dirs)
- `src/ui/web/templates/runs_list.html`: Added "Compare Runs" button
- `src/app.py`: Added `--clear-cache` and `--compare` CLI flags
- `src/ui/cli/interactive.py`: Shows cache stats at startup
- `.gitignore`: Added `cache/` directory

## [1.2.0] - 2026-02-13

### Added
- **PDF Export**: Generate styled PDF reports from any completed research run
  - Title page with run configuration
  - Overview rankings table with all suburbs
  - Embedded overview and per-suburb chart PNGs
  - Per-suburb sections with growth projections, market metrics, infrastructure, and risk analysis
  - Custom header/footer with run ID and page numbers
  - Implemented with `fpdf2` (pure Python, no system dependencies)
- **Excel Export**: Generate multi-sheet `.xlsx` workbooks with structured data
  - 7 sheets: Overview, Market Metrics, Growth Projections, Property Config, Demographics, Infrastructure, Price History
  - Styled headers, currency/percentage formatting, auto-column-widths
  - Confidence intervals for 1/5/10-year projections
  - Wide-format price history with year columns
  - Implemented with `openpyxl`
- **Run Metadata Persistence**: `run_metadata.json` saved alongside HTML reports, enabling exports on past runs
- **Web UI Export**: PDF and Excel download buttons on run status page and runs list
  - `GET /export/{run_id}/{format}` endpoint with caching (generates once, serves cached)
- **Interactive CLI Export**: Post-completion prompts to generate PDF and Excel reports with spinner feedback
- **Basic CLI Export Flags**: `--export-pdf` and `--export-xlsx` flags for automated export generation
- **Export Orchestration Layer** (`src/reporting/exports.py`):
  - `generate_pdf_export()` and `generate_excel_export()` public API
  - `reconstruct_run_result()` for rebuilding RunResult from metadata files
  - `ExportError` exception class for export-specific error handling

### Dependencies
- Added `fpdf2>=2.7.0` (PDF generation)
- Added `openpyxl>=3.1.0` (Excel generation)

## [1.1.0] - 2026-02-13

### Added
- **Dual AI Provider Support**: Toggle between Perplexity and Anthropic Claude as research providers
  - New `AnthropicClient` (`src/research/anthropic_client.py`) with matching interface to `PerplexityClient`
  - Anthropic Claude uses `claude-sonnet-4-5-20250929` model for research
  - Provider auto-detection based on configured API keys in `.env`
  - Provider selector in all interfaces (web, interactive CLI, basic CLI)
- **Provider Selection UI**:
  - Web interface: dropdown with provider descriptions (only shown when both keys configured)
  - Interactive CLI: numbered table selection with provider info
  - Basic CLI: `--provider` flag (`perplexity` or `anthropic`)
- **Dynamic Configuration**:
  - `AVAILABLE_PROVIDERS` list auto-populated from set API keys
  - `DEFAULT_PROVIDER` defaults to first available (prefers Perplexity)
  - At least one API key required (was previously Perplexity-only)
- **Anthropic-specific error handling**: `AnthropicAPIError`, `AnthropicRateLimitError`, `AnthropicAuthError`
- **Combined error handling** across both providers in pipeline, web server, and research modules

### Changed
- `settings.py`: API keys are now individually optional (at least one required)
- `UserInput` model: added `provider` field and `get_provider_display()` method
- `get_client()` factory function now accepts `provider` parameter and caches clients per-provider
- `suburb_discovery.py` and `suburb_research.py`: route to correct provider client
- Web server passes provider list and default to templates
- Interactive CLI dynamically adjusts step numbering based on provider availability

## [1.0.0] - 2026-02-10

### Added
- FastAPI web interface with browser UI
- Interactive CLI with prompt_toolkit and rich formatting
- Quick mode for interactive CLI

## [0.1.0] - 2026-02-01

### Added
- Initial release of Australian Property Research application
- **Core Features**:
  - Perplexity deep research integration with Claude Sonnet 4.5
  - Australia-wide suburb discovery and filtering
  - Multi-region support (23 predefined regions)
  - Comprehensive data collection (60+ fields per suburb)
  - Growth projections for 1, 2, 3, 5, 10, and 25-year horizons
  - Confidence intervals and risk analysis

- **Research Pipeline**:
  - Suburb discovery with price/type filtering
  - Batch research with parallel processing support
  - Intelligent ranking (growth_score, composite_score, 5yr_growth methods)
  - Retry logic with exponential backoff for API calls

- **Reporting System**:
  - Professional HTML reports with Jinja2 templates
  - Responsive CSS design for mobile/desktop
  - 9 chart types using matplotlib and seaborn:
    - Price history charts
    - Growth projection charts
    - Days on market trends
    - Comparison charts (overview)
    - Risk vs growth scatter plots
  - Overview dashboard with rankings table
  - Detailed suburb-level reports

- **CLI Interface**:
  - Command-line argument parsing with argparse
  - Support for multiple regions selection
  - Configurable number of suburbs
  - Custom run IDs
  - Warning system for large runs (>25 suburbs)

- **Configuration**:
  - Environment-based configuration (.env)
  - 23 predefined Australian regions
  - Configurable timeouts and retry behavior
  - Output directory management

- **Data Models**:
  - Comprehensive Pydantic models with validation
  - SuburbMetrics with 8 nested models
  - UserInput with multi-region support
  - RunResult with status tracking
  - SuburbReport with ranking information

- **Documentation**:
  - Comprehensive README.md
  - CLAUDE.md project specification
  - Code documentation and docstrings
  - .env.example template

- **Testing**:
  - Unit tests for data models
  - Integration tests for Perplexity API
  - Live API validation tests
  - Chart generation tests

### Technical Details

**Dependencies**:
- Python 3.10+
- perplexityai SDK
- pydantic ^2.0
- jinja2
- matplotlib
- seaborn
- python-dotenv

**Architecture**:
- Modular design with separation of concerns
- Config layer for settings management
- Research layer for API integration
- Reporting layer for visualization
- Models layer for data validation

### Known Issues
- Template rendering requires numeric checks for household_types data (fixed in v0.1.0)
- Long-running deep research queries (expected behavior, 2-5 min per suburb)
- No caching mechanism for repeated queries

### Performance
- Suburb discovery: ~30-120 seconds (depending on region size)
- Per-suburb research: ~2-5 minutes (Perplexity deep research)
- Chart generation: ~1-3 seconds per chart
- Report rendering: ~1-2 seconds per report

### Security
- API keys managed via environment variables
- No hardcoded credentials
- .gitignore configured to exclude secrets
- Input validation via Pydantic models

---

## Version History Summary

- **v1.7.0** (2026-02-13): Parallel discovery + parallel research pipeline
- **v1.6.0** (2026-02-13): Cache resilience + home page cache management
- **v1.5.0** (2026-02-13): Test organization, API response resilience, CSS fix
- **v1.4.0** (2026-02-13): Pipeline resilience + real-time progress visibility
- **v1.3.0** (2026-02-13): Historical data caching + run comparison mode
- **v1.2.0** (2026-02-13): PDF and Excel export functionality
- **v1.1.0** (2026-02-13): Dual AI provider support (Perplexity + Anthropic Claude)
- **v1.0.0** (2026-02-10): Web interface + interactive CLI
- **v0.1.0** (2026-02-01): Initial release with core functionality

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to this project.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.
