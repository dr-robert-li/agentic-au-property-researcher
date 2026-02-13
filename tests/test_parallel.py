"""
Unit tests for parallel pipeline functionality (v1.7.0).

Tests cover:
- AccountErrorSignal thread-safe error propagation
- parallel_discover_suburbs() multi-region discovery
- parallel_research_suburbs() concurrent research
- Cache thread safety under concurrent access
"""
import sys
import threading
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from research.suburb_discovery import (
    AccountErrorSignal, SuburbCandidate,
    parallel_discover_suburbs, discover_suburbs,
)
from research.suburb_research import (
    parallel_research_suburbs, _create_fallback_metrics,
    API_ACCOUNT_ERRORS, API_TRANSIENT_ERRORS,
)
from research.perplexity_client import PerplexityRateLimitError, PerplexityAuthError
from research.anthropic_client import AnthropicRateLimitError
from research.cache import ResearchCache, CacheConfig
from models.suburb_metrics import (
    SuburbMetrics, SuburbIdentification, MarketMetricsCurrent,
    GrowthProjections,
)


# ============================================================
# Test helpers
# ============================================================

def make_candidate(name="TestSuburb", state="QLD", price=500000):
    """Create a SuburbCandidate from a dict."""
    return SuburbCandidate({
        "name": name,
        "state": state,
        "lga": "Test LGA",
        "region": "Test Region",
        "median_price": price,
        "growth_signals": ["test signal"],
        "major_events_relevance": "",
        "data_quality": "high",
    })


def make_metrics(name="TestSuburb", state="QLD", price=500000, score=75.0):
    """Create a mock SuburbMetrics object."""
    return SuburbMetrics(
        identification=SuburbIdentification(name=name, state=state, lga="Test", region="Test"),
        market_current=MarketMetricsCurrent(median_price=price),
        growth_projections=GrowthProjections(
            projected_growth_pct={1: 5, 2: 10, 3: 15, 5: 25, 10: 50, 25: 100},
            growth_score=score,
            risk_score=30.0,
            composite_score=score,
        ),
    )


def make_user_input(regions=None, price=700000, dwelling="house", num_suburbs=5, provider="perplexity"):
    """Create a UserInput object."""
    from models.inputs import UserInput
    return UserInput(
        max_median_price=price,
        dwelling_type=dwelling,
        regions=regions or ["South East Queensland"],
        num_suburbs=num_suburbs,
        provider=provider,
        run_id="test-run",
        interface_mode="cli",
    )


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


# ============================================================
# AccountErrorSignal tests
# ============================================================

def test_account_error_signal_initial_state():
    """Signal starts with no error."""
    signal = AccountErrorSignal()
    assert not signal.is_set, "Should not be set initially"
    assert signal.error is None, "Error should be None initially"
    print("  \u2713 AccountErrorSignal initial state correct")


def test_account_error_signal_set():
    """Setting an error makes is_set True."""
    signal = AccountErrorSignal()
    err = PerplexityRateLimitError("rate limited")
    signal.set(err)
    assert signal.is_set, "Should be set after set()"
    assert signal.error is err, "Should return the exact error"
    print("  \u2713 AccountErrorSignal set works")


def test_account_error_signal_first_wins():
    """Only the first error is stored; subsequent calls are ignored."""
    signal = AccountErrorSignal()
    err1 = PerplexityRateLimitError("first")
    err2 = PerplexityAuthError("second")
    signal.set(err1)
    signal.set(err2)
    assert signal.error is err1, "First error should win"
    assert signal.error is not err2, "Second error should be ignored"
    print("  \u2713 AccountErrorSignal first-error-wins correct")


# ============================================================
# Parallel discovery tests
# ============================================================

def test_parallel_discovery_single_region_delegates():
    """Single region calls discover_suburbs() directly (no threading)."""
    user_input = make_user_input(regions=["South East Queensland"])
    expected = [make_candidate("Sub1"), make_candidate("Sub2")]

    with patch("research.suburb_discovery.discover_suburbs", return_value=expected) as mock_ds:
        result = parallel_discover_suburbs(user_input, max_results=10)

    mock_ds.assert_called_once_with(user_input, max_results=10)
    assert len(result) == 2
    print("  \u2713 Single region delegates to discover_suburbs()")


