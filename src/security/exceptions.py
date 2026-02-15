"""
Typed exception hierarchy for structured error handling.

Replaces string-matching error detection with type-based dispatch.
All exceptions carry structured metadata (error_code, retry_after, is_transient, provider)
for programmatic handling by retry logic, error handlers, and logging.
"""
from typing import Optional


class ApplicationError(Exception):
    """
    Base exception for all application errors.

    Carries structured metadata for downstream error handling:
    - error_code: Machine-readable error identifier
    - retry_after: Seconds to wait before retry (for transient errors)
    - is_transient: Whether error is temporary and can be retried
    - provider: API provider that caused the error ("perplexity" | "anthropic" | None)
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        retry_after: Optional[int] = None,
        is_transient: bool = False,
        provider: Optional[str] = None
    ):
        super().__init__(message)
        self.error_code = error_code
        self.retry_after = retry_after
        self.is_transient = is_transient
        self.provider = provider

    def __str__(self) -> str:
        """Return clean message without metadata (keeps logs readable)."""
        return super().__str__()


# ============================================================================
# Permanent Errors (Do Not Retry)
# ============================================================================

class PermanentError(ApplicationError):
    """Base class for permanent errors that should not be retried."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        provider: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            is_transient=False,
            provider=provider
        )


class ValidationError(PermanentError):
    """Input validation failed (bad region, run_id, price, etc.)."""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message=message, error_code="VALIDATION_ERROR")
        self.field = field


class AuthenticationError(PermanentError):
    """API authentication failed (invalid/expired key)."""

    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="AUTH_ERROR",
            provider=provider
        )


class ConfigurationError(PermanentError):
    """Application configuration is invalid or missing."""

    def __init__(self, message: str):
        super().__init__(message=message, error_code="CONFIG_ERROR")


# ============================================================================
# Transient Errors (Can Retry)
# ============================================================================

class TransientError(ApplicationError):
    """Base class for transient errors that can be retried."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        retry_after: Optional[int] = None,
        provider: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            retry_after=retry_after,
            is_transient=True,
            provider=provider
        )


class RateLimitError(TransientError):
    """API rate limit exceeded or insufficient credits."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = 60,
        provider: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT",
            retry_after=retry_after,
            provider=provider
        )


class TimeoutError(TransientError):
    """Request timed out."""

    def __init__(self, message: str, timeout_seconds: int, provider: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="TIMEOUT",
            provider=provider
        )
        self.timeout_seconds = timeout_seconds


class NetworkError(TransientError):
    """Network connectivity issue (connection refused, DNS failure, etc.)."""

    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="NETWORK_ERROR",
            provider=provider
        )


class APIError(TransientError):
    """Generic API error (5xx status, service unavailable, etc.)."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        provider: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="API_ERROR",
            provider=provider
        )
        self.status_code = status_code


# ============================================================================
# Research-Specific Errors
# ============================================================================

class ResearchError(ApplicationError):
    """
    Error specific to the research pipeline.

    Examples:
    - JSON parsing failure from API response
    - No qualifying suburbs found
    - Invalid suburb data structure
    """

    def __init__(self, message: str, is_transient: bool = False):
        super().__init__(
            message=message,
            error_code="RESEARCH_ERROR",
            is_transient=is_transient
        )


# ============================================================================
# Convenience Tuples for Catch Blocks
# ============================================================================

# All transient errors (use in retry loops)
TRANSIENT_ERRORS = (RateLimitError, TimeoutError, NetworkError, APIError)

# All permanent errors (fail immediately)
PERMANENT_ERRORS = (AuthenticationError, ConfigurationError, ValidationError)

# Account-level errors that should stop all workers (not just one suburb)
ACCOUNT_ERRORS = (RateLimitError, AuthenticationError)
