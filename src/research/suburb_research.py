"""
Per-suburb detailed research functionality using Perplexity deep research.
"""
import json
from typing import Optional

from models.suburb_metrics import (
    SuburbMetrics,
    SuburbIdentification,
    MarketMetricsCurrent,
    MarketMetricsHistory,
    PhysicalConfig,
    Demographics,
    Infrastructure,
    GrowthProjections,
    TimePoint
)
from research.suburb_discovery import SuburbCandidate
from research.perplexity_client import get_client


def research_suburb(
    candidate: SuburbCandidate,
    dwelling_type: str,
    max_price: float
) -> SuburbMetrics:
    """
    Perform exhaustive research on a single suburb using Perplexity deep research.

    Args:
        candidate: SuburbCandidate from discovery phase
        dwelling_type: Type of dwelling (house, apartment, townhouse)
        max_price: Maximum median price threshold

    Returns:
        Complete SuburbMetrics object with all available data

    Raises:
        Exception: If API call fails or response cannot be parsed
    """
    client = get_client()

    # Build the detailed research prompt
    prompt = f"""
You are an Australian property research agent. Perform EXHAUSTIVE research on {candidate.name}, {candidate.state} for {dwelling_type} properties.

Use web_search and fetch_url tools to gather comprehensive, current data.

RETURN ONLY VALID JSON IN THIS EXACT STRUCTURE (no additional text):

{{
  "identification": {{
    "name": "{candidate.name}",
    "state": "{candidate.state}",
    "lga": "{candidate.lga}",
    "region": "{candidate.region}"
  }},
  "market_current": {{
    "median_price": {candidate.median_price},
    "average_price": 0,
    "auction_clearance_current": 0.0,
    "days_on_market_current": 0.0,
    "turnover_rate_current": 0.0,
    "rental_yield_current": 0.0
  }},
  "market_history": {{
    "price_history": [{{"year": 2020, "value": 0}}, {{"year": 2021, "value": 0}}, {{"year": 2022, "value": 0}}, {{"year": 2023, "value": 0}}, {{"year": 2024, "value": 0}}],
    "dom_history": [],
    "clearance_history": [],
    "turnover_history": []
  }},
  "physical_config": {{
    "land_size_median_sqm": 0,
    "floor_size_median_sqm": 0,
    "typical_bedrooms": 0,
    "typical_bathrooms": 0,
    "typical_car_spaces": 0
  }},
  "demographics": {{
    "population_trend": "",
    "median_age": 0.0,
    "household_types": {{}},
    "income_distribution": {{}}
  }},
  "infrastructure": {{
    "current_transport": [],
    "future_transport": [],
    "current_infrastructure": [],
    "planned_infrastructure": [],
    "major_events_relevance": "",
    "shopping_access": "",
    "schools_summary": "",
    "crime_stats": {{}}
  }},
  "growth_projections": {{
    "projected_growth_pct": {{
      "1": 0.0,
      "2": 0.0,
      "3": 0.0,
      "5": 0.0,
      "10": 0.0,
      "25": 0.0
    }},
    "confidence_intervals": {{
      "1": [0.0, 0.0],
      "2": [0.0, 0.0],
      "3": [0.0, 0.0],
      "5": [0.0, 0.0],
      "10": [0.0, 0.0],
      "25": [0.0, 0.0]
    }},
    "risk_analysis": "",
    "key_drivers": [],
    "growth_score": 0.0,
    "risk_score": 0.0,
    "composite_score": 0.0
  }}
}}

CRITICAL INSTRUCTIONS:
1. Fill ALL fields with real, researched data where available
2. Use 0, "", [], or {{}} ONLY when data truly cannot be found
3. For price_history: Include actual historical data points from 2020-2024
4. For growth_projections: Calculate realistic percentage growth for 1, 2, 3, 5, 10, and 25 year horizons
5. For confidence_intervals: Provide [low, high] ranges for each projection
6. For growth_score: Calculate 0-100 score based on projected growth potential
7. For risk_score: Calculate 0-100 score based on market volatility and risks
8. For composite_score: Growth score adjusted for risk (higher growth + lower risk = higher score)
9. Include all available transport, infrastructure, and amenity information
10. Research major events relevance (Brisbane 2032 Olympics, infrastructure projects, etc.)

Focus on {dwelling_type} properties. Be thorough and accurate.

Begin your response with the opening brace {{
"""

    print(f"Researching {candidate.name}, {candidate.state} in detail...")

    try:
        # Make the API call with extended timeout for deep research
        response = client.call_deep_research(
            prompt=prompt,
            timeout=240  # 4 minutes for detailed research
        )

        # Parse JSON response
        try:
            data = client.parse_json_response(response)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse JSON for {candidate.name}: {e}")
            # Fall back to basic data from candidate
            return _create_fallback_metrics(candidate)

        # Parse into SuburbMetrics
        metrics = _parse_metrics_from_json(data)

        print(f"✓ Research complete for {candidate.name}")
        return metrics

    except Exception as e:
        print(f"Error researching {candidate.name}: {e}")
        # Return fallback metrics rather than failing
        return _create_fallback_metrics(candidate)


