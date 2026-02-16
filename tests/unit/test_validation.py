"""
Unit tests for API response validation and coercion.

Tests numeric coercion, discovery response validation (including string prices,
missing fields, invalid states), research response validation (required/optional
fields, coercion), and data quality defaults.
"""
import copy

import pytest

from research.validation import (
    coerce_numeric,
    validate_discovery_response,
    validate_research_response,
)
from security.exceptions import ValidationError as AppValidationError
from tests.fixtures.mock_responses import (
    VALID_DISCOVERY_RESPONSE,
    MALFORMED_DISCOVERY_RESPONSE,
    VALID_RESEARCH_RESPONSE,
    PARTIAL_RESEARCH_RESPONSE,
    INVALID_RESEARCH_RESPONSE,
)


@pytest.mark.unit
class TestCoerceNumeric:
    """Test the coerce_numeric helper function."""

    def test_coerce_numeric_string_int(self):
        assert coerce_numeric("450000") == 450000

    def test_coerce_numeric_string_float(self):
        assert coerce_numeric("3.5") == 3.5

    def test_coerce_numeric_none(self):
        assert coerce_numeric(None) is None

    def test_coerce_numeric_empty_string(self):
        assert coerce_numeric("") is None

    def test_coerce_numeric_invalid_string(self):
        assert coerce_numeric("not_a_number") is None

    def test_coerce_numeric_passthrough_int(self):
        assert coerce_numeric(42) == 42

    def test_coerce_numeric_passthrough_float(self):
        assert coerce_numeric(3.14) == 3.14

    def test_coerce_numeric_zero(self):
        assert coerce_numeric(0) == 0


@pytest.mark.unit
class TestDiscoveryValidation:
    """Test discovery response validation."""

    def test_discovery_valid_response(self):
        """Pass VALID_DISCOVERY_RESPONSE, verify is_valid=True, len(data)==3, no warnings."""
        result = validate_discovery_response(copy.deepcopy(VALID_DISCOVERY_RESPONSE))
        assert result.is_valid is True
        assert len(result.data) == 3
        assert len(result.warnings) == 0

    def test_discovery_string_prices_coerced(self):
        """Pass suburb with median_price as string, verify coerced to float."""
        suburbs = [
            {
                "name": "StringPriceSuburb",
                "state": "QLD",
                "lga": "Brisbane",
                "median_price": "500000",
            }
        ]
        result = validate_discovery_response(suburbs)
        assert result.is_valid is True
        assert len(result.data) == 1
        assert result.data[0]["median_price"] == 500000.0

    def test_discovery_missing_required_field(self):
        """Pass suburb without 'name', verify excluded and warning generated."""
        suburbs = [
            {
                # Missing "name"
                "state": "QLD",
                "lga": "Brisbane",
                "median_price": 450000,
            }
        ]
        result = validate_discovery_response(suburbs)
        assert result.is_valid is False
        assert len(result.data) == 0
        assert len(result.warnings) > 0

    def test_discovery_invalid_state(self):
        """Pass suburb with state='INVALID', verify excluded with warning."""
        suburbs = [
            {
                "name": "BadState",
                "state": "INVALID",
                "lga": "Test",
                "median_price": 400000,
            }
        ]
        result = validate_discovery_response(suburbs)
        assert result.is_valid is False
        assert len(result.data) == 0
        assert any("state" in w.lower() for w in result.warnings)

    def test_discovery_empty_list_invalid(self):
        """Pass empty list, verify is_valid=False and warning about no valid suburbs."""
        result = validate_discovery_response([])
        assert result.is_valid is False
        assert any("No valid suburbs" in w for w in result.warnings)

    def test_discovery_mixed_valid_invalid(self):
        """Pass 3 suburbs where 1 is invalid, verify 2 valid and 1 warning."""
        suburbs = [
            {"name": "Valid1", "state": "QLD", "lga": "Brisbane", "median_price": 400000},
            {"name": "", "state": "QLD", "lga": "Brisbane", "median_price": 400000},  # invalid (empty name)
            {"name": "Valid2", "state": "NSW", "lga": "Sydney", "median_price": 500000},
        ]
        result = validate_discovery_response(suburbs)
        assert result.is_valid is True
        assert len(result.data) == 2
        assert len(result.warnings) >= 1


@pytest.mark.unit
class TestResearchValidation:
    """Test research response validation."""

    def test_research_valid_response(self):
        """Pass VALID_RESEARCH_RESPONSE, verify is_valid=True."""
        result = validate_research_response(
            copy.deepcopy(VALID_RESEARCH_RESPONSE), "Acacia Ridge"
        )
        assert result.is_valid is True

    def test_research_partial_response(self):
        """Pass PARTIAL_RESEARCH_RESPONSE (only required fields), verify is_valid=True with warnings."""
        result = validate_research_response(
            copy.deepcopy(PARTIAL_RESEARCH_RESPONSE), "PartialSuburb"
        )
        assert result.is_valid is True
        assert len(result.warnings) > 0  # Warnings about missing optional data

    def test_research_missing_identification_raises(self):
        """Pass response without identification section, verify AppValidationError raised."""
        with pytest.raises(AppValidationError):
            validate_research_response(
                copy.deepcopy(INVALID_RESEARCH_RESPONSE), "InvalidSuburb"
            )

    def test_research_missing_median_price_raises(self):
        """Pass response with identification but no median_price, verify AppValidationError raised."""
        data = {
            "identification": {
                "name": "TestSuburb",
                "state": "QLD",
                "lga": "Brisbane",
            },
            "market_current": {
                # Missing median_price
                "average_price": 500000,
            },
        }
        with pytest.raises(AppValidationError):
            validate_research_response(data, "TestSuburb")

    def test_research_string_price_coerced(self):
        """Pass research response with median_price as string, verify coerced."""
        data = copy.deepcopy(VALID_RESEARCH_RESPONSE)
        data["market_current"]["median_price"] = "600000"

        result = validate_research_response(data, "Acacia Ridge")
        assert result.is_valid is True
        assert result.data["market_current"]["median_price"] == 600000.0

    def test_growth_projections_string_keys_coerced(self):
        """Pass projected_growth_pct with string keys, verify keys coerced to ints."""
        data = copy.deepcopy(VALID_RESEARCH_RESPONSE)
        data["growth_projections"]["projected_growth_pct"] = {
            "1": 5.0,
            "5": 25.0,
        }

        result = validate_research_response(data, "Acacia Ridge")
        assert result.is_valid is True
        proj = result.data["growth_projections"]["projected_growth_pct"]
        assert 1 in proj
        assert 5 in proj

    def test_data_quality_validation(self):
        """Pass data_quality='invalid_value', verify defaults to 'medium'."""
        suburbs = [
            {
                "name": "QualityTest",
                "state": "QLD",
                "lga": "Brisbane",
                "median_price": 400000,
                "data_quality": "invalid_value",
            }
        ]
        result = validate_discovery_response(suburbs)
        assert result.is_valid is True
        assert result.data[0]["data_quality"] == "medium"
