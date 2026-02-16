"""
Shared pytest fixtures for the test suite.

Provides:
- temp_cache_dir: Function-scoped temporary directory for cache tests
- cache_config: CacheConfig with temp dir and short TTLs
- research_cache: ResearchCache instance for testing
- reset_cache_singleton: Autouse fixture to reset singleton after each test
"""
import tempfile
from pathlib import Path

import pytest

from research.cache import CacheConfig, ResearchCache, reset_cache_instance


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache tests, cleaned up after each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def cache_config(temp_cache_dir):
    """CacheConfig with temp directory and short TTLs for testing."""
    return CacheConfig(
        cache_dir=temp_cache_dir,
        discovery_ttl=60,
        research_ttl=120,
        enabled=True,
        max_size_bytes=500 * 1024 * 1024,
    )


@pytest.fixture
def research_cache(cache_config):
    """ResearchCache instance for testing."""
    return ResearchCache(cache_config)


@pytest.fixture(autouse=True)
def reset_cache_singleton():
    """Reset the cache singleton after each test to avoid cross-test contamination."""
    yield
    reset_cache_instance()
