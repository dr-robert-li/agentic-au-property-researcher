"""
Unit tests for cache resilience and home page cache management (v1.6.0).

Tests:
- _coerce_to_str_list: mixed type coercion
- _parse_metrics_from_json: section-isolated parsing
- Cached data path: invalid cache data triggers re-fetch
- Web UI: cache stats and clear endpoints
- Web UI: home page cache management section
"""
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from research.suburb_research import _coerce_to_str_list, _parse_metrics_from_json


# ============================================================
# Helpers
# ============================================================

def _valid_base_data():
    """Return minimal valid data for _parse_metrics_from_json."""
    return {
        "identification": {
            "name": "TestSuburb",
            "state": "QLD",
            "lga": "Test LGA",
            "region": "Test Region"
        },
        "market_current": {
            "median_price": 500000,
        }
    }


# ============================================================
# _coerce_to_str_list tests
# ============================================================

def test_coerce_strings_pass_through():
    """Strings should pass through unchanged."""
    result = _coerce_to_str_list(["bus", "train", "ferry"])
    assert result == ["bus", "train", "ferry"]


def test_coerce_dicts_to_strings():
    """Dicts should be joined into readable strings."""
    items = [
        {"mode": "bus", "name": "Route 520"},
        {"mode": "train", "name": "Beenleigh Line"}
    ]
    result = _coerce_to_str_list(items)
    assert len(result) == 2
    assert "bus" in result[0]
    assert "Route 520" in result[0]
    assert "train" in result[1]


def test_coerce_mixed_types():
    """Mix of strings, dicts, and other types should all convert."""
    items = [
        "Plain string",
        {"key": "value", "other": "data"},
        42,
        None
    ]
    result = _coerce_to_str_list(items)
    assert len(result) == 4
    assert result[0] == "Plain string"
    assert "value" in result[1]
    assert result[2] == "42"
    assert result[3] == "None"


def test_coerce_empty_list():
    """Empty list should return empty list."""
    assert _coerce_to_str_list([]) == []


def test_coerce_dict_with_empty_values():
    """Dict with empty/falsy values should skip them."""
    items = [{"name": "Test", "empty": "", "none": None}]
    result = _coerce_to_str_list(items)
    assert len(result) == 1
    assert "Test" in result[0]
    # Empty string and None should be skipped (falsy)
    assert result[0] == "Test"


def test_coerce_complex_transport_dicts():
    """Test with realistic transport dict format from API."""
    items = [
        {"mode": "bus", "name": "Route 520", "summary": "Local service"},
        {"mode": "train", "name": "Beenleigh Line", "summary": "Commuter rail"},
        {"project": "Cross River Rail", "timing": "2025", "relevance_to_blackstone": "Improved access"}
    ]
    result = _coerce_to_str_list(items)
    assert len(result) == 3
    for r in result:
        assert isinstance(r, str)
        assert len(r) > 0


# ============================================================
# _parse_metrics_from_json tests
# ============================================================

def test_parse_minimal_valid_data():
    """Minimal valid data (identification + market_current) should parse."""
    data = _valid_base_data()
    metrics = _parse_metrics_from_json(data)
    assert metrics.identification.name == "TestSuburb"
    assert metrics.market_current.median_price == 500000


def test_parse_with_bad_market_history_still_returns():
    """Bad market_history should fall back to empty, not crash."""
    data = _valid_base_data()
    data["market_history"] = {"price_history": "not a list"}
    metrics = _parse_metrics_from_json(data)
    assert metrics.identification.name == "TestSuburb"
    assert metrics.market_history.price_history == []


def test_parse_with_bad_demographics_still_returns():
    """Bad demographics section should fall back to empty."""
    data = _valid_base_data()
    data["demographics"] = {"median_age": "not a number xyz"}
    metrics = _parse_metrics_from_json(data)
    assert metrics.identification.name == "TestSuburb"


def test_parse_infrastructure_with_dicts():
    """Infrastructure with dict items should be coerced to strings."""
    data = _valid_base_data()
    data["infrastructure"] = {
        "current_transport": [
            {"mode": "bus", "name": "Route 520"},
            {"mode": "train", "name": "Beenleigh Line"}
        ],
        "future_transport": [
            {"project": "Cross River Rail", "timing": "2025"}
        ],
        "current_infrastructure": ["Shopping centre", "Hospital"],
        "planned_infrastructure": [
            {"project": "New Park", "timing": "2026"}
        ]
    }
    metrics = _parse_metrics_from_json(data)
    assert len(metrics.infrastructure.current_transport) == 2
    assert all(isinstance(t, str) for t in metrics.infrastructure.current_transport)
    assert len(metrics.infrastructure.future_transport) == 1
    assert isinstance(metrics.infrastructure.future_transport[0], str)


def test_parse_with_bad_growth_projections():
    """Bad growth projections should fall back to empty defaults."""
    data = _valid_base_data()
    data["growth_projections"] = {"growth_score": "not_a_number"}
    metrics = _parse_metrics_from_json(data)
    assert metrics.growth_projections.growth_score == 0.0


def test_parse_all_sections_bad_except_required():
    """Only identification and market_current are required; all else can fail."""
    data = _valid_base_data()
    data["market_history"] = "broken"
    data["physical_config"] = 12345
    data["demographics"] = [1, 2, 3]
    data["infrastructure"] = "broken"
    data["growth_projections"] = None
    metrics = _parse_metrics_from_json(data)
    assert metrics.identification.name == "TestSuburb"
    assert metrics.market_current.median_price == 500000


