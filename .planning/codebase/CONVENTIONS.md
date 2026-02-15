# Coding Conventions

**Analysis Date:** 2026-02-15

## Naming Patterns

**Files:**
- Module files use `snake_case`: `perplexity_client.py`, `suburb_discovery.py`, `html_renderer.py`
- Test files use `test_*.py` pattern: `test_perplexity.py`, `test_cache.py`, `test_models.py`
- Package directories use `snake_case`: `src/config/`, `src/models/`, `src/research/`, `src/reporting/`, `src/ui/`

**Functions:**
- Use `snake_case` for all function names: `get_client()`, `discover_suburbs()`, `run_research_pipeline()`, `render_overview_report()`
- Private/internal functions prefixed with `_`: `_progress()`, `_make_key()`
- Factory functions prefix with `get_` or `create_`: `get_client()`, `get_region_names()`

**Variables:**
- Use `snake_case`: `user_input`, `run_result`, `suburbs_list`, `output_dir`, `max_retries`
- Constants use `UPPER_CASE`: `API_TIMEOUT`, `MAX_RETRIES`, `DEFAULT_PORT`, `CACHE_DIR`
- Private attributes prefixed with `_`: `self._error`, `self._lock`

**Types:**
- Use `PascalCase` for class names: `UserInput`, `SuburbMetrics`, `RunResult`, `PerplexityClient`, `AccountErrorSignal`
- Use `PascalCase` for exception classes: `PerplexityAPIError`, `PerplexityRateLimitError`, `AnthropicAuthError`

## Code Style

**Formatting:**
- No explicit formatter configured in repo (no `.prettierrc`, `.flake8`, `pyproject.toml`)
- Follow PEP 8 style (implicit standard)
- Use 4-space indentation (standard Python)
- Line wrapping observed for readability around 80-100 characters
- Blank lines between function definitions and class methods as per PEP 8

**Linting:**
- No linting configuration detected in repository
- Type hints used throughout codebase but not enforced via mypy
- Docstrings provided for modules, classes, and public functions

## Import Organization

**Order:**
1. Standard library imports (`import sys`, `from pathlib import Path`, `from typing import Optional`)
2. Third-party imports (`from pydantic import BaseModel`, `import matplotlib.pyplot as plt`, `from dotenv import load_dotenv`)
3. Local application imports (`from config import settings`, `from models.inputs import UserInput`, `from research.perplexity_client import get_client`)

**Pattern observed in `src/app.py`:**
```python
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from models.inputs import UserInput
from models.run_result import RunResult
from research.suburb_discovery import discover_suburbs, parallel_discover_suburbs
from research.perplexity_client import PerplexityRateLimitError
```

**Path Aliases:**
- `sys.path.insert(0, str(Path(__file__).parent))` used in test files to enable absolute imports from `src/`
- Relative imports within packages (`from .inputs import UserInput` in `models/run_result.py`)
- Import errors handled gracefully in client initialization (e.g., Perplexity SDK optional)

## Error Handling

**Patterns:**
- **Custom exception hierarchy:** Base exception class with specific subclasses
  - `PerplexityAPIError` (base) → `PerplexityRateLimitError`, `PerplexityAuthError`
  - `AnthropicAPIError` (base) → `AnthropicRateLimitError`, `AnthropicAuthError`
- **Error detection with informative messages:** Exceptions include actionable user guidance (check API balance, verify credentials, etc.)
- **Graceful degradation:** Client initialization catches import errors and sets `initialized=False` flag
- **Retry logic with exponential backoff:** Implemented in client calls with configurable `max_retries` and `RETRY_DELAY`
- **Thread-safe error signaling:** `AccountErrorSignal` class for propagating account-level errors across parallel workers
- **Validation in models:** Pydantic validators in `UserInput` (e.g., `validate_regions()`, `validate_num_suburbs()`)
- **Optional type handling:** Return `None` for missing data, use `Optional[Type]` in type hints throughout models

