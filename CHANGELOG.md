# Changelog

All notable changes to the Australian Property Research project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- PDF/Excel export functionality
- Historical data caching layer
- Multi-run comparison mode
- Email report delivery
- RESTful API endpoints

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

- **v1.1.0** (2026-02-13): Dual AI provider support (Perplexity + Anthropic Claude)
- **v1.0.0** (2026-02-10): Web interface + interactive CLI
- **v0.1.0** (2026-02-01): Initial release with core functionality

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to this project.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.
