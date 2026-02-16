---
phase: 05-comprehensive-testing
plan: 01
subsystem: testing
tags: [pytest, unit-tests, cache, exceptions, validation, worker-scaling]
dependency-graph:
  requires: [01-01, 01-02, 02-01, 04-01, 04-02, 04-03]
  provides: [test-infrastructure, unit-test-suite]
  affects: [05-02]
tech-stack:
  added: [pytest, pytest-asyncio, pytest-mock, pytest-cov, freezegun]
  patterns: [fixture-based-testing, parametrized-tests, mock-patching]
key-files:
  created:
    - pyproject.toml
    - requirements-dev.txt
    - tests/conftest.py
    - tests/__init__.py
    - tests/unit/__init__.py
    - tests/fixtures/__init__.py
    - tests/fixtures/sample_data.py
    - tests/fixtures/mock_responses.py
    - tests/unit/test_cache.py
    - tests/unit/test_exceptions.py
    - tests/unit/test_validation.py
    - tests/unit/test_worker_scaling.py
  modified: []
decisions:
  - "Used sys.modules patching for lazy psutil imports in worker_scaling tests"
  - "Used config.settings.CACHE_MAX_SIZE_MB patching for lazy settings imports in cache eviction tests"
  - "freezegun for time-dependent cache expiry tests"
metrics:
  duration: 383s
  completed: 2026-02-16
---

# Phase 5 Plan 1: Unit Test Infrastructure and Core Tests Summary

63 unit tests across 4 test files covering cache CRUD/expiry/recovery, exception hierarchy routing, API response validation/coercion, and adaptive worker scaling with >70% coverage on all tested modules.

## What Was Built

### Task 1: Test Infrastructure (5a5a8ac)

Set up complete pytest infrastructure:

- **pyproject.toml**: pytest configuration with 5 custom markers (unit, integration, asyncio, concurrent, slow), asyncio_mode=auto, pythonpath=["src"], strict-markers, coverage settings
- **requirements-dev.txt**: pytest>=8.0.0, pytest-asyncio, pytest-mock, pytest-cov, freezegun, httpx, responses
- **tests/conftest.py**: 4 shared fixtures -- temp_cache_dir (TemporaryDirectory), cache_config (short TTLs), research_cache (ResearchCache instance), reset_cache_singleton (autouse cleanup)
- **tests/fixtures/sample_data.py**: 3 factory functions -- make_discovery_suburb(), make_research_response(), make_suburb_metrics()
- **tests/fixtures/mock_responses.py**: 5 canned responses -- VALID_DISCOVERY_RESPONSE, MALFORMED_DISCOVERY_RESPONSE, VALID_RESEARCH_RESPONSE, PARTIAL_RESEARCH_RESPONSE, INVALID_RESEARCH_RESPONSE

### Task 2: Unit Tests (1630026)

63 unit tests across 4 files:

**test_cache.py (16 tests)**:
- CRUD: put/get, get missing key, put overwrites existing
- Expiry: freezegun-based TTL expiry verification
- Invalidation: existing and nonexistent key handling
- Clear: clear all, clear by type
- Stats: correct counting of discovery/research entries
- Recovery: backup index recovery from corrupted main index
- Orphan cleanup: stray file deletion on cache initialization
- LRU eviction: size-limited cache evicts oldest-accessed entries
- Atomic write: file creation with correct content
- Key generation: deterministic hashing, different inputs produce different keys
- Price bucketing: 475k->500k, 525k->500k, 550k->550k
- Disabled cache: put/get returns None when disabled

**test_exceptions.py (18 tests)**:
- Metadata: ApplicationError carries error_code, retry_after, is_transient, provider
- Permanent errors: PermanentError.is_transient=False, ValidationError.field, AuthenticationError.provider
- Transient errors: RateLimitError.retry_after=60, TimeoutError.timeout_seconds, APIError.status_code
- CacheError: operation attribute
- Convenience tuples: TRANSIENT_ERRORS and PERMANENT_ERRORS contain correct types
- isinstance routing (parametrized): 7 error types correctly classified as TransientError or PermanentError
- String representation: str() returns message only

**test_validation.py (21 tests)**:
- coerce_numeric: 8 tests covering string int/float, None, empty string, invalid string, passthrough int/float, zero
- Discovery validation: valid response, string price coercion, missing required field, invalid state, empty list, mixed valid/invalid
- Research validation: valid response, partial response (only required fields), missing identification raises, missing median_price raises, string price coercion, string growth projection key coercion, data quality default

**test_worker_scaling.py (8 tests)**:
- Overrides: discovery=4, research=3, minimum 1 from 0
- Caps: 100 CPUs still respects MAX_DISCOVERY_WORKERS(8)/MAX_RESEARCH_WORKERS(6)
- CPU detection: fallback to os.cpu_count(), cgroup v2 parsing (200000/100000=2), cgroup v2 unlimited (max)
- Memory scaling: 4GB available caps workers to 4

## Coverage Results

| Module | Coverage | Missing Lines |
|--------|----------|---------------|
| research/cache.py | 81% | Error recovery paths, singleton factory |
| security/exceptions.py | 98% | ResearchError init |
| research/validation.py | 98% | coerce_numeric edge case, validator fallbacks |
| config/worker_scaling.py | 92% | psutil ImportError path |
| config/cpu_detection.py | 72% | cgroup v1 parsing, logging branches |
| **TOTAL** | **87%** | |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mock paths for lazy imports**
- **Found during:** Task 2 (initial test run)
- **Issue:** worker_scaling.py uses `from src.config.cpu_detection import detect_cpu_limit` (with src. prefix) and `import psutil` inside function body. cache.py uses `from config import settings` lazily. Patching `config.worker_scaling.detect_cpu_limit` and `research.cache.settings` failed because these are not module-level attributes.
- **Fix:** Used `patch("src.config.cpu_detection.detect_cpu_limit")` for cpu_detection, `patch.dict(sys.modules, {"psutil": mock})` for psutil lazy import, and `patch("config.settings.CACHE_MAX_SIZE_MB")` for cache settings.
- **Files modified:** tests/unit/test_worker_scaling.py, tests/unit/test_cache.py
- **Commit:** 1630026

## Self-Check: PASSED

All created files verified to exist:
- pyproject.toml: FOUND
- requirements-dev.txt: FOUND
- tests/conftest.py: FOUND
- tests/unit/test_cache.py: FOUND
- tests/unit/test_exceptions.py: FOUND
- tests/unit/test_validation.py: FOUND
- tests/unit/test_worker_scaling.py: FOUND
- tests/fixtures/sample_data.py: FOUND
- tests/fixtures/mock_responses.py: FOUND

All commits verified:
- 5a5a8ac: FOUND
- 1630026: FOUND
