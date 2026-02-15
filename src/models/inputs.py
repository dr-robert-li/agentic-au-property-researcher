"""
User input data models.
"""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class UserInput(BaseModel):
    """User input for a research run."""

    max_median_price: float = Field(..., gt=0, description="Maximum median price threshold in AUD")
    dwelling_type: Literal["house", "apartment", "townhouse"] = Field(..., description="Type of dwelling")
    regions: list[str] = Field(default=["All Australia"], description="List of regions/states to search")
    num_suburbs: int = Field(default=10, gt=0, le=100, description="Number of top suburbs to include in report")
    provider: Literal["perplexity", "anthropic"] = Field(default="perplexity", description="AI research provider")
    interface_mode: Literal["gui", "cli"] = Field(default="gui", description="Interface mode used")
    run_id: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), description="Unique run identifier")

    @field_validator("run_id")
    @classmethod
    def validate_run_id_field(cls, v):
        """Validate run_id against safe character pattern."""
        from security.validators import validate_run_id
        return validate_run_id(v)

    @field_validator("regions")
    @classmethod
    def validate_regions_field(cls, v):
        """Validate regions against whitelist with case normalization."""
        from security.validators import validate_regions
        if not v:
            return ["All Australia"]
        return validate_regions(v)

    @field_validator("num_suburbs")
    @classmethod
    def validate_num_suburbs(cls, v):
        """Warn if num_suburbs is high."""
        if v > 25:
            # This will be checked in the application logic for user confirmation
            pass
        return v

    def get_region_description(self) -> str:
        """Get human-readable description of selected regions."""
        if not self.regions or "All Australia" in self.regions:
            return "All Australia"
        if len(self.regions) == 1:
            return self.regions[0]
        return f"{len(self.regions)} regions ({', '.join(self.regions[:3])}{'...' if len(self.regions) > 3 else ''})"

    def get_provider_display(self) -> str:
        """Get human-readable provider name."""
        if self.provider == "perplexity":
            return "Perplexity (Deep Research + Web Search)"
        return "Anthropic Claude (claude-sonnet-4-5)"

    class Config:
        json_schema_extra = {
            "example": {
                "max_median_price": 800000,
                "dwelling_type": "house",
                "regions": ["South East Queensland", "Northern NSW"],
                "num_suburbs": 10,
                "provider": "perplexity",
                "interface_mode": "gui"
            }
        }
