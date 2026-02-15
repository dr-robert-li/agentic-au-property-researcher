# External Integrations

**Analysis Date:** 2026-02-15

## APIs & External Services

**Research APIs (Dual Provider):**
- Perplexity Agentic Research API
  - Purpose: Primary provider for exhaustive suburb discovery and detailed research with deep-research preset
  - SDK/Client: `perplexityai` Python SDK (v0.1.0+)
  - Auth: `PERPLEXITY_API_KEY` environment variable
  - Usage: `src/research/perplexity_client.py` - PerplexityClient class wraps SDK with retry logic
  - Models Used: `anthropic/claude-sonnet-4-5` via Perplexity's deep-research preset
  - Tools: Web search and URL fetching
  - Error Handling: Custom exceptions (PerplexityRateLimitError, PerplexityAuthError, PerplexityAPIError)

- Anthropic Claude API
  - Purpose: Fallback provider for research when Perplexity unavailable, also used for narrative generation
  - SDK/Client: `anthropic` Python SDK (v0.42.0+)
  - Auth: `ANTHROPIC_API_KEY` environment variable (optional)
  - Usage: `src/research/anthropic_client.py` - AnthropicClient class with matching interface
  - Model: `claude-sonnet-4-5-20250929`
  - Error Handling: Custom exceptions (AnthropicRateLimitError, AnthropicAuthError, AnthropicAPIError)
  - Provider Selection: Automatic via `src/config/settings.py` - prefers Perplexity if both keys present

## Data Storage

**Databases:**
- None - Not used; application uses file-based storage only

**File Storage:**
- Local filesystem only
- Output directory: `runs/` (configurable via `OUTPUT_DIR` env var)
- Structure:
  - `runs/{TIMESTAMP}/` - Each run creates timestamped folder
  - `runs/{TIMESTAMP}/overview.html` - Main report with suburb rankings
  - `runs/{TIMESTAMP}/suburbs/` - Individual suburb HTML reports
  - `runs/{TIMESTAMP}/charts/` - Generated PNG/SVG chart images
  - `runs/{TIMESTAMP}/overview.pdf` - Optional PDF export
  - `runs/{TIMESTAMP}/comparison.xlsx` - Optional Excel export

**Caching:**
- Local file-based JSON cache (`cache/` directory)
- Module: `src/research/cache.py` - ResearchCache class
- Cache Index: `cache/cache_index.json` - Metadata tracking for cached results
- TTL Configuration:
  - Discovery results: 86400 seconds (24 hours) by default
  - Research results: 604800 seconds (7 days) by default
- Thread-safe with file locking

## Authentication & Identity

**Auth Provider:**
- None - Application uses API key authentication only
- No user authentication, login, or session management
- All authentication is API-level (Perplexity and Anthropic keys)

## Monitoring & Observability

**Error Tracking:**
- None detected - Errors logged to stdout/console
- Custom exception handling in API client wrappers with user-friendly error messages

**Logs:**
- Console stdout - All progress and status messages printed to console
- Optional callback-based progress reporting for web UI (`progress_callback` in `src/app.py`)
- No persistent log files; logging is in-memory during execution
- Rich formatted output via `rich` library for terminal output formatting

## CI/CD & Deployment

**Hosting:**
- Local development: localhost:8080 (FastAPI/Uvicorn)
- No cloud platform integration detected
- Can be packaged as executable via PyInstaller (v6.0.0+)

**CI Pipeline:**
- None detected - No GitHub Actions, GitLab CI, Jenkins, or other CI systems found

**Packaging:**
- PyInstaller 6.0.0+ - For creating standalone executables
- Entry points: `run_web.py` (web mode) and `run_interactive.py` (CLI mode)

## Environment Configuration

**Required env vars:**
- `PERPLEXITY_API_KEY` or `ANTHROPIC_API_KEY` (at least one must be set)
  - Checked at startup in `src/config/settings.py`
  - If both missing, application raises ValueError

