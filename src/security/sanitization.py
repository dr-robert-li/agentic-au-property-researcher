"""
Credential sanitization for logs, error messages, and HTTP responses.

Provides global logging filter to redact all .env values and common API key patterns
from log output, exception messages, and stack traces.
"""
import logging
import re
from pathlib import Path
from dotenv import dotenv_values


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter that redacts sensitive data from all log records.

    Loads all values from .env file and creates regex patterns to redact them.
    Also includes hardcoded patterns for common API key formats.
    """

    def __init__(self):
        super().__init__()
        self.patterns = []

        # Load all .env values and build redaction patterns
        env_file = Path(__file__).parent.parent.parent / ".env"
        if env_file.exists():
            env_values = dotenv_values(env_file)
            for key, value in env_values.items():
                if value and len(value) > 0:
                    # Escape special regex characters in the value
                    escaped_value = re.escape(value)
                    # Create pattern to match the exact value
                    self.patterns.append(
                        (re.compile(escaped_value), "[REDACTED]")
                    )

        # Hardcoded patterns for common API key formats
        # Perplexity: pplx-<hex chars>
        self.patterns.append(
            (re.compile(r'pplx-[a-f0-9]{20,}'), "[REDACTED]")
        )
        # Anthropic: sk-ant-<alphanumeric>
        self.patterns.append(
            (re.compile(r'sk-ant-[a-zA-Z0-9-_]{20,}'), "[REDACTED]")
        )
        # Generic OpenAI-style: sk-<alphanumeric>
        self.patterns.append(
            (re.compile(r'sk-[a-zA-Z0-9-_]{20,}'), "[REDACTED]")
        )

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Sanitize log record by removing sensitive data.

        Args:
            record: Log record to sanitize

        Returns:
            True (always allows record through after sanitization)
        """
        # Sanitize message string
        if isinstance(record.msg, str):
            for pattern, replacement in self.patterns:
                record.msg = pattern.sub(replacement, record.msg)

        # Sanitize args if present
        if record.args:
            sanitized_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern, replacement in self.patterns:
                        arg = pattern.sub(replacement, arg)
                sanitized_args.append(arg)
            record.args = tuple(sanitized_args)

        # Sanitize exception text if present
        if record.exc_text:
            for pattern, replacement in self.patterns:
                record.exc_text = pattern.sub(replacement, record.exc_text)

        return True  # Always allow record through


def sanitize_text(text: str) -> str:
    """
    Sanitize arbitrary text by removing sensitive data.

    Use this for HTTP error responses, print statements, or any output
    that might contain secrets.

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text with secrets replaced by [REDACTED]
    """
    if not isinstance(text, str):
        text = str(text)

    # Load .env values
    env_file = Path(__file__).parent.parent.parent / ".env"
    env_values = {}
    if env_file.exists():
        env_values = dotenv_values(env_file)

    # Build patterns
    patterns = []
    for key, value in env_values.items():
        if value and len(value) > 0:
            escaped_value = re.escape(value)
            patterns.append((re.compile(escaped_value), "[REDACTED]"))

    # Add hardcoded patterns
    patterns.extend([
        (re.compile(r'pplx-[a-f0-9]{20,}'), "[REDACTED]"),
        (re.compile(r'sk-ant-[a-zA-Z0-9-_]{20,}'), "[REDACTED]"),
        (re.compile(r'sk-[a-zA-Z0-9-_]{20,}'), "[REDACTED]"),
    ])

    # Apply sanitization
    for pattern, replacement in patterns:
        text = pattern.sub(replacement, text)

    return text


def install_log_sanitization():
    """
    Install global log sanitization filter.

    Call this once during application initialization to ensure all log output
    (including from third-party libraries) has sensitive data redacted.
    """
    # Create and attach filter to root logger
    sensitive_filter = SensitiveDataFilter()
    root_logger = logging.getLogger()
    root_logger.addFilter(sensitive_filter)

    # Set third-party loggers to WARNING to reduce noise
    # These libraries may log request details at DEBUG level
    third_party_loggers = [
        "httpx",
        "httpcore",
        "perplexity",
        "anthropic",
        "urllib3",
    ]

    for logger_name in third_party_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
