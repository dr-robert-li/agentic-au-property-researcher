# Phase 5: Comprehensive Testing - Research

**Researched:** 2026-02-16
**Domain:** Python testing (pytest, async/concurrent testing, FastAPI testing)
**Confidence:** HIGH

## Summary

This phase involves comprehensive testing of a multi-threaded, async Python application with FastAPI web server, SSE endpoints, Perplexity API integration, and concurrent suburb research pipeline. The testing strategy must validate thread safety, async behavior, API mocking, and end-to-end integration.

The project currently uses a custom test runner pattern. The research recommends migrating to pytest for better tooling, fixtures, async support, and coverage reporting. Key challenges include testing concurrent cache operations, SSE event streaming with client disconnects, and race conditions in shared state (threading.Lock, queue.Queue, copy.deepcopy()).

**Primary recommendation:** Adopt pytest with pytest-asyncio, pytest-mock, responses (for API mocking), and pytest-cov (coverage). Use custom markers to organize test categories (unit, integration, async, concurrent). Implement conftest.py for shared fixtures. Use httpx.AsyncClient for async FastAPI endpoints and TestClient for synchronous ones.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=8.0.0 | Test framework | Industry standard, powerful fixtures, plugins, async support |
| pytest-asyncio | >=0.24.0 | Async test support | Required for testing FastAPI async endpoints and SSE streams |
| pytest-mock | >=3.14.0 | Mocking utilities | Cleaner unittest.mock wrapper, mocker fixture |
| pytest-cov | >=6.0.0 | Coverage reporting | Official pytest plugin, HTML/XML/terminal reports |
| httpx | >=0.27.0 | HTTP client for testing | Required for AsyncClient to test FastAPI async endpoints |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| responses | >=0.25.0 | Mock HTTP responses | Mocking Perplexity/Anthropic API calls without hitting real endpoints |
| pytest-repeat | >=0.9.3 | Repeat tests N times | Detecting flaky race conditions (run with --count=100) |
| pytest-xdist | >=3.6.0 | Parallel test execution | Speed up test suite (use -n auto), ensures main thread for asyncio |
| freezegun | >=1.5.0 | Mock datetime/time | Testing TTL expiration in cache without waiting |
| faker | >=30.0.0 | Generate test data | Creating realistic suburb/region names for parametrized tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest (built-in) | pytest has better fixtures, parametrization, plugins; unittest is stdlib |
| responses | requests-mock | responses is simpler for basic mocking; requests-mock has more features |
| httpx.AsyncClient | Starlette TestClient | AsyncClient needed for async endpoints; TestClient creates own event loop |

**Installation:**
```bash
pip install pytest>=8.0.0 pytest-asyncio>=0.24.0 pytest-mock>=3.14.0 pytest-cov>=6.0.0 httpx>=0.27.0 responses>=0.25.0 pytest-repeat>=0.9.3 freezegun>=1.5.0 faker>=30.0.0
```

## Architecture Patterns

### Recommended Test Structure
```
tests/
├── conftest.py              # Shared fixtures (cache, mock API, temp dirs)
├── unit/                    # Fast, isolated tests
│   ├── test_cache.py
│   ├── test_exceptions.py
│   ├── test_validation.py
│   └── test_worker_scaling.py
├── integration/             # Multi-component tests
│   ├── test_pipeline.py
│   ├── test_discovery_to_research.py
│   └── test_checkpoint_recovery.py
├── async_tests/             # Async/SSE tests (pytest-asyncio)
│   ├── test_sse_endpoints.py
│   ├── test_async_client_disconnect.py
│   └── test_server_shutdown.py
├── concurrent/              # Thread safety tests
│   ├── test_cache_race_conditions.py
│   ├── test_parallel_research.py
│   └── test_queue_thread_safety.py
└── fixtures/                # Test data fixtures
    ├── mock_responses.py
    └── sample_data.py
```

### Pattern 1: pytest Configuration with Custom Markers
**What:** Define custom markers for test categorization and selective execution
**When to use:** Organizing large test suites by type (unit, integration, async, concurrent, slow)
**Example:**
```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "unit: Fast unit tests with no external dependencies",
    "integration: Integration tests spanning multiple components",
    "async: Async tests using pytest-asyncio",
    "concurrent: Thread safety and race condition tests",
    "slow: Tests that take > 5 seconds",
    "api_mock: Tests that mock external APIs"
]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--strict-markers --tb=short"
```