def test_parallel_discovery_multi_region():
    """Multi-region runs per-region calls and merges results."""
    user_input = make_user_input(regions=["South East Queensland", "Northern NSW"])
    seq_results = [make_candidate("Sub1", "QLD"), make_candidate("Sub2", "NSW")]

    with patch("research.suburb_discovery._discover_for_single_region") as mock_fn:
        mock_fn.side_effect = [
            [make_candidate("Sub1", "QLD", 400000)],
            [make_candidate("Sub2", "NSW", 500000)],
        ]
        result = parallel_discover_suburbs(user_input, max_results=20)

    assert len(result) == 2, f"Expected 2 suburbs, got {len(result)}"
    names = {c.name for c in result}
    assert "Sub1" in names and "Sub2" in names
    print("  \u2713 Multi-region merges results from all regions")


def test_parallel_discovery_deduplication():
    """Duplicate suburbs (same name+state) are deduplicated."""
    user_input = make_user_input(regions=["Region A", "Region B"])

    with patch("research.suburb_discovery._discover_for_single_region") as mock_fn:
        mock_fn.side_effect = [
            [make_candidate("Springfield", "QLD", 400000)],
            [make_candidate("Springfield", "QLD", 410000)],  # duplicate
        ]
        result = parallel_discover_suburbs(user_input, max_results=20)

    assert len(result) == 1, f"Expected 1 deduplicated suburb, got {len(result)}"
    print("  \u2713 Deduplication by (name, state) works")


def test_parallel_discovery_all_australia_splits():
    """'All Australia' splits into individual state calls."""
    user_input = make_user_input(regions=["All Australia"])

    with patch("research.suburb_discovery._discover_for_single_region", return_value=[]) as mock_fn:
        result = parallel_discover_suburbs(user_input, max_results=20)

    # AUSTRALIAN_STATES has 8 entries
    assert mock_fn.call_count == 8, f"Expected 8 state calls, got {mock_fn.call_count}"
    print("  \u2713 'All Australia' splits into 8 state calls")


def test_parallel_discovery_partial_failure():
    """Partial region failure still returns results from successful regions."""
    user_input = make_user_input(regions=["Region A", "Region B"])

    with patch("research.suburb_discovery._discover_for_single_region") as mock_fn:
        mock_fn.side_effect = [
            [make_candidate("Sub1", "QLD", 400000)],
            Exception("Region B failed"),
        ]
        result = parallel_discover_suburbs(user_input, max_results=20)

    assert len(result) == 1, f"Expected 1 suburb from successful region, got {len(result)}"
    assert result[0].name == "Sub1"
    print("  \u2713 Partial region failure preserves successful results")


# ============================================================
# Parallel research tests
# ============================================================

def test_parallel_research_all_succeed():
    """All suburbs succeed -> all results returned."""
    candidates = [make_candidate(f"Sub{i}", "QLD", 400000 + i * 10000) for i in range(4)]

    with patch("research.suburb_research.research_suburb") as mock_rs:
        mock_rs.side_effect = [
            make_metrics(f"Sub{i}", "QLD", 400000 + i * 10000, 70 + i)
            for i in range(4)
        ]
        result = parallel_research_suburbs(
            candidates, "house", 700000, max_workers=2
        )

    assert len(result) == 4, f"Expected 4 results, got {len(result)}"
    print("  \u2713 All suburbs succeed -> all results returned")


def test_parallel_research_order_preserved():
    """Results are returned in original candidate order."""
    candidates = [
        make_candidate("Alpha", "QLD", 400000),
        make_candidate("Bravo", "NSW", 500000),
        make_candidate("Charlie", "VIC", 600000),
    ]

    with patch("research.suburb_research.research_suburb") as mock_rs:
        mock_rs.side_effect = [
            make_metrics("Alpha", "QLD", 400000, 80),
            make_metrics("Bravo", "NSW", 500000, 70),
            make_metrics("Charlie", "VIC", 600000, 60),
        ]
        result = parallel_research_suburbs(
            candidates, "house", 700000, max_workers=1  # 1 worker ensures sequential execution
        )

    names = [r.identification.name for r in result]
    assert names == ["Alpha", "Bravo", "Charlie"], f"Order wrong: {names}"
    print("  \u2713 Order preserved in results")


