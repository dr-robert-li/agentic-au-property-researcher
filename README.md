# Agentic Australian Property Researcher 🏘️

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/yourusername/agentic-re-researcher)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Author:** Dr. Robert Li

**Version:** 1.0.0

---

AI-powered property investment researcher that generates comprehensive suburb-level analysis reports for Australian real estate markets. Uses Perplexity's deep research capabilities with Claude Sonnet 4.5 to analyze market trends, infrastructure development, demographics, and growth potential.

## ⚠️ Important Warnings

### API Usage and Costs
- **This application consumes significant API credits**: Each suburb research uses Perplexity's deep-research preset, which is resource-intensive
- **Token consumption**: A typical run analyzing 5-10 suburbs can consume tens of thousands of API tokens
- **Processing time**: Research takes 2-5 minutes per suburb; a 10-suburb analysis can take 20-50 minutes
- **Rate limiting**: Perplexity API has rate limits; large runs may encounter delays or failures

### Recommendations
- Start with small runs (2-3 suburbs) to test
- Monitor your Perplexity API credit balance
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
- **Deep Research**: Powered by Perplexity's agentic research with Claude Sonnet 4.5
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
- **Triple Interface**: Three ways to use the application
  - Basic command-line interface (argparse)
  - Interactive CLI with autocomplete and validation (prompt_toolkit + rich)
  - Web interface with real-time status updates (FastAPI)

## Installation

### Prerequisites

- Python 3.10 or higher
- Perplexity API key ([Get one here](https://www.perplexity.ai/))

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

   Edit `.env` and add your Perplexity API key:
   ```
   PERPLEXITY_API_KEY=pplx-your-api-key-here
   ```

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
- `--run-id`: Custom run ID (default: auto-generated timestamp)

#### Examples

**Search South East Queensland for affordable houses**:
```bash
python -m src.app \
  --max-price 700000 \
  --dwelling-type house \
  --regions "South East Queensland" \
  --num-suburbs 10
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
    └── static/                 # CSS and assets
        └── css/
            └── styles.css
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
# Perplexity API Configuration
PERPLEXITY_API_KEY=your-api-key-here

# Optional Settings
OUTPUT_DIR=runs
REQUEST_TIMEOUT=180
MAX_RETRIES=3
```

### Advanced Configuration

Edit `src/config/settings.py` for advanced settings:
- API timeouts and retry behavior
- Default model and preset
- Output directory structure
- Chart styling and dimensions

## Performance Notes

- **API Costs**: Each suburb requires deep research API calls (~2-5 minutes per suburb)
- **Rate Limits**: Perplexity API rate limits may affect large runs
- **Recommended**: Start with 3-5 suburbs for testing
- **Warning**: Runs with >25 suburbs will prompt for confirmation due to cost/time

## Architecture

```
src/
├── config/              # Settings and region definitions
├── models/              # Pydantic data models
├── research/            # Perplexity integration and analysis
├── reporting/           # Chart generation and HTML rendering
└── ui/                  # Templates and static assets
    └── web/
        ├── templates/   # Jinja2 HTML templates
        └── static/      # CSS, JS, images
```

### Key Components

1. **Perplexity Client** (`research/perplexity_client.py`): API wrapper with retry logic
2. **Suburb Discovery** (`research/suburb_discovery.py`): Finds qualifying suburbs
3. **Suburb Research** (`research/suburb_research.py`): Deep research per suburb
4. **Ranking Engine** (`research/ranking.py`): Scores and ranks suburbs
5. **Chart Generator** (`reporting/charts.py`): Creates visualizations
6. **HTML Renderer** (`reporting/html_renderer.py`): Generates reports

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

# Run all tests
python -m pytest tests/ -v

# Run specific test
python tests/test_perplexity.py
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

**API Key Not Found**:
```
Error: PERPLEXITY_API_KEY not set
```
Solution: Ensure `.env` file exists with valid API key.

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

- [ ] FastAPI web interface
- [ ] Interactive CLI with prompt_toolkit
- [ ] Export to PDF/Excel
- [ ] Historical data caching
- [ ] Comparison mode for multiple runs
- [ ] Email report delivery
- [ ] RESTful API for integration

## Acknowledgments

- **Perplexity AI**: Deep research API with web search capabilities
- **Anthropic**: Claude Sonnet 4.5 for advanced reasoning
- **Libraries**: Pydantic, Jinja2, Matplotlib, Seaborn

## Disclaimer

This tool is for informational and research purposes only. It does not constitute financial or investment advice. Property markets are subject to various risks and uncertainties. Always conduct your own due diligence and consult with qualified professionals before making investment decisions.
