"""
Unit tests for pipeline resilience and progress callback functionality.
Tests the v1.4.0 changes: error type splitting, batch resilience, and progress visibility.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from types import SimpleNamespace

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from research.perplexity_client import (
    PerplexityRateLimitError, PerplexityAuthError, PerplexityAPIError
)
from research.anthropic_client import (
    AnthropicRateLimitError, AnthropicAuthError, AnthropicAPIError
)
from research.suburb_research import (
    API_ACCOUNT_ERRORS, API_TRANSIENT_ERRORS,
    batch_research_suburbs, _create_fallback_metrics
)
from research.suburb_discovery import SuburbCandidate


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
        "data_quality": "high"
    })


def make_metrics(name="TestSuburb", state="QLD", price=500000, score=75.0):
    """Create a mock SuburbMetrics-like object."""
    from models.suburb_metrics import (
        SuburbMetrics, SuburbIdentification, MarketMetricsCurrent,
        GrowthProjections
    )
    return SuburbMetrics(
        identification=SuburbIdentification(name=name, state=state, lga="Test", region="Test"),
        market_current=MarketMetricsCurrent(median_price=price),
        growth_projections=GrowthProjections(
            projected_growth_pct={1: 5, 2: 10, 3: 15, 5: 25, 10: 50, 25: 100},
            growth_score=score,
            risk_score=30.0,
            composite_score=score
        ),
    )


# ============================================================
# Test: Error type splitting
# ============================================================

def test_account_errors_tuple():
    """API_ACCOUNT_ERRORS includes auth and rate limit errors only."""
    assert PerplexityRateLimitError in API_ACCOUNT_ERRORS
    assert PerplexityAuthError in API_ACCOUNT_ERRORS
    assert AnthropicRateLimitError in API_ACCOUNT_ERRORS
    assert AnthropicAuthError in API_ACCOUNT_ERRORS
    # General API errors should NOT be in account errors
    assert PerplexityAPIError not in API_ACCOUNT_ERRORS
    assert AnthropicAPIError not in API_ACCOUNT_ERRORS
    print("  \u2713 Account errors tuple correct")


def test_transient_errors_tuple():
    """API_TRANSIENT_ERRORS includes general API errors only."""
    assert PerplexityAPIError in API_TRANSIENT_ERRORS
    assert AnthropicAPIError in API_TRANSIENT_ERRORS
    # Auth/rate limit errors should NOT be in transient
    assert PerplexityRateLimitError not in API_TRANSIENT_ERRORS
    assert PerplexityAuthError not in API_TRANSIENT_ERRORS
    assert AnthropicRateLimitError not in API_TRANSIENT_ERRORS
    assert AnthropicAuthError not in API_TRANSIENT_ERRORS
    print("  \u2713 Transient errors tuple correct")


def test_no_overlap_between_error_tuples():
    """No error type appears in both tuples."""
    overlap = set(API_ACCOUNT_ERRORS) & set(API_TRANSIENT_ERRORS)
    assert len(overlap) == 0, f"Overlapping errors: {overlap}"
    print("  \u2713 No overlap between error tuples")


# ============================================================
# Test: Batch resilience - transient errors don't stop batch
# ============================================================

def test_batch_continues_on_transient_api_error():
    """batch_research_suburbs continues when a PerplexityAPIError occurs."""
    candidates = [make_candidate(f"Sub{i}") for i in range(3)]
    metrics_ok = make_metrics("Sub0")

    call_count = 0

    def mock_research(candidate, dwelling_type, max_price, provider):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise PerplexityAPIError("Temporary server error")
        return make_metrics(candidate.name)

    with patch("research.suburb_research.research_suburb", side_effect=mock_research):
        results = batch_research_suburbs(candidates, "house", 700000, provider="perplexity")

    assert len(results) == 3, f"Expected 3 results (2 real + 1 fallback), got {len(results)}"
    assert call_count == 3, "All 3 suburbs should have been attempted"
    print("  \u2713 Batch continues on transient API error")


def test_batch_continues_on_anthropic_api_error():
    """batch_research_suburbs continues when an AnthropicAPIError occurs."""
    candidates = [make_candidate(f"Sub{i}") for i in range(3)]

    call_count = 0

    def mock_research(candidate, dwelling_type, max_price, provider):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise AnthropicAPIError("Service unavailable")
        return make_metrics(candidate.name)

    with patch("research.suburb_research.research_suburb", side_effect=mock_research):
        results = batch_research_suburbs(candidates, "house", 700000, provider="anthropic")

    assert len(results) == 3
    assert call_count == 3
    print("  \u2713 Batch continues on Anthropic API error")


def test_batch_stops_on_account_error_rate_limit():
    """batch_research_suburbs stops when a rate limit error occurs."""
    candidates = [make_candidate(f"Sub{i}") for i in range(3)]

    call_count = 0

    def mock_research(candidate, dwelling_type, max_price, provider):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise PerplexityRateLimitError("Rate limit exceeded")
        return make_metrics(candidate.name)

    with patch("research.suburb_research.research_suburb", side_effect=mock_research):
        try:
            results = batch_research_suburbs(candidates, "house", 700000, provider="perplexity")
            assert False, "Should have raised PerplexityRateLimitError"
        except PerplexityRateLimitError:
            pass  # Expected

    assert call_count == 2, "Should have stopped at suburb 2"
    print("  \u2713 Batch stops on rate limit error")


def test_batch_stops_on_account_error_auth():
    """batch_research_suburbs stops when an auth error occurs."""
    candidates = [make_candidate(f"Sub{i}") for i in range(3)]

    call_count = 0

    def mock_research(candidate, dwelling_type, max_price, provider):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise AnthropicAuthError("Invalid API key")
        return make_metrics(candidate.name)

    with patch("research.suburb_research.research_suburb", side_effect=mock_research):
        try:
            results = batch_research_suburbs(candidates, "house", 700000, provider="anthropic")
            assert False, "Should have raised AnthropicAuthError"
        except AnthropicAuthError:
            pass  # Expected

    assert call_count == 1, "Should have stopped at suburb 1"
    print("  \u2713 Batch stops on auth error")


def test_batch_continues_on_generic_exception():
    """batch_research_suburbs continues on non-API exceptions."""
    candidates = [make_candidate(f"Sub{i}") for i in range(3)]

    call_count = 0

    def mock_research(candidate, dwelling_type, max_price, provider):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ValueError("JSON parse error")
        return make_metrics(candidate.name)

    with patch("research.suburb_research.research_suburb", side_effect=mock_research):
        results = batch_research_suburbs(candidates, "house", 700000, provider="perplexity")

    assert len(results) == 3
    assert call_count == 3
    print("  \u2713 Batch continues on generic exception")


def test_batch_all_transient_errors():
    """batch_research_suburbs returns fallbacks for all suburbs if all hit transient errors."""
    candidates = [make_candidate(f"Sub{i}") for i in range(3)]

    def mock_research(candidate, dwelling_type, max_price, provider):
        raise PerplexityAPIError("Server error")

    with patch("research.suburb_research.research_suburb", side_effect=mock_research):
        results = batch_research_suburbs(candidates, "house", 700000, provider="perplexity")

    assert len(results) == 3, "Should return 3 fallback results"
    # All should be fallback metrics with default scores
    for r in results:
        assert r.growth_projections.composite_score == 50.0
    print("  \u2713 All transient errors produce fallback results")


def test_batch_max_suburbs_limits():
    """batch_research_suburbs respects max_suburbs parameter."""
    candidates = [make_candidate(f"Sub{i}") for i in range(10)]

    with patch("research.suburb_research.research_suburb", return_value=make_metrics()):
        results = batch_research_suburbs(candidates, "house", 700000, max_suburbs=3)

    assert len(results) == 3
    print("  \u2713 max_suburbs limits correctly")


# ============================================================
# Test: Progress callback
# ============================================================

def test_batch_calls_progress_callback():
    """batch_research_suburbs calls progress_callback for each suburb."""
    candidates = [make_candidate(f"Sub{i}") for i in range(3)]
    steps = []

    def callback(msg):
        steps.append(msg)

    with patch("research.suburb_research.research_suburb", return_value=make_metrics()):
        batch_research_suburbs(
            candidates, "house", 700000,
            provider="perplexity",
            progress_callback=callback
        )

    # Should have 2 messages per suburb: "Researching..." and "Research complete"
    assert len(steps) == 6, f"Expected 6 steps, got {len(steps)}: {steps}"
    assert "Researching suburb 1/3" in steps[0]
    assert "Research complete" in steps[1]
    assert "Researching suburb 2/3" in steps[2]
    assert "Research complete" in steps[3]
    print("  \u2713 Progress callback called per suburb")


def test_batch_callback_on_transient_error():
    """Progress callback reports fallback usage on transient errors."""
    candidates = [make_candidate("FailSub")]
    steps = []

    def mock_research(candidate, dwelling_type, max_price, provider):
        raise PerplexityAPIError("timeout")

    with patch("research.suburb_research.research_suburb", side_effect=mock_research):
        batch_research_suburbs(
            candidates, "house", 700000,
            provider="perplexity",
            progress_callback=lambda m: steps.append(m)
        )

    assert any("API error" in s for s in steps), f"Should report API error: {steps}"
    assert any("fallback" in s for s in steps), f"Should mention fallback: {steps}"
    print("  \u2713 Progress callback reports transient errors")


def test_batch_callback_on_account_error():
    """Progress callback reports fatal error before raising."""
    candidates = [make_candidate("FailSub")]
    steps = []

    def mock_research(candidate, dwelling_type, max_price, provider):
        raise PerplexityRateLimitError("credits exhausted")

    with patch("research.suburb_research.research_suburb", side_effect=mock_research):
        try:
            batch_research_suburbs(
                candidates, "house", 700000,
                provider="perplexity",
                progress_callback=lambda m: steps.append(m)
            )
        except PerplexityRateLimitError:
            pass

    assert any("FATAL" in s for s in steps), f"Should report fatal error: {steps}"
    print("  \u2713 Progress callback reports account errors before raise")


def test_batch_no_callback_works():
    """batch_research_suburbs works with progress_callback=None."""
    candidates = [make_candidate("Sub1")]

    with patch("research.suburb_research.research_suburb", return_value=make_metrics()):
        results = batch_research_suburbs(candidates, "house", 700000, progress_callback=None)

    assert len(results) == 1
    print("  \u2713 Works without callback (None)")


# ============================================================
# Test: Pipeline progress helper (_progress)
# ============================================================

def test_pipeline_progress_helper():
    """_progress calls both print and callback."""
    import inspect
    source_path = Path(__file__).parent.parent / "src" / "app.py"
    source = source_path.read_text()
    assert "progress_callback" in source, "run_research_pipeline should accept progress_callback"
    assert "def _progress" in source, "Should have _progress helper"
    assert "progress_callback(message)" in source or "progress_callback(msg)" in source, \
        "Should call callback in _progress"
    print("  \u2713 Pipeline accepts progress_callback with _progress helper")


# ============================================================
# Test: Fallback metrics
# ============================================================

def test_fallback_metrics_created():
    """_create_fallback_metrics returns valid SuburbMetrics."""
    candidate = make_candidate("FallbackSub", "NSW", 600000)
    metrics = _create_fallback_metrics(candidate)

    assert metrics.identification.name == "FallbackSub"
    assert metrics.identification.state == "NSW"
    assert metrics.market_current.median_price == 600000
    assert metrics.growth_projections.composite_score == 50.0
    assert metrics.growth_projections.growth_score == 50.0
    assert 5 in metrics.growth_projections.projected_growth_pct
    print("  \u2713 Fallback metrics created correctly")


def test_fallback_preserves_growth_signals():
    """Fallback metrics preserve growth_signals from candidate."""
    candidate = make_candidate("SigSub")
    metrics = _create_fallback_metrics(candidate)
    assert "test signal" in metrics.growth_projections.key_drivers
    print("  \u2713 Fallback preserves growth signals")


# ============================================================
# Test: Discovery price filter logging
# ============================================================

def test_discovery_price_filter_message(capsys=None):
    """Discovery logs when price filter removes candidates."""
    # This is a structural test - verify the logging code exists
    import inspect
    from research import suburb_discovery
    source = inspect.getsource(suburb_discovery.discover_suburbs)
    assert "pre_filter_count" in source, "Should track pre-filter count"
    assert "Price filter:" in source, "Should log price filter message"
    print("  \u2713 Discovery has price filter logging")


# ============================================================
# Test: Web server steps initialization
# ============================================================

def test_server_has_steps_in_active_runs():
    """Web server initializes steps list in active_runs."""
    source_path = Path(__file__).parent.parent / "src" / "ui" / "web" / "server.py"
    source = source_path.read_text()
    assert '"steps"' in source or "'steps'" in source, "start_run should initialize steps"
    assert "[]" in source, "steps should be initialized as empty list"
    print("  \u2713 Server initializes steps in active_runs")


def test_server_has_progress_callback():
    """Web server creates progress_callback in run_pipeline_background."""
    source_path = Path(__file__).parent.parent / "src" / "ui" / "web" / "server.py"
    source = source_path.read_text()
    assert "progress_callback" in source, "run_pipeline_background should create callback"
    assert "steps" in source, "Callback should append to steps"
    print("  \u2713 Server creates progress_callback")


# ============================================================
# Test: Multiplier changes
# ============================================================

def test_discovery_multiplier_increased():
    """Discovery uses 5x multiplier (not 3x)."""
    source_path = Path(__file__).parent.parent / "src" / "app.py"
    source = source_path.read_text()
    assert "num_suburbs * 5" in source, "Discovery should use 5x multiplier"
    print("  \u2713 Discovery multiplier is 5x")


def test_research_multiplier_increased():
    """Research uses 3x multiplier (not 2x)."""
    source_path = Path(__file__).parent.parent / "src" / "app.py"
    source = source_path.read_text()
    assert "num_suburbs * 3" in source, "Research should use 3x multiplier"
    print("  \u2713 Research multiplier is 3x")


# ============================================================
# Runner
# ============================================================

def run_tests():
    """Run all tests and report results."""
    tests = [
        # Error type splitting
        test_account_errors_tuple,
        test_transient_errors_tuple,
        test_no_overlap_between_error_tuples,
        # Batch resilience
        test_batch_continues_on_transient_api_error,
        test_batch_continues_on_anthropic_api_error,
        test_batch_stops_on_account_error_rate_limit,
        test_batch_stops_on_account_error_auth,
        test_batch_continues_on_generic_exception,
        test_batch_all_transient_errors,
        test_batch_max_suburbs_limits,
        # Progress callback
        test_batch_calls_progress_callback,
        test_batch_callback_on_transient_error,
        test_batch_callback_on_account_error,
        test_batch_no_callback_works,
        # Pipeline
        test_pipeline_progress_helper,
        # Fallback metrics
        test_fallback_metrics_created,
        test_fallback_preserves_growth_signals,
        # Discovery
        test_discovery_price_filter_message,
        # Server integration
        test_server_has_steps_in_active_runs,
        test_server_has_progress_callback,
        # Multipliers
        test_discovery_multiplier_increased,
        test_research_multiplier_increased,
    ]

    passed = 0
    failed = 0

    print("\n" + "=" * 60)
    print("Pipeline Resilience & Progress Callback Tests")
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