**Optional env vars:**
- `ANTHROPIC_API_KEY` - Enables provider toggle if set alongside Perplexity key
- `DEFAULT_PORT` - Web server port (default: 8080)
- `OUTPUT_DIR` - Output directory for reports (default: runs/)
- `DISCOVERY_MAX_WORKERS` - Parallel discovery workers (default: 4)
- `RESEARCH_MAX_WORKERS` - Parallel research workers (default: 3)
- `DISCOVERY_TIMEOUT` - Discovery timeout in seconds (default: 120)
- `RESEARCH_TIMEOUT` - Research timeout in seconds (default: 240)
- `CACHE_ENABLED` - Enable caching (default: true)
- `CACHE_DISCOVERY_TTL` - Discovery cache TTL in seconds (default: 86400)
- `CACHE_RESEARCH_TTL` - Research cache TTL in seconds (default: 604800)

**Secrets location:**
- `.env` file (git-ignored, never committed)
- Template: `.env.example` shows structure
- Loaded at startup via `python-dotenv`

## Webhooks & Callbacks

**Incoming:**
- None - Application does not expose webhook endpoints

**Outgoing:**
- Progress callbacks: Optional `progress_callback` parameter in `src/app.py:run_research_pipeline()`
  - Used by web UI to display real-time progress updates
  - Called during discovery, research, and report generation phases
  - No external webhooks; internal callback mechanism only

## Request Patterns

**API Call Characteristics:**

**Discovery API Calls:**
- Endpoint: Perplexity `client.responses.create()` or Anthropic `client.messages.create()`
- Timeout: 120 seconds per region (configurable)
- Retry: Up to 3 attempts with exponential backoff (2-second delay between retries)
- Request: Deep-research prompt with region/state filters, price threshold, dwelling type
- Response: Structured JSON array with suburb candidates (name, state, LGA, median price, growth signals)

**Research API Calls:**
- Endpoint: Same as above
- Timeout: 240 seconds per suburb (configurable)
- Retry: Up to 3 attempts
- Request: Detailed suburb research prompt requesting structured JSON (metrics, history, demographics, infrastructure, projections)
- Response: Large JSON object with comprehensive suburb data (market history, growth projections, confidence intervals)

**Rate Limiting & Quotas:**
- Perplexity: API rate limit errors handled by PerplexityRateLimitError with user guidance
- Anthropic: Rate limit errors handled by AnthropicRateLimitError
- No built-in request queuing; errors surface to user with actionable messages
- Parallel execution (configurable workers) may trigger rate limits; adjust DISCOVERY_MAX_WORKERS and RESEARCH_MAX_WORKERS

## Data Flow & Processing

**Discovery Flow:**
1. User input validated in `src/models/inputs.py`
2. Multi-region discovery via `src/research/suburb_discovery.py:parallel_discover_suburbs()`
3. Parallel workers (default: 4) call Perplexity/Anthropic per region
4. Results cached in `cache/` directory (24-hour TTL)
5. Candidates filtered by price, dwelling type
6. Top N suburbs selected for detailed research

**Research Flow:**
1. Per-suburb detailed research via `src/research/suburb_research.py:parallel_research_suburbs()`
2. Parallel workers (default: 3) call API per suburb
3. JSON responses parsed into `SuburbMetrics` objects
4. Results cached (7-day TTL)
5. Growth projections extracted and normalized

**Reporting Flow:**
1. Suburbs ranked by growth score via `src/research/ranking.py`
2. Charts generated: `src/reporting/charts.py` - PNG images via matplotlib/seaborn
3. HTML reports rendered: `src/reporting/html_renderer.py` - Jinja2 templates
4. Optional exports:
   - PDF: `src/reporting/pdf_exporter.py` - fpdf2-based multi-page layouts
   - Excel: `src/reporting/excel_exporter.py` - openpyxl-based multi-sheet workbooks

---

*Integration audit: 2026-02-15*
