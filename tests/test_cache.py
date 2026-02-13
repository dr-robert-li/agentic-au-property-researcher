"""
Unit tests for the research cache module (src/research/cache.py).

Tests cover:
- Cache creation and directory management
- Key generation (deterministic, price bucketing)
- Put/get operations
- TTL expiration
- Invalidation and clearing
- Statistics
- Edge cases: corrupt index, missing data files, disabled cache
- Concurrent-safe index operations
"""
import json
import logging
import sys
import os
import tempfile
import time
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from research.cache import ResearchCache, CacheConfig, CacheEntry


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_cache(tmpdir, **overrides):
    """Create a ResearchCache with a temp directory."""
    defaults = dict(
        cache_dir=Path(tmpdir),
        discovery_ttl=86400,
        research_ttl=604800,
        enabled=True,
    )
    defaults.update(overrides)
    config = CacheConfig(**defaults)
    return ResearchCache(config)


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


# ─── Key Generation Tests ────────────────────────────────────────────────────

def test_make_key_deterministic():
    """Same inputs produce same key."""
    k1 = ResearchCache._make_key("research", suburb_name="test", state="qld")
    k2 = ResearchCache._make_key("research", suburb_name="test", state="qld")
    assert k1 == k2, f"Keys differ: {k1} != {k2}"


def test_make_key_different_for_different_inputs():
    """Different inputs produce different keys."""
    k1 = ResearchCache._make_key("research", suburb_name="test", state="qld")
    k2 = ResearchCache._make_key("research", suburb_name="other", state="qld")
    assert k1 != k2, "Keys should differ"


def test_make_key_order_independent():
    """Key parts order doesn't matter (sorted internally)."""
    k1 = ResearchCache._make_key("research", suburb_name="test", state="qld")
    k2 = ResearchCache._make_key("research", state="qld", suburb_name="test")
    assert k1 == k2, f"Keys should be order-independent: {k1} != {k2}"


def test_make_key_includes_cache_type():
    """Different cache types produce different keys."""
    k1 = ResearchCache._make_key("discovery", name="test")
    k2 = ResearchCache._make_key("research", name="test")
    assert k1 != k2, "Different cache types should produce different keys"


# ─── Price Bucketing Tests ───────────────────────────────────────────────────

def test_bucket_price_rounds_down():
    """Price below midpoint rounds down."""
    assert ResearchCache.bucket_price(620000) == 600000


def test_bucket_price_rounds_up():
    """Price above midpoint rounds up."""
    assert ResearchCache.bucket_price(680000) == 700000


def test_bucket_price_exact():
    """Exact bucket boundary stays unchanged."""
    assert ResearchCache.bucket_price(700000) == 700000


def test_bucket_price_midpoint():
    """Exact midpoint (650000) rounds to 650000 since 650000/50000=13.0 is exact."""
    result = ResearchCache.bucket_price(650000)
    assert result == 650000, f"Exact division should stay: {result}"


def test_bucket_price_custom_size():
    """Custom bucket size works."""
    assert ResearchCache.bucket_price(123000, bucket_size=100000) == 100000
    assert ResearchCache.bucket_price(180000, bucket_size=100000) == 200000


def test_bucket_price_zero():
    """Zero price returns zero."""
    assert ResearchCache.bucket_price(0) == 0


# ─── Put/Get Tests ───────────────────────────────────────────────────────────

def test_put_and_get():
    """Basic put then get retrieves data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        data = {"suburb": "Test", "price": 500000}
        cache.put("research", data, suburb_name="test", state="qld")
        result = cache.get("research", suburb_name="test", state="qld")
        assert result == data, f"Got {result}"


def test_get_missing_returns_none():
    """Get on empty cache returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        result = cache.get("research", suburb_name="nonexistent", state="qld")
        assert result is None, f"Expected None, got {result}"


def test_put_overwrites():
    """Second put with same key overwrites."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        cache.put("research", {"v": 1}, name="test")
        cache.put("research", {"v": 2}, name="test")
        result = cache.get("research", name="test")
        assert result == {"v": 2}, f"Got {result}"


def test_different_cache_types_independent():
    """Discovery and research caches are independent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        cache.put("discovery", {"type": "discovery"}, name="test")
        cache.put("research", {"type": "research"}, name="test")
        d = cache.get("discovery", name="test")
        r = cache.get("research", name="test")
        assert d["type"] == "discovery"
        assert r["type"] == "research"