Run specific test categories:
```bash
pytest -m unit              # Fast tests only
pytest -m "not slow"        # Skip slow tests
pytest -m "async or concurrent"  # Async and concurrent tests
```

### Pattern 2: Shared Fixtures in conftest.py
**What:** Define reusable fixtures accessible to all tests
**When to use:** Common setup (temp dirs, mock clients, sample data) used across multiple test files
**Example:**
```python
# tests/conftest.py
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from research.cache import ResearchCache, CacheConfig

@pytest.fixture
def temp_cache_dir():
    """Temporary directory for cache tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def mock_cache(temp_cache_dir):
    """ResearchCache instance with temp directory."""
    config = CacheConfig(
        cache_dir=temp_cache_dir,
        discovery_ttl=86400,
        research_ttl=604800,
        enabled=True
    )
    return ResearchCache(config)

@pytest.fixture
def mock_perplexity_client(mocker):
    """Mocked Perplexity client with canned responses."""
    client = mocker.Mock()
    client.search.return_value = {"results": [...]}
    return client

@pytest.fixture(autouse=True)
def reset_global_state():
    """Auto-cleanup fixture to reset global state between tests."""
    yield
    # Cleanup code here
```

### Pattern 3: Mocking External APIs with responses
**What:** Intercept HTTP requests and return predefined responses
**When to use:** Testing Perplexity/Anthropic API integration without hitting real endpoints
**Example:**
```python
# tests/fixtures/mock_responses.py
import responses
import pytest

@pytest.fixture
def mock_perplexity_api():
    """Mock Perplexity deep-research endpoint."""
    with responses.RequestsMock() as rsps:
        rsps.add(
            method=responses.POST,
            url="https://api.perplexity.ai/chat/completions",
            json={
                "choices": [{
                    "message": {
                        "content": '{"suburbs": [...]}'
                    }
                }]
            },
            status=200
        )
        yield rsps

# Usage in test
def test_discovery(mock_perplexity_api):
    result = discover_suburbs(...)
    assert len(result) > 0
```

### Pattern 4: Testing Async FastAPI Endpoints
**What:** Use httpx.AsyncClient with pytest-asyncio for async endpoint testing
**When to use:** Testing FastAPI routes that use async def, database operations, or SSE streams
**Example:**
```python
# tests/async_tests/test_sse_endpoints.py
import pytest
from httpx import AsyncClient, ASGITransport
from src.ui.web.server import app

@pytest.mark.asyncio
async def test_sse_progress_stream():
    """Test SSE endpoint streams progress events."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        async with client.stream("GET", "/api/progress/run123") as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream"

            events = []
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    events.append(line[5:].strip())
                if len(events) >= 3:
                    break

            assert len(events) == 3
            assert "suburb_discovered" in events[0]

@pytest.mark.asyncio
async def test_client_disconnect_cleanup():
    """Test SSE connection cleanup when client disconnects."""
    # Test implementation
    pass
```

### Pattern 5: Testing Thread Safety with Concurrent Execution
**What:** Use ThreadPoolExecutor or threading.Barrier to force race conditions
**When to use:** Verifying cache operations, queue.Queue usage, and Lock-protected code under concurrent access
**Example:**
```python
# tests/concurrent/test_cache_race_conditions.py
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

@pytest.mark.concurrent
def test_cache_concurrent_writes(mock_cache):
    """Verify cache handles concurrent writes without corruption."""
    barrier = threading.Barrier(10)  # Synchronize 10 threads
    results = []

    def write_entry(index):
        barrier.wait()  # All threads start simultaneously
        mock_cache.put(f"key_{index}", {"data": f"value_{index}"}, "discovery")
        return index

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(write_entry, i) for i in range(10)]
        results = [f.result() for f in as_completed(futures)]

    # Verify all entries written without corruption
    assert len(results) == 10
    for i in range(10):
        entry = mock_cache.get(f"key_{i}", "discovery")
        assert entry is not None
        assert entry["data"] == f"value_{i}"

@pytest.mark.concurrent
@pytest.mark.repeat(100)  # Run 100 times to catch intermittent failures
def test_queue_thread_safety():
    """Test queue.Queue thread safety under high contention."""
    # Test implementation with multiple producers/consumers
    pass
```

