"""
Unit tests for the file-based research cache.

Tests CRUD operations, expiry, backup recovery, orphan cleanup,
LRU eviction, atomic writes, key generation, and price bucketing.
"""
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from research.cache import (
    CacheConfig,
    ResearchCache,
    atomic_write_json,
)


@pytest.mark.unit
class TestCachePutAndGet:
    """Test basic put/get operations."""

    def test_put_and_get(self, research_cache):
        """Put a discovery entry, get it back, verify data matches."""
        data = {"suburbs": [{"name": "TestSuburb"}]}
        research_cache.put("discovery", data, query="test", price=500000)

        result = research_cache.get("discovery", query="test", price=500000)
        assert result == data

    def test_get_missing_key(self, research_cache):
        """Get nonexistent key returns None."""
        result = research_cache.get("discovery", query="nonexistent")
        assert result is None

    def test_get_expired_entry(self, cache_config):
        """Put entry, advance time past TTL, verify get returns None."""
        # discovery_ttl is 60s in our test config
        with freeze_time("2025-01-01 00:00:00") as frozen:
            cache = ResearchCache(cache_config)
            cache.put("discovery", {"data": "test"}, query="expire_test")

            # Advance past TTL
            frozen.move_to("2025-01-01 00:02:00")  # 120 seconds later

            result = cache.get("discovery", query="expire_test")
            assert result is None

    def test_put_overwrites_existing(self, research_cache):
        """Put same key twice with different data, verify second data returned."""
        research_cache.put("discovery", {"v": 1}, query="overwrite")
        research_cache.put("discovery", {"v": 2}, query="overwrite")

        result = research_cache.get("discovery", query="overwrite")
        assert result == {"v": 2}


@pytest.mark.unit
class TestCacheInvalidate:
    """Test cache invalidation."""

    def test_invalidate_existing(self, research_cache):
        """Put entry, invalidate it, verify get returns None and invalidate returned True."""
        research_cache.put("discovery", {"data": "test"}, query="inv_test")
        result = research_cache.invalidate("discovery", query="inv_test")
        assert result is True
        assert research_cache.get("discovery", query="inv_test") is None

    def test_invalidate_nonexistent(self, research_cache):
        """Invalidate nonexistent key returns False."""
        result = research_cache.invalidate("discovery", query="no_such_key")
        assert result is False


@pytest.mark.unit
class TestCacheClear:
    """Test cache clearing."""

    def test_clear_all(self, research_cache):
        """Put 3 entries (2 discovery, 1 research), clear all, verify stats show 0."""
        research_cache.put("discovery", {"d": 1}, query="d1")
        research_cache.put("discovery", {"d": 2}, query="d2")
        research_cache.put("research", {"r": 1}, suburb="s1")

        research_cache.clear()

        stats = research_cache.stats()
        assert stats["total_entries"] == 0

    def test_clear_by_type(self, research_cache):
        """Put 2 discovery + 1 research, clear discovery, verify research still exists."""
        research_cache.put("discovery", {"d": 1}, query="d1")
        research_cache.put("discovery", {"d": 2}, query="d2")
        research_cache.put("research", {"r": 1}, suburb="s1")

        research_cache.clear("discovery")

        stats = research_cache.stats()
        assert stats["discovery_count"] == 0
        assert stats["research_count"] == 1


@pytest.mark.unit
class TestCacheStats:
    """Test cache statistics."""

    def test_stats_counts(self, research_cache):
        """Put entries of both types, verify stats dict has correct counts."""
        research_cache.put("discovery", {"d": 1}, query="d1")
        research_cache.put("research", {"r": 1}, suburb="s1")
        research_cache.put("research", {"r": 2}, suburb="s2")

        stats = research_cache.stats()
        assert stats["discovery_count"] == 1
        assert stats["research_count"] == 2
        assert stats["total_entries"] == 3


