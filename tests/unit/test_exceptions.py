"""
Unit tests for the typed exception hierarchy.

Tests exception metadata, isinstance routing for transient vs permanent
classification, and convenience tuples for catch blocks.
"""
import pytest

from security.exceptions import (
    ApplicationError,
    PermanentError,
    TransientError,
    ValidationError,
    AuthenticationError,
    ConfigurationError,
    RateLimitError,
    TimeoutError,
    NetworkError,
    APIError,
    CacheError,
    TRANSIENT_ERRORS,
    PERMANENT_ERRORS,
)


@pytest.mark.unit
class TestApplicationErrorMetadata:
    """Test base ApplicationError carries correct metadata."""

    def test_application_error_metadata(self):
        """Create ApplicationError with all kwargs, verify attributes."""
        err = ApplicationError(
            "test error",
            error_code="TEST_CODE",
            retry_after=30,
            is_transient=True,
            provider="perplexity",
        )
        assert err.error_code == "TEST_CODE"
        assert err.retry_after == 30
        assert err.is_transient is True
        assert err.provider == "perplexity"

    def test_str_returns_message(self):
        """str(ApplicationError(...)) returns message, not metadata."""
        err = ApplicationError("test message", error_code="CODE")
        assert str(err) == "test message"


@pytest.mark.unit
class TestPermanentErrors:
    """Test permanent error types."""

    def test_permanent_error_not_transient(self):
        """PermanentError.is_transient is always False."""
        err = PermanentError("permanent")
        assert err.is_transient is False

    def test_validation_error_has_field(self):
        """ValidationError carries field and error_code."""
        err = ValidationError("bad input", field="regions")
        assert err.field == "regions"
        assert err.error_code == "VALIDATION_ERROR"
        assert err.is_transient is False

    def test_auth_error_has_provider(self):
        """AuthenticationError carries provider."""
        err = AuthenticationError("bad key", provider="perplexity")
        assert err.provider == "perplexity"
        assert err.error_code == "AUTH_ERROR"


@pytest.mark.unit
class TestTransientErrors:
    """Test transient error types."""

    def test_rate_limit_default_retry(self):
        """RateLimitError has retry_after=60 by default, is_transient=True."""
        err = RateLimitError("slow down")
        assert err.retry_after == 60
        assert err.is_transient is True

    def test_timeout_error_has_duration(self):
        """TimeoutError carries timeout_seconds."""
        err = TimeoutError("timed out", timeout_seconds=30)
        assert err.timeout_seconds == 30
        assert err.is_transient is True

    def test_api_error_has_status_code(self):
        """APIError carries status_code."""
        err = APIError("server error", status_code=503)
        assert err.status_code == 503
        assert err.is_transient is True

    def test_cache_error_has_operation(self):
        """CacheError carries operation."""
        err = CacheError("write failed", operation="write")
        assert err.operation == "write"


@pytest.mark.unit
class TestConvenienceTuples:
    """Test TRANSIENT_ERRORS and PERMANENT_ERRORS tuples."""

    def test_transient_errors_tuple(self):
        """TRANSIENT_ERRORS contains the expected error types."""
        assert RateLimitError in TRANSIENT_ERRORS
        assert TimeoutError in TRANSIENT_ERRORS
        assert NetworkError in TRANSIENT_ERRORS
        assert APIError in TRANSIENT_ERRORS

    def test_permanent_errors_tuple(self):
        """PERMANENT_ERRORS contains the expected error types."""
        assert AuthenticationError in PERMANENT_ERRORS
        assert ConfigurationError in PERMANENT_ERRORS
        assert ValidationError in PERMANENT_ERRORS


@pytest.mark.unit
class TestIsinstanceRouting:
    """Test isinstance-based error routing (the key test)."""

    @pytest.mark.parametrize(
        "error_cls,args,is_transient_expected",
        [
            (RateLimitError, ("rate limited",), True),
            (TimeoutError, ("timed out", 30), True),
            (NetworkError, ("connection refused",), True),
            (APIError, ("server error",), True),
            (AuthenticationError, ("bad key",), False),
            (ConfigurationError, ("missing config",), False),
            (ValidationError, ("invalid input",), False),
        ],
    )
    def test_isinstance_routing(self, error_cls, args, is_transient_expected):
        """Verify isinstance checks classify errors correctly as transient or permanent."""
        err = error_cls(*args)

        if is_transient_expected:
            assert isinstance(err, TransientError)
            assert not isinstance(err, PermanentError)
            assert err.is_transient is True
        else:
            assert isinstance(err, PermanentError)
            assert not isinstance(err, TransientError)
            assert err.is_transient is False

        # All should be ApplicationError
        assert isinstance(err, ApplicationError)