### Pattern 6: Testing copy.deepcopy() for Cross-Thread State
**What:** Verify that cross-thread state reads use deepcopy to prevent mutation
**When to use:** Testing progress reporting, web server state access
**Example:**
```python
# tests/unit/test_deepcopy_isolation.py
import copy
import threading

def test_deepcopy_prevents_mutation():
    """Verify deepcopy isolates cross-thread state."""
    shared_state = {"suburbs": [{"name": "Test", "price": 500000}]}
    lock = threading.Lock()

    def reader():
        with lock:
            snapshot = copy.deepcopy(shared_state)
        # Mutate snapshot
        snapshot["suburbs"][0]["price"] = 999999
        return snapshot

    result = reader()

    # Original state unchanged
    assert shared_state["suburbs"][0]["price"] == 500000
    # Snapshot mutated
    assert result["suburbs"][0]["price"] == 999999
```

### Pattern 7: Parametrized Tests for Multiple Scenarios
**What:** Use @pytest.mark.parametrize to run same test with different inputs
**When to use:** Testing validation logic, exception handling, or API response variations
**Example:**
```python
# tests/unit/test_validation.py
import pytest
from research.validation import validate_suburb_metrics

@pytest.mark.parametrize("metrics,expected_valid", [
    ({"name": "Valid", "median_price": 500000}, True),
    ({"name": "", "median_price": 500000}, False),  # Empty name
    ({"name": "Test", "median_price": -1000}, False),  # Negative price
    ({"name": "Test"}, False),  # Missing required field
    ({}, False),  # Empty dict
])
def test_suburb_metrics_validation(metrics, expected_valid):
    result = validate_suburb_metrics(metrics)
    assert result == expected_valid
```

### Anti-Patterns to Avoid
- **Sharing mutable fixtures between tests:** Use function-scoped fixtures (default) or yield-based cleanup
- **Testing implementation details:** Test public APIs and observable behavior, not private methods
- **Ignoring async warnings:** Always mark async tests with @pytest.mark.asyncio
- **Over-mocking:** Mock external dependencies (APIs), not internal logic
- **No cleanup in fixtures:** Use yield fixtures to ensure cleanup runs even if test fails
- **Pytest + asyncio event loop conflicts:** Use httpx.AsyncClient, not TestClient for async endpoints

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test parametrization | Manual loops with test data | @pytest.mark.parametrize | Cleaner test output, better failure reporting, automatic test discovery |
| Mock API responses | Custom HTTP mock server | responses or requests-mock | Handles edge cases (timeouts, retries, redirects), thread-safe |
| Async test runner | Custom asyncio.run() wrapper | pytest-asyncio | Proper event loop management, fixture support, cleanup |
| Coverage reporting | Manual coverage tracking | pytest-cov | HTML reports, branch coverage, CI integration, threshold enforcement |
| Temporary files/dirs | Manual tempfile cleanup | pytest tmp_path fixture | Automatic cleanup, unique per test, path operations |
| Datetime mocking | Manual monkey-patching | freezegun | Handles all time.time(), datetime.now(), etc., thread-safe |
| Flaky test detection | Manual rerun logic | pytest-repeat or pytest-rerunfailures | Configurable retries, failure tracking |

**Key insight:** pytest ecosystem has battle-tested plugins for common testing patterns. Custom solutions miss edge cases (event loop cleanup, thread safety, fixture teardown order) that plugins handle correctly.

## Common Pitfalls

### Pitfall 1: Mixing Synchronous and Async Test Clients
**What goes wrong:** Using TestClient for async FastAPI endpoints causes "event loop closed" errors
**Why it happens:** TestClient creates its own event loop; async resources (DB connections, SSE streams) can't be shared across loops
**How to avoid:** Use httpx.AsyncClient with ASGITransport for async endpoints, TestClient only for sync endpoints
**Warning signs:** RuntimeError about event loops, asyncio warnings, database connection errors in async tests

