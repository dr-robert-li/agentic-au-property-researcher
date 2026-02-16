"""
Factory functions for generating test data.

Provides reusable builders for discovery suburbs, research responses,
and SuburbMetrics objects with sensible defaults and override support.
"""


def make_discovery_suburb(**overrides) -> dict:
    """Return a valid discovery suburb dict with defaults.

    Args:
        **overrides: Any key to override in the default dict.

    Returns:
        dict: A valid discovery suburb response dict.
    """
    base = {
        "name": "TestSuburb",
        "state": "QLD",
        "lga": "Brisbane",
        "region": "South East Queensland",
        "median_price": 500000,
        "growth_signals": ["Population growth", "Infrastructure investment"],
        "major_events_relevance": "Brisbane 2032 Olympics",
        "data_quality": "high",
    }
    base.update(overrides)
    return base


def make_research_response(**overrides) -> dict:
    """Return a valid full research response dict with all sections.

    Args:
        **overrides: Any top-level key to override.

    Returns:
        dict: A valid research response dict.
    """
    base = {
        "identification": {
            "name": "TestSuburb",
            "state": "QLD",
            "lga": "Brisbane",
            "region": "South East Queensland",
        },
        "market_current": {
            "median_price": 500000,
            "average_price": 520000,
            "auction_clearance_current": 72.5,
            "days_on_market_current": 35,
            "turnover_rate_current": 5.2,
            "rental_yield_current": 4.1,
        },
        "market_history": {
            "price_history": [
                {"year": 2020, "value": 400000},
                {"year": 2021, "value": 430000},
                {"year": 2022, "value": 460000},
                {"year": 2023, "value": 480000},
                {"year": 2024, "value": 500000},
            ],
            "dom_history": [
                {"year": 2020, "value": 45},
                {"year": 2021, "value": 40},
                {"year": 2022, "value": 38},
                {"year": 2023, "value": 36},
                {"year": 2024, "value": 35},
            ],
            "clearance_history": [],
            "turnover_history": [],
        },
        "physical_config": {
            "land_size_median_sqm": 600,
            "floor_size_median_sqm": 180,
            "typical_bedrooms": 3,
            "typical_bathrooms": 2,
            "typical_car_spaces": 2,
        },
        "demographics": {
            "population_trend": "Growing steadily at 2.1% per year",
            "median_age": 34,
            "household_types": {
                "families_with_children": 0.45,
                "couples_without_children": 0.25,
                "single_person": 0.20,
                "other": 0.10,
            },
            "income_distribution": {
                "low": 0.20,
                "medium": 0.50,
                "high": 0.30,
            },
        },
        "infrastructure": {
            "current_transport": ["Bus network", "Train station 2km"],
            "future_transport": ["Cross River Rail station planned"],
            "current_infrastructure": ["Shopping centre", "Hospital"],
            "planned_infrastructure": ["New school opening 2027"],
            "major_events_relevance": "Brisbane 2032 Olympics venue nearby",
            "shopping_access": "Major shopping centre within 5km",
            "schools_summary": "3 primary schools, 1 high school within 3km",
            "crime_stats": {"overall_rate": "low", "trend": "declining"},
        },
        "growth_projections": {
            "projected_growth_pct": {1: 5.0, 2: 11.0, 3: 17.0, 5: 30.0, 10: 70.0, 25: 200.0},
            "confidence_intervals": {
                1: [3.0, 7.0],
                2: [7.0, 15.0],
                3: [12.0, 22.0],
                5: [20.0, 40.0],
                10: [45.0, 95.0],
                25: [120.0, 280.0],
            },
            "risk_analysis": "Low risk due to strong fundamentals and Olympics catalyst",
            "key_drivers": ["Olympics 2032", "Population growth", "Infrastructure investment"],
            "growth_score": 8.5,
            "risk_score": 3.0,
            "composite_score": 7.2,
        },
    }
    base.update(overrides)
    return base


def make_suburb_metrics(**overrides):
    """Return a SuburbMetrics object from sample research data.

    Args:
        **overrides: Any field to override on the SuburbMetrics.

    Returns:
        SuburbMetrics: A populated SuburbMetrics instance.
    """
    from models.suburb_metrics import SuburbMetrics

    data = make_research_response()
    flat = {
        "name": data["identification"]["name"],
        "state": data["identification"]["state"],
        "lga": data["identification"]["lga"],
        "region": data["identification"].get("region"),
        "median_price": data["market_current"]["median_price"],
        "average_price": data["market_current"].get("average_price"),
    }
    flat.update(overrides)
    return SuburbMetrics(**flat)
