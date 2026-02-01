"""
Suburb metrics and data models.
"""
from typing import Optional
from pydantic import BaseModel, Field


class TimePoint(BaseModel):
    """A single time-series data point."""
    year: int
    value: float


class SuburbIdentification(BaseModel):
    """Suburb identification information."""
    name: str
    state: str  # NSW, VIC, QLD, SA, WA, TAS, NT, ACT
    lga: str  # Local Government Area
    region: Optional[str] = None


class MarketMetricsCurrent(BaseModel):
    """Current market metrics."""
    median_price: float
    average_price: Optional[float] = None
    auction_clearance_current: Optional[float] = None
    days_on_market_current: Optional[float] = None
    turnover_rate_current: Optional[float] = None
    rental_yield_current: Optional[float] = None


class MarketMetricsHistory(BaseModel):
    """Historical market metrics."""
    price_history: list[TimePoint] = Field(default_factory=list)
    dom_history: list[TimePoint] = Field(default_factory=list)
    clearance_history: list[TimePoint] = Field(default_factory=list)
    turnover_history: list[TimePoint] = Field(default_factory=list)


class PhysicalConfig(BaseModel):
    """Physical configuration metrics."""
    land_size_median_sqm: Optional[float] = None
    floor_size_median_sqm: Optional[float] = None
    typical_bedrooms: Optional[int] = None
    typical_bathrooms: Optional[int] = None
    typical_car_spaces: Optional[int] = None


class Demographics(BaseModel):
    """Demographic information."""
    population_trend: Optional[str | dict] = None
    median_age: Optional[float] = None
    household_types: dict = Field(default_factory=dict)
    income_distribution: Optional[dict] = None


class Infrastructure(BaseModel):
    """Infrastructure and amenity information."""
    current_transport: list[str] = Field(default_factory=list)
    future_transport: list[str] = Field(default_factory=list)
    current_infrastructure: list[str] = Field(default_factory=list)
    planned_infrastructure: list[str] = Field(default_factory=list)
    major_events_relevance: Optional[str | dict] = None
    shopping_access: Optional[str | dict] = None
    schools_summary: Optional[str | dict] = None
    crime_stats: dict = Field(default_factory=dict)


class GrowthProjections(BaseModel):
    """Growth projections and analysis."""
    projected_growth_pct: dict[int, float] = Field(
        default_factory=lambda: {1: 0.0, 2: 0.0, 3: 0.0, 5: 0.0, 10: 0.0, 25: 0.0}
    )
    confidence_intervals: dict[int, tuple[float, float]] = Field(default_factory=dict)
    risk_analysis: str = ""
    key_drivers: list[str] = Field(default_factory=list)
    growth_score: float = 0.0  # Primary ranking metric
    risk_score: float = 0.0
    composite_score: float = 0.0  # Growth adjusted for risk


class SuburbMetrics(BaseModel):
    """Complete metrics for a suburb."""

    identification: SuburbIdentification
    market_current: MarketMetricsCurrent
    market_history: MarketMetricsHistory = Field(default_factory=MarketMetricsHistory)
    physical_config: PhysicalConfig = Field(default_factory=PhysicalConfig)
    demographics: Demographics = Field(default_factory=Demographics)
    infrastructure: Infrastructure = Field(default_factory=Infrastructure)
    growth_projections: GrowthProjections = Field(default_factory=GrowthProjections)

    def get_display_name(self) -> str:
        """Get formatted display name for the suburb."""
        return f"{self.identification.name}, {self.identification.state}"

    def get_slug(self) -> str:
        """Get URL-safe slug for the suburb."""
        from slugify import slugify
        return slugify(f"{self.identification.name}-{self.identification.state}")

    class Config:
        json_schema_extra = {
            "example": {
                "identification": {
                    "name": "Acacia Ridge",
                    "state": "QLD",
                    "lga": "Brisbane",
                    "region": "Greater Brisbane"
                },
                "market_current": {
                    "median_price": 650000,
                    "average_price": 680000,
                    "auction_clearance_current": 0.72,
                    "days_on_market_current": 28,
                    "turnover_rate_current": 0.08,
                    "rental_yield_current": 0.042
                },
                "growth_projections": {
                    "projected_growth_pct": {
                        1: 5.2,
                        2: 11.5,
                        3: 18.3,
                        5: 32.5,
                        10: 78.2,
                        25: 245.0
                    },
                    "growth_score": 85.5,
                    "risk_score": 35.2,
                    "composite_score": 72.8
                }
            }
        }