### Pitfall 2: Race Conditions Not Reproducing Consistently
**What goes wrong:** Concurrent tests pass most of the time but fail intermittently
**Why it happens:** Thread scheduling is non-deterministic; race conditions require precise timing
**How to avoid:**
- Use threading.Barrier to synchronize threads
- Run tests with pytest-repeat (--count=100 or higher)
- Add small random delays in critical sections (for testing only)
- Use ThreadSanitizer for production race detection
**Warning signs:** Tests fail in CI but pass locally, failures happen ~1-5% of runs

### Pitfall 3: Pytest Not Thread-Safe for Fixtures
**What goes wrong:** Shared fixtures mutated by parallel tests cause failures
**Why it happens:** Pytest fixtures are not thread-safe; parallel tests share state
**How to avoid:**
- Use function-scoped fixtures (default) for mutable state
- Don't use pytest-xdist for tests that share stateful fixtures
- For thread safety tests, use custom ThreadPoolExecutor, not pytest-xdist
**Warning signs:** Fixtures have unexpected values, tests fail when run with -n auto

### Pitfall 4: Mocks Don't Match Real API Changes
**What goes wrong:** Tests pass with mocked APIs but production code fails with real API
**Why it happens:** Mock responses become stale when external API changes interface
**How to avoid:**
- Document mock response source (URL, date captured)
- Periodically update mocks from real API responses
- Use contract testing (pytest-contracts) for critical integrations
- Run subset of integration tests against real API weekly
**Warning signs:** All tests pass but production errors, API returns new fields/structure

### Pitfall 5: Cache Tests Don't Clean Up Between Runs
**What goes wrong:** Test cache state leaks between tests, causing false passes/failures
**Why it happens:** Cache persists on disk; fixtures don't clean up properly
**How to avoid:**
- Use tmp_path fixture for cache directory (auto-cleanup)
- Use autouse fixtures to reset cache state
- Verify cache.clear() in teardown
**Warning signs:** Tests pass when run individually but fail in suite, order-dependent failures

### Pitfall 6: SSE Tests Don't Handle Client Disconnect
**What goes wrong:** SSE endpoint tests hang or leak connections
**Why it happens:** Test doesn't simulate client disconnect; server keeps stream open
**How to avoid:**
- Use async context manager (async with client.stream())
- Set timeouts on SSE streams
- Test explicit disconnect scenarios
- Verify connection cleanup in server state
**Warning signs:** Tests take forever, resource warnings about unclosed connections

### Pitfall 7: Coverage Reports Include Virtual Environment
**What goes wrong:** Coverage report shows 1000s of files from venv/
**Why it happens:** pytest-cov default includes all Python files in working directory
**How to avoid:**
```toml
# pyproject.toml
[tool.coverage.run]
source = ["src"]
omit = ["*/venv/*", "*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```
**Warning signs:** Coverage report has 5000+ files, includes site-packages/

## Code Examples

Verified patterns from official sources:

### Example 1: conftest.py with Shared Fixtures
```python
# tests/conftest.py
# Source: https://docs.pytest.org/en/stable/how-to/fixtures.html
import pytest
import tempfile
from pathlib import Path
from research.cache import ResearchCache, CacheConfig

@pytest.fixture(scope="function")
def temp_dir():
    """Function-scoped temp directory (fresh per test)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def cache_config(temp_dir):
    """Cache configuration with temp directory."""
    return CacheConfig(
        cache_dir=temp_dir,
        discovery_ttl=86400,
        research_ttl=604800,
        enabled=True
    )

@pytest.fixture
def research_cache(cache_config):
    """ResearchCache instance for testing."""
    return ResearchCache(cache_config)

@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global state before each test (autouse=True)."""
    # Reset code here
    yield
    # Cleanup code here
```

### Example 2: Async FastAPI Test with httpx.AsyncClient
```python
# tests/async_tests/test_server_endpoints.py
# Source: https://fastapi.tiangolo.com/advanced/async-tests/
import pytest
from httpx import AsyncClient, ASGITransport
from src.ui.web.server import app

@pytest.mark.asyncio
async def test_progress_sse_endpoint():
    """Test SSE progress endpoint streams events correctly."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

@pytest.mark.asyncio
async def test_sse_stream_events():
    """Test SSE stream delivers progress events."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        async with client.stream("GET", "/api/progress/test-run") as response:
            assert response.status_code == 200
            lines = []
            async for line in response.aiter_lines():
                lines.append(line)
                if len(lines) >= 5:
                    break
            assert any("event:" in line for line in lines)
```

