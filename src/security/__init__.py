"""
Security module for credential sanitization, input validation, and typed exceptions.
"""
from .sanitization import SensitiveDataFilter, sanitize_text, install_log_sanitization
from .validators import validate_run_id, validate_cache_path, validate_regions
from .exceptions import (
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
    ResearchError,
    TRANSIENT_ERRORS,
    PERMANENT_ERRORS,
    ACCOUNT_ERRORS,
)

__all__ = [
    # Sanitization
    "SensitiveDataFilter",
    "sanitize_text",
    "install_log_sanitization",
    # Validation
    "validate_run_id",
    "validate_cache_path",
    "validate_regions",
    # Exception hierarchy
    "ApplicationError",
    "PermanentError",
    "TransientError",
    "ValidationError",
    "AuthenticationError",
    "ConfigurationError",
    "RateLimitError",
    "TimeoutError",
    "NetworkError",
    "APIError",
    "ResearchError",
    # Convenience tuples
    "TRANSIENT_ERRORS",
    "PERMANENT_ERRORS",
    "ACCOUNT_ERRORS",
]