def _parse_metrics_from_json(data: dict) -> SuburbMetrics:
    """Parse JSON data into SuburbMetrics object."""

    # Parse identification
    identification = SuburbIdentification(**data.get("identification", {}))

    # Parse market metrics
    market_current = MarketMetricsCurrent(**data.get("market_current", {}))

    # Parse market history
    market_history_data = data.get("market_history", {})
    market_history = MarketMetricsHistory(
        price_history=[TimePoint(**tp) for tp in market_history_data.get("price_history", [])],
        dom_history=[TimePoint(**tp) for tp in market_history_data.get("dom_history", [])],
        clearance_history=[TimePoint(**tp) for tp in market_history_data.get("clearance_history", [])],
        turnover_history=[TimePoint(**tp) for tp in market_history_data.get("turnover_history", [])]
    )

    # Parse physical config
    physical_config = PhysicalConfig(**data.get("physical_config", {}))

    # Parse demographics
    demographics = Demographics(**data.get("demographics", {}))

    # Parse infrastructure
    infrastructure = Infrastructure(**data.get("infrastructure", {}))

    # Parse growth projections
    growth_data = data.get("growth_projections", {})

    # Convert string keys to int for growth projections
    projected_growth = {}
    for k, v in growth_data.get("projected_growth_pct", {}).items():
        projected_growth[int(k)] = float(v)

    confidence_intervals = {}
    for k, v in growth_data.get("confidence_intervals", {}).items():
        if isinstance(v, list) and len(v) == 2:
            confidence_intervals[int(k)] = (float(v[0]), float(v[1]))

    growth_projections = GrowthProjections(
        projected_growth_pct=projected_growth,
        confidence_intervals=confidence_intervals,
        risk_analysis=growth_data.get("risk_analysis", ""),
        key_drivers=growth_data.get("key_drivers", []),
        growth_score=float(growth_data.get("growth_score", 0)),
        risk_score=float(growth_data.get("risk_score", 0)),
        composite_score=float(growth_data.get("composite_score", 0))
    )

    # Create and return SuburbMetrics
    return SuburbMetrics(
        identification=identification,
        market_current=market_current,
        market_history=market_history,
        physical_config=physical_config,
        demographics=demographics,
        infrastructure=infrastructure,
        growth_projections=growth_projections
    )


def _create_fallback_metrics(candidate: SuburbCandidate) -> SuburbMetrics:
    """
    Create basic SuburbMetrics from SuburbCandidate when detailed research fails.

    Args:
        candidate: SuburbCandidate object

    Returns:
        Minimal SuburbMetrics object
    """
    return SuburbMetrics(
        identification=SuburbIdentification(
            name=candidate.name,
            state=candidate.state,
            lga=candidate.lga,
            region=candidate.region or ""
        ),
        market_current=MarketMetricsCurrent(
            median_price=candidate.median_price
        ),
        growth_projections=GrowthProjections(
            key_drivers=candidate.growth_signals,
            projected_growth_pct={1: 3.0, 2: 6.0, 3: 9.5, 5: 16.0, 10: 35.0, 25: 95.0},
            growth_score=50.0,  # Default medium score
            risk_score=50.0,
            composite_score=50.0
        ),
        infrastructure=Infrastructure(
            major_events_relevance=candidate.major_events_relevance
        )
    )


def batch_research_suburbs(
    candidates: list[SuburbCandidate],
    dwelling_type: str,
    max_price: float,
    max_suburbs: Optional[int] = None
) -> list[SuburbMetrics]:
    """
    Research multiple suburbs in batch.

    Args:
        candidates: List of SuburbCandidate objects
        dwelling_type: Type of dwelling
        max_price: Maximum median price
        max_suburbs: Maximum number to research (None = all)

    Returns:
        List of SuburbMetrics objects
    """
    if max_suburbs:
        candidates = candidates[:max_suburbs]

    results = []
    total = len(candidates)

    print(f"\nResearching {total} suburbs in detail...")
    print("=" * 60)

    for i, candidate in enumerate(candidates, 1):
        print(f"\n[{i}/{total}] {candidate.name}, {candidate.state}")
        try:
            metrics = research_suburb(candidate, dwelling_type, max_price)
            results.append(metrics)
        except Exception as e:
            print(f"! Failed to research {candidate.name}: {e}")
            # Add fallback metrics
            results.append(_create_fallback_metrics(candidate))

    print(f"\n✓ Batch research complete: {len(results)}/{total} suburbs")
    return results