### Example 3: Testing Thread Safety with Barriers
```python
# tests/concurrent/test_cache_concurrency.py
# Source: https://py-free-threading.github.io/testing/
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor

@pytest.mark.concurrent
def test_concurrent_cache_writes(research_cache):
    """Verify cache is thread-safe under concurrent writes."""
    num_threads = 10
    barrier = threading.Barrier(num_threads)
    results = []

    def write_and_read(thread_id):
        barrier.wait()  # Synchronize all threads
        key = f"suburb_{thread_id}"
        data = {"name": f"Test{thread_id}", "price": 500000 + thread_id}
        research_cache.put(key, data, "discovery")
        retrieved = research_cache.get(key, "discovery")
        return retrieved == data

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(write_and_read, i) for i in range(num_threads)]
        results = [f.result() for f in futures]

    assert all(results), "Some threads read incorrect data"
```

### Example 4: Mocking External API with responses
```python
# tests/unit/test_perplexity_client.py
# Source: https://github.com/getsentry/responses
import pytest
import responses
from research.perplexity_client import PerplexityClient

@pytest.fixture
def mock_perplexity_success():
    """Mock successful Perplexity API response."""
    with responses.RequestsMock() as rsps:
        rsps.add(
            method=responses.POST,
            url="https://api.perplexity.ai/chat/completions",
            json={
                "id": "test-123",
                "model": "anthropic/claude-sonnet-4-5",
                "choices": [{
                    "message": {
                        "content": '{"suburbs": [{"name": "Test", "state": "QLD"}]}'
                    }
                }]
            },
            status=200
        )
        yield rsps

def test_discovery_api_call(mock_perplexity_success):
    """Test discover_suburbs makes correct API call."""
    client = PerplexityClient(api_key="test-key")
    result = client.discover(max_price=600000, dwelling_type="house")
    assert len(result) > 0
    assert result[0]["name"] == "Test"
```

### Example 5: Parametrized Test with Multiple Scenarios
```python
# tests/unit/test_validation.py
# Source: https://docs.pytest.org/en/stable/how-to/parametrize.html
import pytest
from research.validation import validate_api_response

@pytest.mark.parametrize("response,expected_valid,expected_error", [
    ({"suburbs": [{"name": "Test", "median_price": 500000}]}, True, None),
    ({"suburbs": []}, False, "No suburbs found"),
    ({}, False, "Missing required field: suburbs"),
    ({"suburbs": [{"name": ""}]}, False, "Empty suburb name"),
    ({"suburbs": [{"median_price": -1000}]}, False, "Invalid price"),
])
def test_api_response_validation(response, expected_valid, expected_error):
    """Test API response validation handles various scenarios."""
    is_valid, error_msg = validate_api_response(response)
    assert is_valid == expected_valid
    if not expected_valid:
        assert expected_error in error_msg
```