def test_complex_data():
    """Cache handles complex nested data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        data = {
            "suburbs": [
                {"name": "A", "price": 500000, "growth": [1.0, 2.0, 3.0]},
                {"name": "B", "price": 600000, "growth": [2.0, 3.0, 4.0]},
            ],
            "metadata": {"query": "test", "timestamp": "2024-01-01"},
        }
        cache.put("discovery", data, query="test")
        result = cache.get("discovery", query="test")
        assert result == data


# ─── TTL / Expiration Tests ──────────────────────────────────────────────────

def test_expired_entry_returns_none():
    """Expired entries return None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir, research_ttl=1)  # 1 second TTL
        cache.put("research", {"v": 1}, name="test")
        time.sleep(1.1)
        result = cache.get("research", name="test")
        assert result is None, f"Expired entry should return None, got {result}"


def test_not_expired_returns_data():
    """Non-expired entries return data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir, research_ttl=3600)
        cache.put("research", {"v": 1}, name="test")
        result = cache.get("research", name="test")
        assert result == {"v": 1}


def test_discovery_ttl_separate():
    """Discovery and research have separate TTLs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir, discovery_ttl=1, research_ttl=3600)
        cache.put("discovery", {"v": "disc"}, name="test")
        cache.put("research", {"v": "res"}, name="test")
        time.sleep(1.1)
        d = cache.get("discovery", name="test")
        r = cache.get("research", name="test")
        assert d is None, "Discovery should be expired"
        assert r == {"v": "res"}, "Research should still be valid"


# ─── Invalidation Tests ─────────────────────────────────────────────────────

def test_invalidate_existing():
    """Invalidate removes an existing entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        cache.put("research", {"v": 1}, name="test")
        result = cache.invalidate("research", name="test")
        assert result is True
        assert cache.get("research", name="test") is None


def test_invalidate_nonexistent():
    """Invalidate on nonexistent key returns False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        result = cache.invalidate("research", name="nonexistent")
        assert result is False


def test_invalidate_removes_file():
    """Invalidate removes the data file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        cache.put("research", {"v": 1}, name="test")
        # Count JSON files (excluding index)
        files_before = [f for f in Path(tmpdir).glob("research_*.json")]
        assert len(files_before) == 1
        cache.invalidate("research", name="test")
        files_after = [f for f in Path(tmpdir).glob("research_*.json")]
        assert len(files_after) == 0


# ─── Clear Tests ─────────────────────────────────────────────────────────────

def test_clear_all():
    """Clear all removes all entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        cache.put("discovery", {"v": 1}, name="d1")
        cache.put("research", {"v": 2}, name="r1")
        cache.put("research", {"v": 3}, name="r2")
        count = cache.clear()
        assert count == 3, f"Expected 3 cleared, got {count}"
        assert cache.get("discovery", name="d1") is None
        assert cache.get("research", name="r1") is None


def test_clear_by_type():
    """Clear by type only removes that type."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        cache.put("discovery", {"v": 1}, name="d1")
        cache.put("research", {"v": 2}, name="r1")
        count = cache.clear("discovery")
        assert count == 1
        assert cache.get("discovery", name="d1") is None
        assert cache.get("research", name="r1") == {"v": 2}


def test_clear_empty_cache():
    """Clear on empty cache returns 0."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        count = cache.clear()
        assert count == 0


# ─── Stats Tests ─────────────────────────────────────────────────────────────

def test_stats_empty():
    """Stats on empty cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        stats = cache.stats()
        assert stats["discovery_count"] == 0
        assert stats["research_count"] == 0
        assert stats["total_entries"] == 0
        assert stats["expired_count"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["enabled"] is True


def test_stats_with_entries():
    """Stats with entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        cache.put("discovery", {"v": 1}, name="d1")
        cache.put("discovery", {"v": 2}, name="d2")
        cache.put("research", {"v": 3}, name="r1")
        stats = cache.stats()
        assert stats["discovery_count"] == 2
        assert stats["research_count"] == 1
        assert stats["total_entries"] == 3
        assert stats["total_size_bytes"] > 0
        assert stats["oldest_timestamp"] is not None
        assert stats["newest_timestamp"] is not None
        assert stats["oldest_timestamp"] <= stats["newest_timestamp"]


