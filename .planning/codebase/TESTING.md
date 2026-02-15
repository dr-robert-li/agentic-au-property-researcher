# Testing Patterns

**Analysis Date:** 2026-02-15

## Test Framework

**Runner:**
- Python unittest-style test functions (no pytest/unittest framework enforced)
- Tests run as standalone scripts via `python -m tests.test_*` or direct execution
- Manual test runner pattern: each test file has `if __name__ == "__main__"` entry point

**Assertion Library:**
- Built-in Python `assert` statements with custom error messages
- Pattern: `assert condition, f"Expected X, got Y"`

**Run Commands:**
```bash
python tests/test_models.py              # Run configuration and models tests
python tests/test_perplexity.py          # Test Perplexity client connectivity
python tests/test_cache.py               # Test cache functionality
python tests/test_research_ranking.py    # Test ranking logic with mock data
python tests/test_charts.py              # Test chart generation
python tests/test_end_to_end.py          # Test complete pipeline
```

No centralized test runner (pytest/unittest) detected; tests are independent scripts.

## Test File Organization

**Location:**
- `tests/` directory at root level, separate from `src/`
- Test files co-located by function area: `test_perplexity.py`, `test_cache.py`, `test_models.py`, `test_discovery.py`

**Naming:**
- `test_*.py` pattern: `test_perplexity.py`, `test_cache.py`, `test_models.py`
- Functions within tests: `test_<feature>()` (e.g., `test_perplexity_client()`, `test_make_key_deterministic()`)

**Structure:**
```
tests/
├── test_models.py              # Configuration + data model validation
├── test_perplexity.py          # Perplexity client connectivity
├── test_cache.py               # Cache key generation, put/get, TTL
├── test_cache_resilience.py    # Cache JSON parsing robustness
├── test_discovery.py           # Suburb discovery functionality
├── test_research_ranking.py    # Ranking logic with mock data
├── test_charts.py              # Chart generation output
├── test_exports.py             # PDF/Excel export functionality
├── test_comparison.py          # Comparison report generation
├── test_pipeline.py            # Research pipeline orchestration
├── test_end_to_end.py          # Full pipeline integration
├── test_parallel.py            # Parallel processing threads
└── test_output/                # Generated test artifacts
```

## Test Structure

**Suite Organization:**
- Each test file contains standalone functions, no suite classes
- Global tracking variables for pass/fail: `passed = 0`, `failed = 0`, `errors = []`
- Test runner helper function: `run_test(name, fn)` wraps each test with try/except

Example from `src/tests/test_cache.py`:
```python
passed = 0
failed = 0
errors = []

def run_test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ✓ {name}")
        passed += 1
    except Exception as e:
        print(f"  ✗ {name}")
        errors.append((name, traceback.format_exc()))
        failed += 1

# Then in main:
if __name__ == "__main__":
    run_test("key generation deterministic", test_make_key_deterministic)
    run_test("key differs for different inputs", test_make_key_different_for_different_inputs)
```

**Patterns:**
- **Setup:** `make_cache(tmpdir, **overrides)` helper creates test fixtures with temp directories
- **Assertions:** Direct assert statements with descriptive messages
- **Output:** Print statements for progress, visual checkmarks (✓/✗) for results
- **Cleanup:** Temp directories created via Python's `tempfile` module, auto-cleaned

## Mocking

**Framework:** Not formally declared; manual mock data creation observed

**Patterns:**
- **Mock data creation:** Test files create realistic mock objects using actual Pydantic models

Example from `test_charts.py`:
```python
# Create mock suburb with data
mock_suburb = SuburbMetrics(
    identification=SuburbIdentification(
        name="Test Suburb",
        state="QLD",
        lga="Brisbane",
        region="Greater Brisbane"
    ),
    market_current=MarketMetricsCurrent(median_price=650000),
    market_history=MarketMetricsHistory(
        price_history=[
            TimePoint(year=2019, value=550000),
            TimePoint(year=2020, value=590000),
            # ...
        ]
    ),
    growth_projections=GrowthProjections(
        projected_growth_pct={1: 5.0, 2: 10.5, 3: 16.2, 5: 28.5, 10: 65.0, 25: 180.0},
        growth_score=82.5,
        risk_score=35.0,
        composite_score=75.8
    )
)
```