Example from `src/research/perplexity_client.py`:
```python
class PerplexityRateLimitError(PerplexityAPIError):
    """Exception raised when API rate limit is exceeded."""
    def __init__(self, message: str = None):
        default_msg = (
            "\n⚠️  API RATE LIMIT EXCEEDED OR INSUFFICIENT CREDITS\n\n"
            "Your Perplexity API request was denied. This typically means:\n"
            "  1. You've exceeded your API rate limit\n"
            "  2. Your API credit balance is insufficient\n\n"
            "ACTION REQUIRED:\n"
            "  → Check your API credit balance at:\n"
            "    https://www.perplexity.ai/account/api/billing\n"
        )
        super().__init__(message or default_msg)
```

## Logging

**Framework:** Python's built-in `logging` module

**Patterns:**
- Module-level loggers: `logger = logging.getLogger(__name__)`
- Used in `src/research/suburb_discovery.py`, `src/research/cache.py`, `src/reporting/exports.py`
- Typically used for debugging cache operations and error tracking
- No configured log level or handler setup in main source (configuration likely expected at runtime)

## Comments

**When to Comment:**
- Module docstrings (triple-quoted at top of every file) describing purpose and scope
- Class docstrings explaining the class role
- Method/function docstrings with Args, Returns, Raises sections
- Inline comments sparse; code is self-documenting via clear naming and type hints

**JSDoc/TSDoc:**
- Not applicable (Python project)
- Docstring format follows standard Python conventions with Args/Returns/Raises

Example from `src/app.py`:
```python
def run_research_pipeline(
    user_input: UserInput,
    progress_callback: Optional[Callable[[str], None]] = None
) -> RunResult:
    """
    Execute the complete research pipeline.

    Args:
        user_input: User input parameters
        progress_callback: Optional callback for progress updates (used by web UI)

    Returns:
        Complete RunResult with all reports
    """
```

## Function Design

**Size:** Functions tend to be focused and medium-length (30-50 lines typical), splitting responsibilities
- Discoverable functions like `discover_suburbs()` and `research_suburb()` are kept separate
- Parallel variants (`parallel_discover_suburbs()`) wrap sequential versions with threading logic

**Parameters:**
- Use type hints for all parameters: `suburb_name: str`, `max_results: Optional[int]`, `ranking_method: Literal["growth_score", "composite_score", "5yr_growth"]`
- Use `Literal` for constrained string choices (e.g., `Literal["house", "apartment", "townhouse"]`)
- Default parameters provided where sensible (e.g., `preset: str = "deep-research"`, `top_n: Optional[int] = None`)
- Pydantic `Field` used in dataclass definitions with defaults and validation metadata

**Return Values:**
- Always declare return type: `-> RunResult`, `-> list[SuburbMetrics]`, `-> Path`, `-> dict`
- Consistent return of structured data models (SuburbMetrics, RunResult, SuburbReport)
- Return `None` explicitly for functions without results, or use `Optional[Type]`

## Module Design

**Exports:**
- Functions and classes exported at module level without `__all__` (implicit public API)
- Imports at package level (`from .inputs import UserInput` in `models/__init__.py`)
- Factory functions provide single entry points: `get_client(provider)` to instantiate Perplexity or Anthropic clients

**Barrel Files:**
- `src/config/__init__.py` imports and re-exports `settings` and `regions_data` for convenience
- `src/models/__init__.py` exists (empty) but imports done explicitly per module

**Code Organization:**
- **Separation of concerns:** Each module has single responsibility (cache.py = caching, ranking.py = ranking logic, html_renderer.py = HTML rendering)
- **Data models isolated:** `src/models/` contains only Pydantic dataclasses with no business logic
- **Research layer separate:** `src/research/` handles API calls and data fetching
- **Reporting layer separate:** `src/reporting/` handles output generation (HTML, charts, exports)

---

*Convention analysis: 2026-02-15*