def test_stats_expired_count():
    """Stats counts expired entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir, research_ttl=1)
        cache.put("research", {"v": 1}, name="test")
        time.sleep(1.1)
        stats = cache.stats()
        assert stats["expired_count"] == 1


# ─── Edge Cases ──────────────────────────────────────────────────────────────

def test_disabled_cache_get_returns_none():
    """Disabled cache always returns None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir, enabled=False)
        cache.put("research", {"v": 1}, name="test")  # put is also no-op
        result = cache.get("research", name="test")
        assert result is None


def test_disabled_cache_put_is_noop():
    """Disabled cache put doesn't create files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir, enabled=False)
        cache.put("research", {"v": 1}, name="test")
        # No data files should exist
        files = [f for f in Path(tmpdir).glob("*.json") if f.name != "cache_index.json"]
        assert len(files) == 0


def test_corrupt_index_recovers():
    """Corrupt cache_index.json is handled gracefully."""
    cache_logger = logging.getLogger("research.cache")
    old_level = cache_logger.level
    cache_logger.setLevel(logging.CRITICAL)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "cache_index.json"
            index_path.write_text("{invalid json!!!}")
            cache = make_cache(tmpdir)
            # Should not crash, returns empty
            result = cache.get("research", name="test")
            assert result is None
            # Should be able to put after recovery
            cache.put("research", {"v": 1}, name="test")
            result = cache.get("research", name="test")
            assert result == {"v": 1}
    finally:
        cache_logger.setLevel(old_level)


def test_missing_data_file_cleanup():
    """Missing data file is cleaned up from index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        cache.put("research", {"v": 1}, name="test")
        # Delete the data file manually
        for f in Path(tmpdir).glob("research_*.json"):
            f.unlink()
        # Get should return None and clean up index
        result = cache.get("research", name="test")
        assert result is None


def test_unicode_key_parts():
    """Unicode in key parts works."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        cache.put("research", {"v": "unicode"}, suburb="Grünwald", state="Bayern")
        result = cache.get("research", suburb="Grünwald", state="Bayern")
        assert result == {"v": "unicode"}


def test_empty_string_key_parts():
    """Empty strings in key parts work."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        cache.put("research", {"v": 1}, name="", state="")
        result = cache.get("research", name="", state="")
        assert result == {"v": 1}


def test_large_data():
    """Large data can be cached."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        data = {"items": [{"name": f"suburb_{i}", "price": i * 1000} for i in range(100)]}
        cache.put("discovery", data, query="large")
        result = cache.get("discovery", query="large")
        assert len(result["items"]) == 100


def test_cache_dir_created():
    """Cache directory is created if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir) / "nested" / "cache"
        config = CacheConfig(cache_dir=cache_dir)
        cache = ResearchCache(config)
        assert cache_dir.exists()


def test_multiple_caches_same_dir():
    """Multiple cache instances on same dir are compatible."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache1 = make_cache(tmpdir)
        cache1.put("research", {"v": 1}, name="test")
        # Create second instance
        cache2 = make_cache(tmpdir)
        result = cache2.get("research", name="test")
        assert result == {"v": 1}


# ─── CacheEntry Tests ────────────────────────────────────────────────────────

def test_cache_entry_dataclass():
    """CacheEntry dataclass creation."""
    entry = CacheEntry(
        key_hash="abc123",
        filepath="research_abc123.json",
        created_at=time.time(),
        ttl_seconds=3600,
        cache_type="research",
        key_parts={"name": "test"},
    )
    assert entry.key_hash == "abc123"
    assert entry.cache_type == "research"


def test_is_expired_true():
    """is_expired returns True for expired entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        entry = CacheEntry(
            key_hash="test",
            filepath="test.json",
            created_at=time.time() - 100,
            ttl_seconds=50,
            cache_type="research",
        )
        assert cache._is_expired(entry) is True