### Example 6: FastAPI Dependency Override for Testing
```python
# tests/integration/test_web_routes.py
# Source: https://fastapi.tiangolo.com/advanced/testing-dependencies/
import pytest
from fastapi.testclient import TestClient
from src.ui.web.server import app, get_research_cache

@pytest.fixture
def mock_cache_dependency(research_cache):
    """Override cache dependency with test cache."""
    def override_get_cache():
        return research_cache

    app.dependency_overrides[get_research_cache] = override_get_cache
    yield
    app.dependency_overrides.clear()

def test_start_run_endpoint(mock_cache_dependency):
    """Test POST /api/run creates new research run."""
    client = TestClient(app)
    response = client.post("/api/run", json={
        "max_median_price": 600000,
        "dwelling_type": "house",
        "regions": ["Queensland"],
        "num_suburbs": 5
    })
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| unittest.TestCase | pytest with fixtures | ~2015 | Cleaner tests, better parametrization, plugin ecosystem |
| Manual async test runners | pytest-asyncio | 2020 | Proper event loop management, fixture support |
| TestClient for all endpoints | AsyncClient for async | 2022 | Fixes event loop issues with async endpoints |
| Manual coverage tracking | pytest-cov with branch coverage | 2018 | HTML reports, CI integration, branch coverage |
| pytest-xdist < 3.6 | pytest-xdist >= 3.6 with main thread | 2024 | Fixes asyncio compatibility, ensures main thread execution |
| responses for all mocking | responses + requests-mock | 2023 | responses simpler; requests-mock for complex scenarios |

**Deprecated/outdated:**
- **unittest.TestCase with pytest:** pytest can run unittest tests, but native pytest style is preferred
- **@pytest.mark.asyncio(mode="auto") explicit:** Now use asyncio_mode = "auto" in config
- **pytest.yield_fixture:** Replaced by @pytest.fixture with yield (since pytest 3.0)
- **pytest.fixture(scope="module") for temp dirs:** Use function scope to avoid state leakage

## Open Questions

1. **Current test framework migration:**
   - What we know: Tests use custom test runner (run_test() pattern), not pytest
   - What's unclear: Migration strategy—convert all tests at once or incrementally?
   - Recommendation: Incremental migration—keep custom runner for existing tests, write new Phase 5 tests in pytest, convert legacy tests in Phase 6

2. **pytest-xdist for parallel execution:**
   - What we know: pytest-xdist >= 3.6 ensures main thread for asyncio compatibility
   - What's unclear: Will parallel execution reveal new race conditions in existing code?
   - Recommendation: Use -n auto cautiously; start with -n 2, monitor for flaky tests, increase workers gradually

3. **Coverage threshold enforcement:**
   - What we know: pytest-cov can enforce minimum coverage (--cov-fail-under=80)
   - What's unclear: What threshold is realistic for this codebase?
   - Recommendation: Start with --cov-report=html to see current coverage, then set --cov-fail-under=70 (aim for 80%+ over time)

4. **Testing real API integration:**
   - What we know: All tests should mock APIs to avoid rate limits and API costs
   - What's unclear: How often should we run integration tests against real Perplexity API?
   - Recommendation: Weekly scheduled CI job with real API (small dataset), mark with @pytest.mark.real_api (skip by default)

## Sources

### Primary (HIGH confidence)
- [pytest Official Documentation](https://docs.pytest.org/en/stable/) - Fixtures, parametrization, markers
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/) - Async test patterns
- [FastAPI Async Tests](https://fastapi.tiangolo.com/advanced/async-tests/) - AsyncClient usage
- [FastAPI Testing Dependencies](https://fastapi.tiangolo.com/advanced/testing-dependencies/) - Dependency override pattern
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/en/latest/) - Coverage configuration
- [Python Free-Threading Testing Guide](https://py-free-threading.github.io/testing/) - Thread safety validation

### Secondary (MEDIUM confidence)
- [Pytest Fixtures Complete Guide 2026](https://devtoolbox.dedyn.io/blog/pytest-fixtures-complete-guide) - Modern fixture patterns
- [Testing Race Conditions with pytest](https://woteq.com/testing-race-conditions-in-python-with-pytest/) - Concurrent testing strategies
- [pytest-xdist Changelog](https://pytest-xdist.readthedocs.io/en/latest/changelog.html) - Version 3.6 asyncio improvements
- [responses Library PyPI](https://pypi.org/project/responses/) - HTTP mocking
- [sse-starlette PyPI](https://pypi.org/project/sse-starlette/) - SSE implementation

### Tertiary (LOW confidence)
- [Medium: Pytest Markers Guide](https://medium.com/@johnidouglasmarangon/pytest-how-to-use-custom-markers-to-enhance-your-test-suite-7720129f625d) - Custom markers
- [Medium: Testing SSE with FastAPI](https://medium.com/@inandelibas/real-time-notifications-in-python-using-sse-with-fastapi-1c8c54746eb7) - SSE testing examples

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest ecosystem is industry standard, well-documented
- Architecture: HIGH - Patterns verified from official docs (pytest, FastAPI, pytest-asyncio)
- Concurrent testing: MEDIUM - Thread safety testing is complex; barrier pattern verified but coverage varies
- SSE testing: MEDIUM - AsyncClient pattern verified, but SSE-specific testing has fewer canonical examples
- Pitfalls: HIGH - Common issues well-documented in pytest discussions and issues

**Research date:** 2026-02-16
**Valid until:** ~60 days (pytest stable, patterns mature; revalidate if pytest 9.0 releases)
