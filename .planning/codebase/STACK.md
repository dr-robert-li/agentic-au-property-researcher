# Technology Stack

**Analysis Date:** 2026-02-15

## Languages

**Primary:**
- Python 3.14.2 - Core application language, used throughout backend, CLI, and all processing logic

## Runtime

**Environment:**
- Python 3.14+ with virtual environment (venv)

**Package Manager:**
- pip
- Lockfile: requirements.txt (present)

## Frameworks

**Core Web:**
- FastAPI 0.104.0+ - Web server and REST API for browser-based interface
- Uvicorn 0.24.0+ (with standard extras) - ASGI server for FastAPI

**Templating:**
- Jinja2 3.1.0+ - HTML template rendering for web UI and suburb reports

**CLI & Interaction:**
- click 8.1.0+ - Command-line interface and argument parsing
- prompt-toolkit 3.0.0+ - Interactive prompts, autocomplete, and enhanced CLI experience
- rich 13.0.0+ - Rich text formatting, progress bars, tables, and terminal output

**Data Processing:**
- pandas 2.0.0+ - Data manipulation and analysis (optional but present)
- pydantic 2.0.0+ - Data validation and serialization for input/output models

## Key Dependencies

**Critical:**
- perplexityai 0.1.0+ - Perplexity Agentic Research API client for suburb discovery and research
- anthropic 0.42.0+ - Anthropic Claude API client (fallback provider when Perplexity unavailable)

**Visualization & Reporting:**
- matplotlib 3.7.0+ - Chart generation for price history, growth projections, market trends
- seaborn 0.12.0+ - Statistical data visualization and styling for charts
- fpdf2 2.7.0+ - PDF report generation with multi-page layouts and embedded images
- openpyxl 3.1.0+ - Excel spreadsheet generation with formatting and multi-sheet support

**Utilities:**
- python-dotenv 1.0.0+ - Environment variable loading from .env files
- python-slugify 8.0.0+ - URL-safe slug generation for suburb names and file paths
- requests 2.31.0+ - HTTP client for web requests (underlying requests library)
- python-multipart 0.0.6+ - Multipart form data handling for FastAPI file uploads

## Configuration

**Environment:**
- Loaded via `python-dotenv` from `.env` file at application startup
- See `src/config/settings.py` for configuration loading and defaults

**Key Configuration Variables:**
- `PERPLEXITY_API_KEY` - Perplexity API authentication (required or ANTHROPIC_API_KEY)
- `ANTHROPIC_API_KEY` - Anthropic Claude API authentication (optional, for fallback)
- `DEFAULT_PORT` - Web server port (default: 8080)
- `OUTPUT_DIR` - Directory for report outputs (default: runs/)
- `DISCOVERY_MAX_WORKERS` - Max parallel region discovery workers (default: 4)
- `RESEARCH_MAX_WORKERS` - Max parallel suburb research workers (default: 3)
- `DISCOVERY_TIMEOUT` - Timeout per region discovery in seconds (default: 120)
- `RESEARCH_TIMEOUT` - Timeout per suburb research in seconds (default: 240)
- `CACHE_ENABLED` - Enable/disable result caching (default: true)
- `CACHE_DISCOVERY_TTL` - Cache time-to-live for discovery results (default: 86400 / 24 hours)
- `CACHE_RESEARCH_TTL` - Cache time-to-live for suburb research (default: 604800 / 7 days)

**Build:**
- `requirements.txt` - Pinned dependency versions
- No build configuration files (setup.py, pyproject.toml, Makefile) detected; uses pip directly

## Platform Requirements

**Development:**
- Python 3.14+
- pip package manager
- Virtual environment support
- macOS, Linux, or Windows (cross-platform compatible)

**Production:**
- Python 3.14+ runtime
- FastAPI/Uvicorn compatible system
- Sufficient disk space for output directory (`runs/`)
- Network access to Perplexity or Anthropic APIs
- Optional: PyInstaller compatible system for bundled executable

## Additional Components

**Data Persistence:**
- File-based JSON cache (`src/research/cache.py`) for discovery and research results
- Cache stored in `cache/` directory with metadata index (`cache_index.json`)
- No database system (SQLite, PostgreSQL, MongoDB) - all persistence is filesystem-based

**Entry Points:**
- `src/app.py` - Main orchestration entry point for research pipeline
- `src/ui/web/server.py` - FastAPI web server for browser interface
- `src/ui/cli/interactive.py` - CLI interface with interactive prompts
- `run_web.py` - Entry script for web mode (starts server on localhost:8080)
- `run_interactive.py` - Entry script for CLI mode

---

*Stack analysis: 2026-02-15*