**What to Mock:**
- API responses (use realistic JSON structures)
- File system operations (use `Path()` and temp directories)
- Model instances (use actual Pydantic models with test data)

**What NOT to Mock:**
- Logic functions like `rank_suburbs()`, `calculate_comparison_stats()` — test with real data
- Data model validation (Pydantic does this automatically)
- Cache operations — test with actual `ResearchCache` instance

## Fixtures and Factories

**Test Data:**
- **Mock suburb generator:** `SuburbMetrics` created with full nested structure

Example from `test_research_ranking.py`:
```python
mock_suburbs = [
    SuburbMetrics(
        identification=SuburbIdentification(
            name="Acacia Ridge",
            state="QLD",
            lga="Brisbane",
            region="Greater Brisbane"
        ),
        market_current=MarketMetricsCurrent(median_price=650000),
        growth_projections=GrowthProjections(
            projected_growth_pct={1: 5.0, 2: 10.5, 3: 16.2, 5: 28.5, 10: 65.0, 25: 180.0},
            growth_score=82.5,
            risk_score=35.0,
            composite_score=75.8
        )
    ),
    # ... more suburbs
]
```

**Location:**
- Fixtures defined inline in test functions or as module-level helper functions
- No separate fixtures file; each test file is self-contained
- Temp directories created with `tempfile` and passed to `make_cache(tmpdir, **overrides)`

## Coverage

**Requirements:** No coverage target enforced or configured

**View Coverage:**
- No pytest coverage plugin or coverage.py configuration
- Manual inspection of test file count and function count
- Tests provide functional validation, not statistical coverage metrics

## Test Types

**Unit Tests:**
- Isolated function testing with mock data
- Examples: `test_make_key_deterministic()` (cache key generation), `test_ranking_logic()` (sorting)
- Scope: Single function or small utility module in isolation
- Approach: Create minimal valid inputs, verify expected output

**Integration Tests:**
- Tests that combine multiple modules
- Example: `test_small_pipeline_run()` validates discovery → research → ranking → report generation
- Scope: Full or partial pipeline from user input to artifacts
- Approach: Create realistic user input, run full pipeline, verify directory structure and file existence

**E2E Tests:**
- Not formally declared but `test_end_to_end.py` performs full run
- Validates: Input validation, pipeline execution, output generation, report files, chart existence
- Note: Requires valid API keys; skipped in CI environments

## Common Patterns

**Async Testing:**
- No async code in codebase; threading used for parallel execution
- Parallel tests in `test_parallel.py` verify thread-safe operations and concurrent discovery/research

**Error Testing:**
Example from `test_cache_resilience.py`:
```python
def test_cached_data_invalid_triggers_refetch():
    """Test that invalid cached data triggers a refetch from API."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir, enabled=True)

        # Simulate corrupted cache entry
        cache.put("discovery", invalid_json_string)

        # Verify refetch triggered
        result = cache.get("discovery")
        assert result is None, "Invalid cache should return None and trigger refetch"
```

**Exception Testing:**
- Custom exceptions imported and verified: `PerplexityRateLimitError`, `PerplexityAuthError`
- Pattern: Catch expected exception type and verify error message contains key text
- Example: Verify error message includes "RATE LIMIT EXCEEDED" or "INSUFFICIENT CREDITS"

## Test Data Patterns

**Suburb Creation Helpers:**
Each test file that needs suburb data uses:
```python
SuburbMetrics(
    identification=SuburbIdentification(...),
    market_current=MarketMetricsCurrent(...),
    growth_projections=GrowthProjections(...)
)
```

**Validation Testing:**
- Pydantic models self-validate on instantiation
- Tests verify field constraints: `max_median_price` > 0, `num_suburbs` 1-100
- Field validators tested indirectly by attempting invalid instantiation

**Cache Testing:**
- Mock JSON responses for discovery/research
- Verify key generation consistency
- Test TTL expiration with mocked time
- Verify concurrent access safety with threading

---

*Testing analysis: 2026-02-15*