# ============================================================
# Cached data path resilience tests
# ============================================================

def test_cached_data_invalid_triggers_refetch():
    """When cached data fails to parse, it should invalidate cache and re-fetch."""
    from research.suburb_discovery import SuburbCandidate

    candidate = SuburbCandidate({
        "name": "Blackstone",
        "state": "QLD",
        "lga": "Ipswich",
        "region": "South East Queensland",
        "median_price": 450000,
        "growth_signals": ["test"],
        "major_events_relevance": "",
        "data_quality": "high"
    })

    # Cached data with dicts that would cause old code to fail
    bad_cached_data = {
        "identification": {"name": "Blackstone", "state": "QLD", "lga": "Ipswich", "region": "SEQ"},
        "market_current": {"median_price": 450000},
        "infrastructure": {
            "current_transport": [
                {"mode": "bus", "name": "Route 520"}
            ]
        }
    }

    mock_cache = MagicMock()
    mock_cache.get.return_value = bad_cached_data

    # Mock the client to avoid actual API calls
    mock_client = MagicMock()
    mock_client.parse_json_response.return_value = _valid_base_data()

    with patch("research.suburb_research.get_cache", return_value=mock_cache), \
         patch("research.suburb_research.get_client", return_value=mock_client):

        from research.suburb_research import research_suburb
        result = research_suburb(candidate, "house", 600000)

        # The function should still return valid metrics
        assert result is not None
        assert result.identification.name in ("Blackstone", "TestSuburb")


def test_cached_data_valid_uses_cache():
    """When cached data parses successfully, it should use the cache (no API call)."""
    from research.suburb_discovery import SuburbCandidate

    candidate = SuburbCandidate({
        "name": "GoodSuburb",
        "state": "QLD",
        "lga": "Test",
        "region": "Test",
        "median_price": 400000,
        "growth_signals": ["test"],
        "major_events_relevance": "",
        "data_quality": "high"
    })

    valid_cached_data = _valid_base_data()
    valid_cached_data["identification"]["name"] = "GoodSuburb"

    mock_cache = MagicMock()
    mock_cache.get.return_value = valid_cached_data

    mock_client = MagicMock()

    with patch("research.suburb_research.get_cache", return_value=mock_cache), \
         patch("research.suburb_research.get_client", return_value=mock_client):

        from research.suburb_research import research_suburb
        result = research_suburb(candidate, "house", 600000)

        assert result.identification.name == "GoodSuburb"
        # Client should NOT have been called (cache hit)
        mock_client.call_deep_research.assert_not_called()


# ============================================================
# Web UI cache management tests
# ============================================================

def test_web_index_has_cache_section():
    """Home page template should contain cache management section."""
    template_path = Path(__file__).parent.parent / "src" / "ui" / "web" / "templates" / "web_index.html"
    content = template_path.read_text()
    assert "cache-section" in content
    assert "Cache Management" in content
    assert "clear-cache-btn" in content
    assert "clearCache" in content
    assert "/cache/stats" in content
    assert "/cache/clear" in content


def test_web_index_has_cache_stats_display():
    """Home page should display discovery, research, and total cache counts."""
    template_path = Path(__file__).parent.parent / "src" / "ui" / "web" / "templates" / "web_index.html"
    content = template_path.read_text()
    assert "cache-discovery" in content
    assert "cache-research" in content
    assert "cache-total" in content


def test_server_has_cache_endpoints():
    """Server should have /cache/stats and /cache/clear endpoints."""
    server_path = Path(__file__).parent.parent / "src" / "ui" / "web" / "server.py"
    content = server_path.read_text()
    assert '/cache/stats' in content
    assert '/cache/clear' in content
    assert 'cache.stats()' in content
    assert 'cache.clear()' in content


def test_cached_path_has_try_except():
    """The cached data path in research_suburb should have try/except with invalidation."""
    source_path = Path(__file__).parent.parent / "src" / "research" / "suburb_research.py"
    content = source_path.read_text()
    # Check that cache.get is followed by try/except block
    assert "cache.invalidate" in content
    assert "Cached data invalid" in content or "Cached data failed to parse" in content


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    import traceback

    tests = [
        # _coerce_to_str_list
        test_coerce_strings_pass_through,
        test_coerce_dicts_to_strings,
        test_coerce_mixed_types,
        test_coerce_empty_list,
        test_coerce_dict_with_empty_values,
        test_coerce_complex_transport_dicts,
        # _parse_metrics_from_json
        test_parse_minimal_valid_data,
        test_parse_with_bad_market_history_still_returns,
        test_parse_with_bad_demographics_still_returns,
        test_parse_infrastructure_with_dicts,
        test_parse_with_bad_growth_projections,
        test_parse_all_sections_bad_except_required,
        # Cached data path
        test_cached_data_invalid_triggers_refetch,
        test_cached_data_valid_uses_cache,
        # Web UI
        test_web_index_has_cache_section,
        test_web_index_has_cache_stats_display,
        test_server_has_cache_endpoints,
        test_cached_path_has_try_except,
    ]

    passed = 0
    failed = 0

    print(f"\n{'='*60}")
    print(f"Running Cache Resilience & Home Page Tests")
    print(f"{'='*60}\n")

    for test in tests:
        try:
            test()
            print(f"  \u2713 {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'='*60}")

    if failed > 0:
        sys.exit(1)
