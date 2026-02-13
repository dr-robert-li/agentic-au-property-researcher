"""
Data models for run comparison functionality.
"""
from typing import Optional
from pydantic import BaseModel, Field


class RunSummary(BaseModel):
    """Summary of a single run for comparison."""
    run_id: str
    timestamp: str
    dwelling_type: str
    max_price: float
    regions: list[str]
    suburb_count: int
    provider: str


class SuburbRunMetrics(BaseModel):
    """Metrics for a suburb from a specific run."""
    run_id: str
    median_price: float = 0.0
    growth_score: float = 0.0
    composite_score: float = 0.0
    risk_score: float = 0.0
    projected_5yr: float = 0.0
    rank: Optional[int] = None


class SuburbDelta(BaseModel):
    """Comparison data for a suburb appearing in multiple runs."""
    suburb_name: str
    state: str
    run_metrics: list[SuburbRunMetrics] = Field(default_factory=list)

    @property
    def price_delta(self) -> Optional[float]:
        """Price difference between first and last run."""
        prices = [m.median_price for m in self.run_metrics if m.median_price > 0]
        if len(prices) >= 2:
            return prices[-1] - prices[0]
        return None

    @property
    def score_delta(self) -> Optional[float]:
        """Composite score difference between first and last run."""
        scores = [m.composite_score for m in self.run_metrics if m.composite_score > 0]
        if len(scores) >= 2:
            return scores[-1] - scores[0]
        return None


class ComparisonResult(BaseModel):
    """Result of comparing multiple runs."""
    run_summaries: list[RunSummary] = Field(default_factory=list)
    overlapping_suburbs: list[SuburbDelta] = Field(default_factory=list)
    unique_per_run: dict[str, list[str]] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True