def test_parallel_research_transient_failure_uses_fallback():
    """Transient failure uses fallback metrics, doesn't discard slot."""
    candidates = [
        make_candidate("GoodSub", "QLD", 400000),
        make_candidate("BadSub", "NSW", 500000),
    ]

    from research.perplexity_client import PerplexityAPIError

    with patch("research.suburb_research.research_suburb") as mock_rs:
        mock_rs.side_effect = [
            make_metrics("GoodSub", "QLD", 400000, 80),
            PerplexityAPIError("timeout"),
        ]
        result = parallel_research_suburbs(
            candidates, "house", 700000, max_workers=1
        )

    assert len(result) == 2, f"Expected 2 results (1 real + 1 fallback), got {len(result)}"
    assert result[0].identification.name == "GoodSub"
    # Fallback has composite_score of 50.0
    assert result[1].growth_projections.composite_score == 50.0
    print("  \u2713 Transient failure uses fallback, slot preserved")


def test_parallel_research_account_error_partial_results():
    """Account error stops workers but returns partial results (not raised)."""
    candidates = [
        make_candidate("Sub1", "QLD", 400000),
        make_candidate("Sub2", "NSW", 500000),
        make_candidate("Sub3", "VIC", 600000),
    ]

    with patch("research.suburb_research.research_suburb") as mock_rs:
        mock_rs.side_effect = [
            make_metrics("Sub1", "QLD", 400000, 80),
            PerplexityRateLimitError("rate limited"),
            make_metrics("Sub3", "VIC", 600000, 60),  # may or may not run
        ]
        # Should NOT raise — returns partial results
        result = parallel_research_suburbs(
            candidates, "house", 700000, max_workers=1  # sequential to control order
        )

    # At least Sub1 should be in results
    assert len(result) >= 1, f"Expected at least 1 partial result, got {len(result)}"
    assert result[0].identification.name == "Sub1"
    print("  \u2713 Account error returns partial results (not raised)")


# ============================================================
# Cache thread safety tests
# ============================================================

def test_cache_concurrent_writes():
    """Concurrent writes to cache don't corrupt the index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        errors = []

        def writer(thread_id):
            try:
                for i in range(20):
                    cache.put("research", {"data": f"t{thread_id}_i{i}"},
                              suburb_name=f"sub_{thread_id}_{i}", state="QLD")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent writes caused errors: {errors}"

        # Verify index is valid JSON and has correct count
        stats = cache.stats()
        assert stats["total_entries"] == 100, f"Expected 100 entries, got {stats['total_entries']}"
        print("  \u2713 Concurrent writes don't corrupt index")


def test_cache_concurrent_read_write():
    """Concurrent read+write doesn't crash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = make_cache(tmpdir)
        # Pre-populate some entries
        for i in range(10):
            cache.put("research", {"data": i}, suburb_name=f"pre_{i}", state="QLD")

        errors = []

        def writer():
            try:
                for i in range(20):
                    cache.put("research", {"data": f"new_{i}"},
                              suburb_name=f"new_{i}", state="QLD")
            except Exception as e:
                errors.append(("writer", e))

        def reader():
            try:
                for i in range(20):
                    cache.get("research", suburb_name=f"pre_{i % 10}", state="QLD")
                    cache.stats()
            except Exception as e:
                errors.append(("reader", e))

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent read/write caused errors: {errors}"
        print("  \u2713 Concurrent read+write doesn't crash")


# ============================================================
# Runner
# ============================================================

def run_tests():
    """Run all tests and report results."""
    tests = [
        # AccountErrorSignal
        test_account_error_signal_initial_state,
        test_account_error_signal_set,
        test_account_error_signal_first_wins,
        # Parallel discovery
        test_parallel_discovery_single_region_delegates,
        test_parallel_discovery_multi_region,
        test_parallel_discovery_deduplication,
        test_parallel_discovery_all_australia_splits,
        test_parallel_discovery_partial_failure,
        # Parallel research
        test_parallel_research_all_succeed,
        test_parallel_research_order_preserved,
        test_parallel_research_transient_failure_uses_fallback,
        test_parallel_research_account_error_partial_results,
        # Cache thread safety
        test_cache_concurrent_writes,
        test_cache_concurrent_read_write,
    ]

    passed = 0
    failed = 0

    print("\n" + "=" * 60)
    print("Parallel Pipeline Tests (v1.7.0)")
    print("=" * 60)

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  \u2717 {test.__name__}: {e}")

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'='*60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
