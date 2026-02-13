# Agentic Australian Property Researcher 🏘️

[![Version](https://img.shields.io/badge/version-1.5.0-blue.svg)](https://github.com/yourusername/agentic-re-researcher)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Author:** Dr. Robert Li

**Version:** 1.5.0

---

AI-powered property investment researcher that generates comprehensive suburb-level analysis reports for Australian real estate markets. Supports dual AI providers: **Perplexity** (deep research with live web search) and **Anthropic Claude** (claude-sonnet-4-5), with the ability to toggle between them when both API keys are configured.

## ⚠️ Important Warnings

### API Usage and Costs
- **This application consumes significant API credits**: Each suburb research uses deep-research API calls (Perplexity or Anthropic), which are resource-intensive
- **Token consumption**: A typical run analyzing 5-10 suburbs can consume tens of thousands of API tokens
- **Processing time**: Research takes 2-5 minutes per suburb; a 10-suburb analysis can take 20-50 minutes
- **Rate limiting**: Both Perplexity and Anthropic APIs have rate limits; large runs may encounter delays or failures

### Recommendations
- Start with small runs (2-3 suburbs) to test
- Monitor your API credit balance (Perplexity and/or Anthropic)
- Use the quick demo (`python demo.py`) for initial testing
- Consider API costs before running large analyses (>10 suburbs)

### Disclaimer
**THE CREATOR OF THIS PROJECT ASSUMES NO RESPONSIBILITY FOR:**
- API credit consumption or costs incurred
- Processing time or resource usage
- Investment decisions made based on generated reports
- Accuracy of data or projections
- Any financial losses or damages

**This tool is for research purposes only and does not constitute financial advice.**

## Features

- **Australia-Wide Coverage**: Research suburbs across all Australian states and territories
- **Multi-Region Filtering**: Target specific regions (e.g., South East Queensland, Northern NSW) or entire states
- **Dual AI Provider Support**: Toggle between Perplexity (deep research + live web search) and Anthropic Claude (claude-sonnet-4-5)
- **Deep Research**: Powered by Perplexity's agentic research or Anthropic Claude's reasoning capabilities
- **Comprehensive Data Collection**:
  - Current & historical market metrics (prices, DOM, clearance rates, turnover)
  - Demographics and population trends
  - Infrastructure (current & planned, including Brisbane 2032 Olympics)
  - Transport networks (existing & future)
  - Schools, crime statistics, shopping access
  - Property configurations (land size, bedrooms, bathrooms)
- **Growth Projections**: 1, 2, 3, 5, 10, and 25-year price growth forecasts with confidence intervals
- **Intelligent Ranking**: Ranks suburbs by composite score (growth potential adjusted for risk)
- **Professional Reports**:
  - Interactive HTML reports with responsive design
  - Comparison charts and visualizations (matplotlib/seaborn)
  - Overview dashboard with rankings
  - Detailed suburb-level reports
- **Export Options**:
  - PDF export with styled layout, rankings table, per-suburb sections, and embedded charts
  - Excel export with 7 structured sheets (overview, market metrics, growth projections, property config, demographics, infrastructure, price history)
  - On-demand export from web UI, interactive CLI, or CLI flags
  - Cached exports for instant re-download
- **Historical Data Caching**:
  - File-based JSON cache reduces redundant API calls and speeds up repeated research
  - Discovery cache (24-hour TTL) keyed by price bucket, dwelling type, and regions
  - Per-suburb research cache (7-day TTL) keyed by suburb, state, and dwelling type
  - Price bucketing (nearest $50k) for better cache hit rates
  - Cache statistics, clear controls via web UI, CLI, and API endpoints
  - Configurable via environment variables (`CACHE_ENABLED`, `CACHE_DISCOVERY_TTL`, `CACHE_RESEARCH_TTL`)
- **Run Comparison Mode**:
  - Compare 2-3 past research runs side-by-side
  - Identifies overlapping suburbs across runs with metric deltas (price, score, growth)
  - Lists unique suburbs per run
  - Run configuration comparison table
  - Available from web UI (runs list + dedicated comparison page) and CLI (`--compare` flag)
  - Generates standalone comparison HTML reports
- **Pipeline Resilience**:
  - Transient API errors (timeouts, server errors) skip the suburb and continue with remaining suburbs using fallback metrics
  - Only account-level errors (auth failures, rate limits) stop the batch
  - Increased discovery multiplier (5x) and research multiplier (3x) to ensure enough candidates survive filtering
- **Progress Visibility**:
  - Web UI displays real-time step-by-step progress during research runs
  - Progress steps include suburb discovery, per-suburb research status, ranking, and report generation
  - Steps auto-update via polling with timestamps
- **Triple Interface**: Three ways to use the application
  - Basic command-line interface (argparse)
  - Interactive CLI with autocomplete and validation (prompt_toolkit + rich)
  - Web interface with real-time status updates (FastAPI)

## Installation

### Prerequisites

- Python 3.10 or higher
- At least one of the following API keys:
  - Perplexity API key ([Get one here](https://www.perplexity.ai/))
  - Anthropic API key ([Get one here](https://console.anthropic.com/))

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd agentic-re-researcher
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your API key(s). At least one is required:
   ```
   # Perplexity API (enables deep research with live web search)
   PERPLEXITY_API_KEY=pplx-your-api-key-here

   # Anthropic API (enables Claude claude-sonnet-4-5 provider)
   ANTHROPIC_API_KEY=sk-ant-your-api-key-here
   ```

   If both keys are provided, you can toggle between providers in the UI or via `--provider` flag.

## Usage

### Quick Demo

Run a quick test with 2 suburbs in South East Queensland:

```bash
python demo.py
```

### Web Interface (Recommended)

The easiest way to use the application is through the web interface:

```bash
python run_web.py
```

This will:
- Start a FastAPI server on http://127.0.0.1:8000
- Automatically open your browser
- Provide a beautiful form interface with:
  - Price input with validation
  - Dwelling type selection
  - Multi-select regions (with "Select All" option)
  - Number of suburbs input
  - Real-time status updates during processing
  - Browse past reports
  - Responsive design for mobile/tablet

The web interface runs research jobs in the background and polls status every 5 seconds, so you can monitor progress without blocking.

### Interactive CLI

For a guided terminal experience with autocomplete and validation:

```bash
python run_interactive.py
```

Features:
- Step-by-step prompts with default values
- Region selection via numbered table
- Autocomplete for dwelling types
- Input validation with helpful error messages
- Rich terminal formatting with progress indicators
- Option to open report in browser when complete

**Quick mode** (minimal prompts):
```bash
python run_interactive.py --quick
```

### Command-Line Interface (Basic)

Basic usage with required parameters:

```bash
python -m src.app \
  --max-price 650000 \
  --dwelling-type house \
  --num-suburbs 5
```

#### CLI Parameters

- `--max-price`: Maximum median price threshold (AUD) **[required]**
- `--dwelling-type`: Type of dwelling (`house`, `apartment`, `townhouse`) **[required]**
- `--regions`: Region(s) to search (default: "South East Queensland")
- `--num-suburbs`: Number of top suburbs to include in report (default: 5)
- `--provider`: AI research provider (`perplexity` or `anthropic`; only available providers shown)
- `--run-id`: Custom run ID (default: auto-generated timestamp)
- `--export-pdf`: Automatically generate PDF report after completion
- `--export-xlsx`: Automatically generate Excel report after completion
- `--clear-cache`: Clear the research cache and display statistics, then exit
- `--compare RUN_ID [RUN_ID ...]`: Compare 2-3 past runs side-by-side and generate a comparison report

#### Examples

**Search South East Queensland for affordable houses**:
```bash
python -m src.app \
  --max-price 700000 \
  --dwelling-type house \
  --regions "South East Queensland" \
  --num-suburbs 10
```

**Use Anthropic Claude as provider**:
```bash
python -m src.app \
  --max-price 700000 \
  --dwelling-type house \
  --provider anthropic
```

**Multiple regions**:
```bash
python -m src.app \
  --max-price 800000 \
  --dwelling-type apartment \
  --regions "South East Queensland" "Northern NSW" \
  --num-suburbs 8
```

**Entire state search**:
```bash
python -m src.app \
  --max-price 600000 \
  --dwelling-type house \
  --regions "Queensland" \
  --num-suburbs 15
```

**With PDF and Excel export**:
```bash
python -m src.app \
  --max-price 700000 \
  --dwelling-type house \
  --export-pdf --export-xlsx
```

**Clear research cache**:
```bash
python -m src.app --clear-cache
```

**Compare past runs**:
```bash
python -m src.app --compare 2026-02-10_14-30-00 2026-02-12_09-15-00
```

**All of Australia** (warning: slow and expensive):
```bash
python -m src.app \
  --max-price 650000 \
  --dwelling-type house \
  --regions "All Australia" \
  --num-suburbs 20
```

### Available Regions

The application supports 23 predefined Australian regions:

**National**:
- All Australia

**Queensland**:
- South East Queensland
- North Queensland
- Central Queensland
- Queensland (entire state)

**New South Wales**:
- Northern NSW
- Greater Sydney
- Central Coast NSW
- Southern NSW
- New South Wales (entire state)

**Victoria**:
- Greater Melbourne
- Regional Victoria
- Victoria (entire state)

**Other States**:
- South Australia
- Western Australia
- Tasmania
- Australian Capital Territory
- Northern Territory

## Output Structure

Each research run creates a timestamped directory in `runs/`:

```
runs/
└── 2026-02-01_10-30-15/
    ├── index.html              # Overview report with rankings
    ├── suburbs/                # Individual suburb reports
    │   ├── suburb-name-1.html
    │   ├── suburb-name-2.html
    │   └── ...
    ├── charts/                 # Generated visualizations
    │   ├── overview_growth_score.png
    │   ├── overview_composite_score.png
    │   ├── overview_5yr_growth.png
    │   ├── price_history_suburb-1.png
    │   ├── growth_projection_suburb-1.png
    │   └── ...
    ├── static/                 # CSS and assets
    │   └── css/
    │       └── styles.css
    ├── run_metadata.json       # Run metadata for export reconstruction
    ├── report_*.pdf            # PDF export (generated on demand)
    └── report_*.xlsx           # Excel export (generated on demand)
```

### Viewing Reports

After a successful run, open the overview report in your browser:

```bash
# macOS
open runs/2026-02-01_10-30-15/index.html

# Linux
xdg-open runs/2026-02-01_10-30-15/index.html

# Windows
start runs/2026-02-01_10-30-15/index.html
```

## Report Contents

### Overview Report (`index.html`)
- Run configuration and parameters
- Price statistics (min, max, avg, median)
- Growth potential statistics
- Comparison charts
- Ranked suburbs table with links to detailed reports
- Methodology and disclaimer

### Suburb Reports (`suburbs/*.html`)
- **Investment Summary**: Key metrics at a glance
- **Growth Projections**: Detailed forecasts for multiple time horizons
- **Key Growth Drivers**: Factors supporting appreciation
- **Market Metrics**: Current and historical trends
- **Property Configuration**: Typical bedrooms, bathrooms, land size
- **Infrastructure**: Transport, schools, shopping, planned developments
- **Demographics**: Population trends, household types, age distribution
- **Risk Analysis**: Comprehensive risk assessment with scoring

## Configuration

### Environment Variables

Configure in `.env` file:

```bash
# Perplexity API Configuration (enables Perplexity provider)
PERPLEXITY_API_KEY=your-perplexity-api-key-here

# Anthropic API Configuration (enables Claude provider)
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# Optional Settings
OUTPUT_DIR=runs
DEFAULT_PORT=8080

# Cache Settings
CACHE_ENABLED=true              # Enable/disable research cache (default: true)
CACHE_DISCOVERY_TTL=86400       # Discovery cache TTL in seconds (default: 24 hours)
CACHE_RESEARCH_TTL=604800       # Research cache TTL in seconds (default: 7 days)
```

At least one API key is required. If both are provided, the provider toggle becomes available in all interfaces.

### Advanced Configuration

Edit `src/config/settings.py` for advanced settings:
- API timeouts and retry behavior
- Default model and preset per provider
- Output directory structure
- Chart styling and dimensions

## Performance Notes

- **API Costs**: Each suburb requires deep research API calls (~2-5 minutes per suburb)
- **Rate Limits**: Both Perplexity and Anthropic APIs have rate limits that may affect large runs
- **Provider Differences**:
  - **Perplexity**: Uses live web search for current data; generally more up-to-date market information
  - **Anthropic Claude**: Uses training data only (no live web search); faster responses but data may be less current
- **Recommended**: Start with 3-5 suburbs for testing
- **Warning**: Runs with >25 suburbs will prompt for confirmation due to cost/time

## Architecture

```
src/
├── config/              # Settings and region definitions
├── models/              # Pydantic data models
├── research/            # AI provider integration and analysis
├── reporting/           # Chart generation and HTML rendering
└── ui/                  # User interfaces (web + CLI)
    ├── web/
    │   ├── templates/   # Jinja2 HTML templates
    │   └── static/      # CSS, JS, images
    └── cli/             # Interactive CLI interface
```

### Key Components

1. **Perplexity Client** (`research/perplexity_client.py`): Perplexity API wrapper with retry logic and client factory
2. **Anthropic Client** (`research/anthropic_client.py`): Anthropic Claude API wrapper with matching interface
3. **Suburb Discovery** (`research/suburb_discovery.py`): Finds qualifying suburbs via selected provider
4. **Suburb Research** (`research/suburb_research.py`): Deep research per suburb with provider routing
5. **Ranking Engine** (`research/ranking.py`): Scores and ranks suburbs
6. **Chart Generator** (`reporting/charts.py`): Creates visualizations
7. **HTML Renderer** (`reporting/html_renderer.py`): Generates reports
8. **PDF Exporter** (`reporting/pdf_exporter.py`): Generates styled PDF reports via fpdf2
9. **Excel Exporter** (`reporting/excel_exporter.py`): Generates multi-sheet Excel workbooks via openpyxl
10. **Export Orchestrator** (`reporting/exports.py`): Coordinates export generation and metadata reconstruction
11. **Research Cache** (`research/cache.py`): File-based JSON cache with TTL for discovery and per-suburb results
12. **Run Comparison** (`research/comparison.py`): Side-by-side comparison of 2-3 past runs with overlap detection
13. **Comparison Renderer** (`reporting/comparison_renderer.py`): Generates comparison HTML reports

## Data Models

The application uses comprehensive Pydantic models with 60+ fields covering:
- Identification (name, state, LGA, region)
- Market metrics (current & historical)
- Physical configuration
- Demographics
- Infrastructure
- Growth projections with confidence intervals

See `src/models/suburb_metrics.py` for complete schema.

## Development

### Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all test suites (88+ tests)
python tests/test_cache.py && python tests/test_comparison.py && python tests/test_pipeline.py

# Run specific test suite
python tests/test_pipeline.py          # Pipeline resilience & progress (22 tests)
python tests/test_cache.py             # Research cache (41 tests)
python tests/test_comparison.py        # Run comparison (25 tests)
python tests/test_models.py            # Config & data models
python tests/test_research_ranking.py  # Ranking logic
python tests/test_exports.py           # PDF & Excel exports (77 tests)
```

### Code Quality

```bash
# Type checking
mypy src/

# Linting
pylint src/

# Formatting
black src/
```

## Troubleshooting

### Common Issues

**No API Key Found**:
```
Error: At least one API key required
```
Solution: Ensure `.env` file exists with at least one valid API key (`PERPLEXITY_API_KEY` or `ANTHROPIC_API_KEY`).

**Module Not Found**:
```
ModuleNotFoundError: No module named 'pydantic'
```
Solution: Activate virtual environment and install dependencies:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**Timeout Errors**:
Increase timeout in `.env`:
```
REQUEST_TIMEOUT=300
```

**JSON Parsing Errors**:
The application has robust fallback mechanisms for API response parsing. If issues persist, check Perplexity API status.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## Roadmap

- [x] FastAPI web interface
- [x] Interactive CLI with prompt_toolkit
- [x] Dual AI provider support (Perplexity + Anthropic Claude)
- [x] Export to PDF/Excel
- [x] Historical data caching
- [x] Comparison mode for multiple runs
- [x] Pipeline resilience (graceful error handling)
- [x] Real-time progress visibility in web UI

## Acknowledgments

- **Perplexity AI**: Deep research API with live web search capabilities
- **Anthropic**: Claude Sonnet 4.5 for advanced reasoning (now a direct provider option)
- **Libraries**: Pydantic, Jinja2, Matplotlib, Seaborn, FastAPI, prompt_toolkit, rich, fpdf2, openpyxl

## Disclaimer

This tool is for informational and research purposes only. It does not constitute financial or investment advice. Property markets are subject to various risks and uncertainties. Always conduct your own due diligence and consult with qualified professionals before making investment decisions.
