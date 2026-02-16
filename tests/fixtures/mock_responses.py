"""
Canned API responses for testing validation and parsing.

Provides pre-built response dicts that simulate various API output scenarios:
- Valid responses (happy path)
- Malformed responses (string prices, missing fields)
- Partial responses (only required fields)
- Invalid responses (missing required fields)
"""

VALID_DISCOVERY_RESPONSE = [
    {
        "name": "Acacia Ridge",
        "state": "QLD",
        "lga": "Brisbane",
        "region": "South East Queensland",
        "median_price": 550000,
        "growth_signals": ["Population growth", "Infrastructure"],
        "major_events_relevance": "Brisbane 2032 Olympics",
        "data_quality": "high",
    },
    {
        "name": "Woodridge",
        "state": "QLD",
        "lga": "Logan",
        "region": "South East Queensland",
        "median_price": 420000,
        "growth_signals": ["Affordability", "Transport upgrades"],
        "major_events_relevance": None,
        "data_quality": "medium",
    },
    {
        "name": "Elizabeth",
        "state": "SA",
        "lga": "Playford",
        "region": "Northern Adelaide",
        "median_price": 380000,
        "growth_signals": ["Government investment"],
        "major_events_relevance": None,
        "data_quality": "low",
    },
]

MALFORMED_DISCOVERY_RESPONSE = [
    {
        "name": "StringPrice",
        "state": "QLD",
        "lga": "Brisbane",
        "median_price": "500000",  # String instead of number
        "data_quality": "high",
    },
    {
        "name": "",  # Empty name - should fail validation
        "state": "QLD",
        "lga": "Brisbane",
        "median_price": 400000,
    },
    {
        # Missing name entirely
        "state": "QLD",
        "lga": "Brisbane",
        "median_price": 450000,
    },
    {
        "name": "InvalidState",
        "state": "INVALID",  # Invalid state code
        "lga": "Test",
        "median_price": 400000,
    },
]

VALID_RESEARCH_RESPONSE = {
    "identification": {
        "name": "Acacia Ridge",
        "state": "QLD",
        "lga": "Brisbane",
        "region": "South East Queensland",
    },
    "market_current": {
        "median_price": 550000,
        "average_price": 570000,
        "auction_clearance_current": 68.5,
        "days_on_market_current": 32,
        "turnover_rate_current": 4.8,
        "rental_yield_current": 4.3,
    },
    "market_history": {
        "price_history": [
            {"year": 2020, "value": 420000},
            {"year": 2021, "value": 450000},
            {"year": 2022, "value": 490000},
            {"year": 2023, "value": 520000},
            {"year": 2024, "value": 550000},
        ],
        "dom_history": [
            {"year": 2020, "value": 42},
            {"year": 2021, "value": 38},
            {"year": 2022, "value": 35},
            {"year": 2023, "value": 33},
            {"year": 2024, "value": 32},
        ],
        "clearance_history": [],
        "turnover_history": [],
    },
    "physical_config": {
        "land_size_median_sqm": 650,
        "floor_size_median_sqm": 190,
        "typical_bedrooms": 3,
        "typical_bathrooms": 2,
        "typical_car_spaces": 2,
    },
    "demographics": {
        "population_trend": "Steady growth at 1.8% pa",
        "median_age": 35,
        "household_types": {"families": 0.50, "couples": 0.25, "singles": 0.25},
        "income_distribution": {"low": 0.25, "medium": 0.50, "high": 0.25},
    },
    "infrastructure": {
        "current_transport": ["Bus", "Train station 3km"],
        "future_transport": ["Cross River Rail"],
        "current_infrastructure": ["Shops", "Parks"],
        "planned_infrastructure": ["New school 2027"],
        "major_events_relevance": "Olympics 2032",
        "shopping_access": "Westfield nearby",
        "schools_summary": "Good local schools",
        "crime_stats": {"overall": "low"},
    },
    "growth_projections": {
        "projected_growth_pct": {1: 4.5, 2: 9.5, 3: 15.0, 5: 28.0, 10: 65.0, 25: 180.0},
        "confidence_intervals": {
            1: [2.5, 6.5],
            2: [6.0, 13.0],
            3: [10.0, 20.0],
            5: [18.0, 38.0],
            10: [40.0, 90.0],
            25: [100.0, 260.0],
        },
        "risk_analysis": "Moderate risk, strong fundamentals",
        "key_drivers": ["Olympics", "Population growth"],
        "growth_score": 7.8,
        "risk_score": 3.5,
        "composite_score": 6.5,
    },
}

PARTIAL_RESEARCH_RESPONSE = {
    "identification": {
        "name": "PartialSuburb",
        "state": "NSW",
        "lga": "Sydney",
    },
    "market_current": {
        "median_price": 700000,
    },
    # All other sections omitted - should use defaults
}

INVALID_RESEARCH_RESPONSE = {
    # Missing identification section entirely
    "market_current": {
        "median_price": 500000,
    },
    "growth_projections": {
        "projected_growth_pct": {1: 5.0},
    },
}
