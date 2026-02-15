"""
Response validation for API outputs using Pydantic v2.

Validates and coerces API responses from Perplexity and Anthropic before
they enter the cache. Handles LLM output variability (string numbers, nulls,
missing optional fields) while providing structured warnings for data quality.
"""
import logging
from dataclasses import dataclass
from typing import Annotated, Optional, Any

from pydantic import (
    BaseModel,
    Field,
    BeforeValidator,
    field_validator,
    ValidationError as PydanticValidationError
)

from security.exceptions import ValidationError as AppValidationError

logger = logging.getLogger(__name__)


# ============================================================================
# Coercion Helpers
# ============================================================================

def coerce_numeric(value: Any) -> float | int | None:
    """
    Coerce string numbers to int/float. Handles '450000', '3.5', etc.

    LLMs frequently return numeric values as strings. This handles:
    - "450000" -> 450000 (int)
    - "3.5" -> 3.5 (float)
    - "invalid" -> None
    - None -> None
    - 0 -> 0
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            # Preserve int vs float distinction
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            logger.warning("Failed to coerce string to numeric: %s", value)
            return None
    return None


# ============================================================================
# Discovery Response Validation
# ============================================================================

class DiscoverySuburbResponse(BaseModel):
    """
    Validation schema for a single suburb in discovery API response.

    Required fields: name, state, lga, median_price
    Optional fields: region, growth_signals, major_events_relevance, data_quality

    String prices are automatically coerced to numbers.
    """
    name: str = Field(min_length=1)
    state: str = Field(pattern=r"^(NSW|VIC|QLD|SA|WA|TAS|NT|ACT)$")
    lga: str = Field(min_length=1)
    region: Optional[str] = None
    median_price: Annotated[float, BeforeValidator(coerce_numeric)] = Field(gt=0)
    growth_signals: list[str] = Field(default_factory=list)
    major_events_relevance: Optional[str] = None
    data_quality: Optional[str] = Field(default="medium")

    @field_validator("data_quality")
    @classmethod
    def validate_data_quality(cls, v: Optional[str]) -> str:
        """Ensure data_quality is one of: high, medium, low (default to medium if invalid)."""
        if v in ("high", "medium", "low"):
            return v
        logger.warning("Invalid data_quality value '%s', defaulting to 'medium'", v)
        return "medium"


# ============================================================================
# Research Response Validation
# ============================================================================

class ResearchIdentificationResponse(BaseModel):
    """Identification section (required)."""
    name: str = Field(min_length=1)
    state: str = Field(pattern=r"^(NSW|VIC|QLD|SA|WA|TAS|NT|ACT)$")
    lga: str = Field(min_length=1)
    region: Optional[str] = None


class ResearchMarketCurrentResponse(BaseModel):
    """Current market metrics (median_price required, others optional)."""
    median_price: Annotated[float, BeforeValidator(coerce_numeric)] = Field(gt=0)
    average_price: Annotated[Optional[float], BeforeValidator(coerce_numeric)] = None
    auction_clearance_current: Annotated[Optional[float], BeforeValidator(coerce_numeric)] = None
    days_on_market_current: Annotated[Optional[float], BeforeValidator(coerce_numeric)] = None
    turnover_rate_current: Annotated[Optional[float], BeforeValidator(coerce_numeric)] = None
    rental_yield_current: Annotated[Optional[float], BeforeValidator(coerce_numeric)] = None


class TimePointResponse(BaseModel):
    """Single time-series data point."""
    year: int
    value: Annotated[float, BeforeValidator(coerce_numeric)]


class ResearchMarketHistoryResponse(BaseModel):
    """Historical market data (all optional)."""
    price_history: list[TimePointResponse] = Field(default_factory=list)
    dom_history: list[TimePointResponse] = Field(default_factory=list)
    clearance_history: list[TimePointResponse] = Field(default_factory=list)
    turnover_history: list[TimePointResponse] = Field(default_factory=list)


class ResearchPhysicalConfigResponse(BaseModel):
    """Physical configuration metrics (all optional, with coercion)."""
    land_size_median_sqm: Annotated[Optional[float], BeforeValidator(coerce_numeric)] = None
    floor_size_median_sqm: Annotated[Optional[float], BeforeValidator(coerce_numeric)] = None
    typical_bedrooms: Annotated[Optional[int], BeforeValidator(coerce_numeric)] = None
    typical_bathrooms: Annotated[Optional[int], BeforeValidator(coerce_numeric)] = None
    typical_car_spaces: Annotated[Optional[int], BeforeValidator(coerce_numeric)] = None


class ResearchDemographicsResponse(BaseModel):
    """Demographics (all optional)."""
    population_trend: Optional[str | dict] = None
    median_age: Annotated[Optional[float], BeforeValidator(coerce_numeric)] = None
    household_types: dict = Field(default_factory=dict)
    income_distribution: Optional[dict] = None


class ResearchInfrastructureResponse(BaseModel):
    """Infrastructure and amenities (list fields default to empty lists)."""
    current_transport: list[str] = Field(default_factory=list)
    future_transport: list[str] = Field(default_factory=list)
    current_infrastructure: list[str] = Field(default_factory=list)
    planned_infrastructure: list[str] = Field(default_factory=list)
    major_events_relevance: Optional[str | dict] = None
    shopping_access: Optional[str | dict] = None
    schools_summary: Optional[str | dict] = None
    crime_stats: dict = Field(default_factory=dict)


class ResearchGrowthProjectionsResponse(BaseModel):
    """
    Growth projections with flexible key coercion.

    LLMs may return dict keys as strings ("1", "2", etc.) or ints (1, 2, etc.).
    We coerce keys to ints during validation.
    """
    projected_growth_pct: dict[str | int, float] = Field(default_factory=dict)
    confidence_intervals: dict[str | int, list[float]] = Field(default_factory=dict)
    risk_analysis: str = ""
    key_drivers: list[str] = Field(default_factory=list)
    growth_score: Annotated[float, BeforeValidator(coerce_numeric)] = 0.0
    risk_score: Annotated[float, BeforeValidator(coerce_numeric)] = 0.0
    composite_score: Annotated[float, BeforeValidator(coerce_numeric)] = 0.0

    @field_validator("projected_growth_pct", mode="before")
    @classmethod
    def coerce_growth_pct_keys(cls, v: dict) -> dict:
        """Coerce string keys to ints."""
        if not isinstance(v, dict):
            return {}
        return {int(k): float(val) for k, val in v.items()}

    @field_validator("confidence_intervals", mode="before")
    @classmethod
    def coerce_confidence_keys(cls, v: dict) -> dict:
        """Coerce string keys to ints."""
        if not isinstance(v, dict):
            return {}
        return {int(k): val for k, val in v.items()}


class ResearchSuburbResponse(BaseModel):
    """
    Top-level research response schema.

    Required: identification, market_current
    Optional: all other sections (default to empty/zero values)
    """
    identification: ResearchIdentificationResponse
    market_current: ResearchMarketCurrentResponse
    market_history: ResearchMarketHistoryResponse = Field(default_factory=ResearchMarketHistoryResponse)
    physical_config: ResearchPhysicalConfigResponse = Field(default_factory=ResearchPhysicalConfigResponse)
    demographics: ResearchDemographicsResponse = Field(default_factory=ResearchDemographicsResponse)
    infrastructure: ResearchInfrastructureResponse = Field(default_factory=ResearchInfrastructureResponse)
    growth_projections: ResearchGrowthProjectionsResponse = Field(default_factory=ResearchGrowthProjectionsResponse)


# ============================================================================
# Validation Result Container
# ============================================================================

@dataclass
class ValidationResult:
    """
    Container for validation results with warnings.

    Attributes:
        data: The validated/coerced data (as dict or list of dicts)
        warnings: List of field-level warnings (e.g., "market_history: No data available")
        is_valid: True if all required fields passed validation
    """
    data: Any  # dict for research, list[dict] for discovery
    warnings: list[str]
    is_valid: bool


# ============================================================================
# Validation Functions
# ============================================================================

def validate_discovery_response(raw_list: list[dict]) -> ValidationResult:
    """
    Validate and coerce discovery API response.

    Args:
        raw_list: List of suburb dicts from API

    Returns:
        ValidationResult with valid items, warnings, and is_valid flag

    Each item that fails required field validation is excluded from result
    and produces a warning with field-level detail. Items that pass are
    included with coerced values.
    """
    valid_items = []
    warnings = []

    for i, item in enumerate(raw_list):
        try:
            validated = DiscoverySuburbResponse(**item)
            valid_items.append(validated.model_dump())
        except PydanticValidationError as e:
            # Extract field-level errors
            suburb_name = item.get("name", f"item_{i}")
            for error in e.errors():
                field_path = ".".join(str(f) for f in error["loc"])
                error_msg = error["msg"]
                actual_value = error.get("input", "N/A")
                warnings.append(
                    f"{suburb_name}: {field_path}: {error_msg} (got: {actual_value})"
                )
            logger.warning("Discovery validation failed for %s: %s", suburb_name, e)

    is_valid = len(valid_items) > 0

    if not is_valid:
        warnings.append("No valid suburbs found in discovery response")

    return ValidationResult(
        data=valid_items,
        warnings=warnings,
        is_valid=is_valid
    )


def validate_research_response(raw_data: dict, suburb_name: str) -> ValidationResult:
    """
    Validate and coerce research API response for a single suburb.

    Args:
        raw_data: Research response dict from API
        suburb_name: Suburb name (for error messages)

    Returns:
        ValidationResult with validated data, warnings, and is_valid flag

    Raises:
        AppValidationError: If required fields (identification, market_current) are missing

    Optional fields that are missing/invalid produce warnings but do not block processing.
    """
    warnings = []

    try:
        validated = ResearchSuburbResponse(**raw_data)

        # Check for optional sections that have no data
        if not validated.market_history.price_history:
            warnings.append("market_history.price_history: No historical price data available")

        if not validated.market_history.dom_history:
            warnings.append("market_history.dom_history: No historical DOM data available")

        if validated.physical_config.land_size_median_sqm is None:
            warnings.append("physical_config.land_size_median_sqm: No land size data available")

        if not validated.demographics.population_trend:
            warnings.append("demographics.population_trend: No population trend data available")

        if not validated.infrastructure.current_transport:
            warnings.append("infrastructure.current_transport: No transport data available")

        if not validated.growth_projections.key_drivers:
            warnings.append("growth_projections.key_drivers: No growth drivers identified")

        return ValidationResult(
            data=validated.model_dump(),
            warnings=warnings,
            is_valid=True
        )

    except PydanticValidationError as e:
        # Extract field-level errors for required fields
        error_details = []
        for error in e.errors():
            field_path = ".".join(str(f) for f in error["loc"])
            error_msg = error["msg"]
            actual_value = error.get("input", "N/A")
            error_details.append(f"{field_path}: {error_msg} (got: {actual_value})")

        error_summary = "; ".join(error_details)
        logger.error("Research validation failed for %s: %s", suburb_name, error_summary)

        raise AppValidationError(
            message=f"Research response validation failed for {suburb_name}: {error_summary}",
            field=suburb_name
        )
