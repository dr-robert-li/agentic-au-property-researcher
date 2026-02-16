"""
Integration tests for the discovery-to-ranking pipeline.

Tests the full flow from suburb discovery through validation to ranking,
with mocked Perplexity/Anthropic API calls. No real network requests.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from tests.fixtures.mock_responses import (
    VALID_DISCOVERY_RESPONSE,
    VALID_RESEARCH_RESPONSE,
    MALFORMED_DISCOVERY_RESPONSE,
)
from tests.fixtures.sample_data import make_research_response
from models.suburb_metrics import (
    SuburbMetrics,
    SuburbIdentification,
    MarketMetricsCurrent,
    GrowthProjections,
)
from models.run_result import SuburbReport
from research.ranking import rank_suburbs, filter_by_criteria
from research.validation import validate_discovery_response


def _make_metrics(name: str, state: str, median_price: float,
                  growth_score: float, risk_score: float = 30.0,
                  composite_score: float = None,
                  data_quality: str = "high") -> SuburbMetrics:
    """Helper to build SuburbMetrics with specific scores."""
    if composite_score is None:
        composite_score = growth_score
    return SuburbMetrics(
        identification=SuburbIdentification(
            name=name, state=state, lga="TestLGA", region="TestRegion"
        ),
        market_current=MarketMetricsCurrent(median_price=median_price),
        growth_projections=GrowthProjections(
            growth_score=growth_score,
            risk_score=risk_score,
            composite_score=composite_score,
        ),
        data_quality=data_quality,
    )


def _mock_cache():
    """Return a mock cache that always misses."""
    cache = MagicMock()
    cache.get.return_value = None
    cache.put.return_value = None
    cache.invalidate.return_value = True
    return cache


# ---------------------------------------------------------------------------
# Discovery integration
# ---------------------------------------------------------------------------

@pytest.mark.integration
@patch("research.suburb_discovery.get_cache")
@patch("research.suburb_discovery.get_client")
def test_discovery_returns_suburbs(mock_get_client, mock_get_cache):
    """Discovery returns valid suburb candidates from mocked API."""
    from research.suburb_discovery import discover_suburbs
    from models.inputs import UserInput

    # Set up mock cache (miss)
    mock_get_cache.return_value = _mock_cache()

    # Set up mock client
    mock_client = MagicMock()
    mock_client.call_deep_research.return_value = json.dumps(VALID_DISCOVERY_RESPONSE)
    mock_client.parse_json_response.return_value = VALID_DISCOVERY_RESPONSE
    mock_get_client.return_value = mock_client

    user_input = UserInput(
        max_median_price=600000,
        dwelling_type="house",
        regions=["Queensland"],
        num_suburbs=5,
        run_id="2026-02-16_00-00-00",
    )

    candidates = discover_suburbs(user_input)

    # Should return list of SuburbCandidate objects
    assert len(candidates) > 0
    for c in candidates:
        assert hasattr(c, "name")
        assert hasattr(c, "state")
        assert hasattr(c, "median_price")
        assert c.median_price <= 600000
        assert c.median_price > 0


# ---------------------------------------------------------------------------
# Research integration
# ---------------------------------------------------------------------------

@pytest.mark.integration
@patch("research.suburb_research.get_cache")
@patch("research.suburb_research.get_client")
def test_research_suburb_returns_metrics(mock_get_client, mock_get_cache):
    """Research returns SuburbMetrics from mocked API."""
    from research.suburb_research import research_suburb
    from research.suburb_discovery import SuburbCandidate

    mock_get_cache.return_value = _mock_cache()

    mock_client = MagicMock()
    mock_client.call_deep_research.return_value = json.dumps(VALID_RESEARCH_RESPONSE)
    mock_client.parse_json_response.return_value = VALID_RESEARCH_RESPONSE
    mock_get_client.return_value = mock_client

    candidate = SuburbCandidate({
        "name": "Acacia Ridge",
        "state": "QLD",
        "lga": "Brisbane",
        "region": "South East Queensland",
        "median_price": 550000,
        "growth_signals": ["Olympics"],
        "data_quality": "high",
    })

    metrics = research_suburb(candidate, dwelling_type="house", max_price=600000)

    assert isinstance(metrics, SuburbMetrics)
    assert metrics.identification.name == "Acacia Ridge"
    assert metrics.market_current.median_price > 0


# ---------------------------------------------------------------------------
# Ranking integration
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_ranking_produces_ordered_reports():
    """Ranking returns correctly ordered SuburbReport objects."""
    metrics_list = [
        _make_metrics("SuburbA", "QLD", 500000, growth_score=80, composite_score=80),
        _make_metrics("SuburbB", "QLD", 450000, growth_score=60, composite_score=60),
        _make_metrics("SuburbC", "QLD", 520000, growth_score=90, composite_score=90),
        _make_metrics("SuburbD", "QLD", 480000, growth_score=70, composite_score=70),
        _make_metrics("SuburbE", "QLD", 400000, growth_score=50, composite_score=50),
    ]

    reports = rank_suburbs(metrics_list, ranking_method="growth_score", top_n=3)

    assert len(reports) == 3
    assert all(isinstance(r, SuburbReport) for r in reports)
    # Should be ordered descending: 90, 80, 70
    assert reports[0].metrics.growth_projections.growth_score == 90
    assert reports[1].metrics.growth_projections.growth_score == 80
    assert reports[2].metrics.growth_projections.growth_score == 70
    # Ranks assigned correctly
    assert reports[0].rank == 1
    assert reports[1].rank == 2
    assert reports[2].rank == 3


@pytest.mark.integration
def test_quality_adjusted_ranking():
    """Quality-adjusted ranking penalizes low-quality data correctly."""
    # growth_score=90, quality=low  -> 90 * 0.85 = 76.5
    # growth_score=80, quality=high -> 80 * 1.0  = 80.0
    low_quality = _make_metrics(
        "LowQ", "QLD", 500000,
        growth_score=90, composite_score=90,
        data_quality="low",
    )
    high_quality = _make_metrics(
        "HighQ", "QLD", 500000,
        growth_score=80, composite_score=80,
        data_quality="high",
    )

    reports = rank_suburbs(
        [low_quality, high_quality],
        ranking_method="quality_adjusted",
    )

    assert len(reports) == 2
    # High quality suburb should rank first (80 > 76.5)
    assert reports[0].metrics.identification.name == "HighQ"
    assert reports[1].metrics.identification.name == "LowQ"


@pytest.mark.integration
def test_ranking_empty_list():
    """Ranking an empty list returns empty list."""
    reports = rank_suburbs([])
    assert reports == []


@pytest.mark.integration
def test_filter_by_criteria():
    """Filter correctly restricts by price and state."""
    metrics_list = [
        _make_metrics("A", "QLD", 500000, growth_score=80),
        _make_metrics("B", "NSW", 450000, growth_score=70),
        _make_metrics("C", "QLD", 700000, growth_score=90),
        _make_metrics("D", "VIC", 400000, growth_score=60),
        _make_metrics("E", "QLD", 550000, growth_score=75),
    ]

    filtered = filter_by_criteria(
        metrics_list,
        max_price=600000,
        states=["QLD"],
    )

    assert len(filtered) == 2
    names = {m.identification.name for m in filtered}
    assert names == {"A", "E"}
    # C is QLD but price > 600000, B is NSW, D is VIC
    for m in filtered:
        assert m.market_current.median_price <= 600000
        assert m.identification.state == "QLD"


# ---------------------------------------------------------------------------
# Validation wired into discovery
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_validation_wired_into_discovery():
    """Validation correctly separates valid from invalid discovery entries."""
    result = validate_discovery_response(MALFORMED_DISCOVERY_RESPONSE)

    # MALFORMED has: StringPrice (valid after coercion), empty name (invalid),
    # missing name (invalid), InvalidState (invalid)
    # Only StringPrice should survive
    assert result.is_valid  # At least one valid
    assert len(result.data) == 1
    assert result.data[0]["name"] == "StringPrice"
    assert result.data[0]["median_price"] == 500000  # coerced from string
    assert len(result.warnings) > 0  # warnings for the invalid ones