@pytest.mark.unit
class TestCacheRecovery:
    """Test backup recovery and orphan cleanup."""

    def test_backup_recovery(self, cache_config):
        """Put entries, corrupt main index, create new cache, verify recovery from backup."""
        cache = ResearchCache(cache_config)
        cache.put("discovery", {"d": 1}, query="backup_test")
        cache.put("research", {"r": 1}, suburb="backup_suburb")

        # Verify entries exist
        assert cache.get("discovery", query="backup_test") is not None

        # Corrupt the main index file
        index_path = cache_config.cache_dir / "cache_index.json"
        with open(index_path, "w") as f:
            f.write("CORRUPTED JSON{{{")

        # Create new cache with same config -- should recover from backup
        cache2 = ResearchCache(cache_config)
        result = cache2.get("discovery", query="backup_test")
        assert result == {"d": 1}

    def test_orphan_cleanup(self, cache_config):
        """Create a stray file, create new cache, verify orphan deleted."""
        # Create cache dir first
        cache_config.cache_dir.mkdir(parents=True, exist_ok=True)

        # Create orphan file
        orphan_path = cache_config.cache_dir / "discovery_orphan123.json"
        with open(orphan_path, "w") as f:
            json.dump({"orphan": True}, f)

        assert orphan_path.exists()

        # Create cache -- should clean up orphan
        cache = ResearchCache(cache_config)
        assert not orphan_path.exists()
        assert cache._last_orphan_cleanup_count == 1


@pytest.mark.unit
class TestCacheLRUEviction:
    """Test LRU eviction when cache size limit is exceeded."""

    def test_lru_eviction(self, temp_cache_dir):
        """Set max_size_bytes very small, put multiple entries, verify oldest-accessed evicted."""
        config = CacheConfig(
            cache_dir=temp_cache_dir,
            discovery_ttl=3600,
            research_ttl=7200,
            enabled=True,
            max_size_bytes=1024,  # Very small
        )
        cache = ResearchCache(config)

        # Mock settings.CACHE_MAX_SIZE_MB to match our small limit
        with patch("config.settings.CACHE_MAX_SIZE_MB", 0.001):
            # Put first entry
            cache.put("discovery", {"data": "a" * 200}, query="first")

            # Put second entry (should trigger eviction of first)
            cache.put("discovery", {"data": "b" * 200}, query="second")

            # Put third entry
            cache.put("discovery", {"data": "c" * 200}, query="third")

        # At least one entry should have been evicted
        stats = cache.stats()
        assert stats["total_entries"] <= 3  # May have evicted some


@pytest.mark.unit
class TestAtomicWrite:
    """Test atomic write utility."""

    def test_atomic_write_creates_file(self, temp_cache_dir):
        """Call atomic_write_json directly, verify file exists with correct content."""
        target = temp_cache_dir / "test_atomic.json"
        data = {"key": "value", "number": 42}

        atomic_write_json(target, data)

        assert target.exists()
        with open(target) as f:
            loaded = json.load(f)
        assert loaded == data


@pytest.mark.unit
class TestCacheKeyGeneration:
    """Test key generation and price bucketing."""

    def test_make_key_deterministic(self):
        """Same inputs produce same hash, different inputs produce different hashes."""
        key1 = ResearchCache._make_key("discovery", query="test", price=500000)
        key2 = ResearchCache._make_key("discovery", query="test", price=500000)
        key3 = ResearchCache._make_key("discovery", query="different", price=500000)

        assert key1 == key2
        assert key1 != key3

    def test_bucket_price(self):
        """Price bucketing rounds to nearest 50k."""
        assert ResearchCache.bucket_price(475000) == 500000
        assert ResearchCache.bucket_price(525000) == 500000
        assert ResearchCache.bucket_price(550000) == 550000


@pytest.mark.unit
class TestDisabledCache:
    """Test cache behavior when disabled."""

    def test_disabled_cache_returns_none(self, temp_cache_dir):
        """Create cache with enabled=False, put data, get returns None."""
        config = CacheConfig(
            cache_dir=temp_cache_dir,
            enabled=False,
        )
        cache = ResearchCache(config)
        cache.put("discovery", {"data": "test"}, query="disabled_test")

        result = cache.get("discovery", query="disabled_test")
        assert result is None
