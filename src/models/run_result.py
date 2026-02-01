"""
Run result data models.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from .inputs import UserInput
from .suburb_metrics import SuburbMetrics


class SuburbReport(BaseModel):
    """Complete report for a single suburb."""

    metrics: SuburbMetrics
    narrative_html: str = ""
    charts: dict[str, str] = Field(default_factory=dict)  # chart name -> filename
    rank: Optional[int] = None  # Position in ranking (1-based)

    def get_chart_path(self, chart_name: str, output_dir: Path) -> Optional[Path]:
        """Get full path to a chart file."""
        if chart_name in self.charts:
            return output_dir / "charts" / self.charts[chart_name]
        return None


class RunResult(BaseModel):
    """Complete result of a research run."""

    run_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    user_input: UserInput
    suburbs: list[SuburbReport] = Field(default_factory=list)
    output_dir: Optional[Path] = None
    status: str = "pending"  # pending, running, completed, failed
    error_message: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def get_output_path(self, base_dir: Path) -> Path:
        """Get the output directory path for this run."""
        if self.output_dir:
            return self.output_dir
        return base_dir / self.run_id

    def get_top_suburbs(self, n: Optional[int] = None) -> list[SuburbReport]:
        """Get top N suburbs by rank."""
        if n is None:
            n = self.user_input.num_suburbs
        return sorted(self.suburbs, key=lambda s: s.rank or 999)[:n]

    def to_summary_dict(self) -> dict:
        """Convert to summary dictionary for display."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "regions": self.user_input.regions,
            "dwelling_type": self.user_input.dwelling_type,
            "max_price": self.user_input.max_median_price,
            "num_suburbs": len(self.suburbs),
            "top_suburb": self.suburbs[0].metrics.identification.name if self.suburbs else None
        }