def test_is_expired_false():
    """is_expired returns False for fresh entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        entry = CacheEntry(
            key_hash="test",
            filepath="test.json",
            created_at=time.time(),
            ttl_seconds=3600,
            cache_type="research",
        )
        assert cache._is_expired(entry) is False


# ─── Integration Tests ───────────────────────────────────────────────────────

def test_full_lifecycle():
    """Full cache lifecycle: put, get, invalidate, stats."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)

        # Put several entries
        cache.put("discovery", {"q": "disc1"}, query="q1")
        cache.put("research", {"s": "res1"}, suburb="a", state="qld")
        cache.put("research", {"s": "res2"}, suburb="b", state="nsw")

        # Verify gets
        assert cache.get("discovery", query="q1")["q"] == "disc1"
        assert cache.get("research", suburb="a", state="qld")["s"] == "res1"
        assert cache.get("research", suburb="b", state="nsw")["s"] == "res2"

        # Check stats
        stats = cache.stats()
        assert stats["total_entries"] == 3
        assert stats["discovery_count"] == 1
        assert stats["research_count"] == 2

        # Invalidate one
        cache.invalidate("research", suburb="a", state="qld")
        assert cache.get("research", suburb="a", state="qld") is None
        stats = cache.stats()
        assert stats["total_entries"] == 2

        # Clear research only
        cache.clear("research")
        stats = cache.stats()
        assert stats["research_count"] == 0
        assert stats["discovery_count"] == 1

        # Clear all
        cache.clear()
        stats = cache.stats()
        assert stats["total_entries"] == 0


def test_index_persistence():
    """Index survives cache object recreation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache1 = make_cache(tmpdir)
        cache1.put("research", {"v": 42}, name="persist")

        # Create new cache instance
        cache2 = make_cache(tmpdir)
        result = cache2.get("research", name="persist")
        assert result == {"v": 42}


# ─── Run All Tests ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("CACHE UNIT TESTS")
    print("=" * 60)

    tests = [
        # Key generation
        ("Key: deterministic", test_make_key_deterministic),
        ("Key: different inputs", test_make_key_different_for_different_inputs),
        ("Key: order independent", test_make_key_order_independent),
        ("Key: includes cache type", test_make_key_includes_cache_type),

        # Price bucketing
        ("Bucket: rounds down", test_bucket_price_rounds_down),
        ("Bucket: rounds up", test_bucket_price_rounds_up),
        ("Bucket: exact boundary", test_bucket_price_exact),
        ("Bucket: midpoint", test_bucket_price_midpoint),
        ("Bucket: custom size", test_bucket_price_custom_size),
        ("Bucket: zero", test_bucket_price_zero),

        # Put/Get
        ("Put/Get: basic", test_put_and_get),
        ("Put/Get: missing returns None", test_get_missing_returns_none),
        ("Put/Get: overwrite", test_put_overwrites),
        ("Put/Get: independent types", test_different_cache_types_independent),
        ("Put/Get: complex data", test_complex_data),

        # TTL
        ("TTL: expired returns None", test_expired_entry_returns_none),
        ("TTL: not expired returns data", test_not_expired_returns_data),
        ("TTL: separate per type", test_discovery_ttl_separate),

        # Invalidation
        ("Invalidate: existing", test_invalidate_existing),
        ("Invalidate: nonexistent", test_invalidate_nonexistent),
        ("Invalidate: removes file", test_invalidate_removes_file),

        # Clear
        ("Clear: all", test_clear_all),
        ("Clear: by type", test_clear_by_type),
        ("Clear: empty", test_clear_empty_cache),

        # Stats
        ("Stats: empty", test_stats_empty),
        ("Stats: with entries", test_stats_with_entries),
        ("Stats: expired count", test_stats_expired_count),

        # Edge cases
        ("Edge: disabled get", test_disabled_cache_get_returns_none),
        ("Edge: disabled put", test_disabled_cache_put_is_noop),
        ("Edge: corrupt index", test_corrupt_index_recovers),
        ("Edge: missing data file", test_missing_data_file_cleanup),
        ("Edge: unicode keys", test_unicode_key_parts),
        ("Edge: empty string keys", test_empty_string_key_parts),
        ("Edge: large data", test_large_data),
        ("Edge: dir created", test_cache_dir_created),
        ("Edge: multiple instances", test_multiple_caches_same_dir),

        # CacheEntry
        ("CacheEntry: creation", test_cache_entry_dataclass),
        ("CacheEntry: is_expired true", test_is_expired_true),
        ("CacheEntry: is_expired false", test_is_expired_false),

        # Integration
        ("Integration: full lifecycle", test_full_lifecycle),
        ("Integration: index persistence", test_index_persistence),
    ]

    print(f"\nRunning {len(tests)} tests...\n")

    for name, fn in tests:
        run_test(name, fn)

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    print(f"{'=' * 60}")

    if errors:
        print("\nFailed tests:")
        for name, tb in errors:
            print(f"\n--- {name} ---")
            print(tb)

    sys.exit(0 if failed == 0 else 1)
