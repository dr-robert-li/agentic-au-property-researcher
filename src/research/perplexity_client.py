"""
Perplexity API client wrapper with retry logic and error handling.
Also provides factory function for getting the appropriate research client.
"""
import json
import time
from typing import Optional, Any
import os

from config import settings
from security.exceptions import RateLimitError, AuthenticationError, APIError, TimeoutError, NetworkError
from security.sanitization import sanitize_text


# Provider-specific exception subclasses
class PerplexityAPIError(APIError):
    """Base exception for Perplexity API errors."""
    def __init__(self, message: str = None, status_code: Optional[int] = None):
        default_msg = (
            "\n⚠️  PERPLEXITY API ERROR\n\n"
            "The Perplexity API request failed.\n\n"
            "Possible causes:\n"
            "  • Network connectivity issues\n"
            "  • API service temporarily unavailable\n"
            "  • Request timeout\n\n"
            "Suggestions:\n"
            "  • Check your internet connection\n"
            "  • Try again in a few minutes\n"
            "  • Check Perplexity API status\n"
            "  • Verify your API credits at: https://www.perplexity.ai/account/api/billing\n"
        )
        super().__init__(
            message=message or default_msg,
            status_code=status_code,
            provider="perplexity"
        )


class PerplexityRateLimitError(RateLimitError):
    """Exception raised when API rate limit is exceeded."""
    def __init__(self, message: str = None, retry_after: Optional[int] = 60):
        default_msg = (
            "\n⚠️  API RATE LIMIT EXCEEDED OR INSUFFICIENT CREDITS\n\n"
            "Your Perplexity API request was denied. This typically means:\n"
            "  1. You've exceeded your API rate limit\n"
            "  2. Your API credit balance is insufficient\n"
            "  3. Your API key has expired or is invalid\n\n"
            "ACTION REQUIRED:\n"
            "  → Check your API credit balance at:\n"
            "    https://www.perplexity.ai/account/api/billing\n\n"
            "  → If your balance is low, add more credits\n"
            "  → If rate limited, wait a few minutes and try again with fewer suburbs\n"
            "  → Verify your API key in .env is correct and active\n"
        )
        super().__init__(
            message=message or default_msg,
            retry_after=retry_after,
            provider="perplexity"
        )


class PerplexityAuthError(AuthenticationError):
    """Exception raised when API authentication fails."""
    def __init__(self, message: str = None):
        default_msg = (
            "\n⚠️  API AUTHENTICATION FAILED\n\n"
            "Your Perplexity API key appears to be invalid or inactive.\n\n"
            "ACTION REQUIRED:\n"
            "  → Check your API key in the .env file\n"
            "  → Verify the key is active at:\n"
            "    https://www.perplexity.ai/account/api/billing\n"
            "  → Generate a new API key if needed\n"
        )
        super().__init__(message=message or default_msg, provider="perplexity")


class PerplexityClient:
    """Wrapper for Perplexity Agentic Research API."""

    def __init__(self):
        """Initialize the Perplexity client."""
        try:
            # Import here to handle SDK availability gracefully
            from perplexity import Perplexity
            self.client = Perplexity(api_key=settings.PERPLEXITY_API_KEY)
            self.initialized = True
        except ImportError:
            print("Warning: perplexityai package not installed. Install with: pip install perplexityai")
            self.initialized = False
        except Exception as e:
            print(f"Warning: Failed to initialize Perplexity client: {e}")
            self.initialized = False

    def test_connection(self) -> bool:
        """Test the API connection with a simple query."""
        if not self.initialized:
            return False

        try:
            response = self.call_deep_research(
                prompt="What is the capital of Australia?",
                timeout=30
            )
            return response is not None and len(response) > 0
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    def call_deep_research(
        self,
        prompt: str,
        preset: str = "deep-research",
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        timeout: int = None,
        max_retries: int = None
    ) -> str:
        """
        Make a deep research call to Perplexity.

        Args:
            prompt: The research prompt/question
            preset: Preset to use (default: "deep-research")
            model: Optional model override (e.g., "anthropic/claude-sonnet-4-5")
            tools: Optional tools list (e.g., [{"type": "web_search"}, {"type": "fetch_url"}])
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts

        Returns:
            Response text from Perplexity

        Raises:
            Exception: If the API call fails after retries
        """
        if not self.initialized:
            raise Exception("Perplexity client not initialized")

        if timeout is None:
            timeout = settings.API_TIMEOUT
        if max_retries is None:
            max_retries = settings.MAX_RETRIES

        last_exception = None

        for attempt in range(max_retries):
            try:
                # Build request parameters
                params = {
                    "input": prompt
                }

                # Use preset if no model specified
                if model is None:
                    params["preset"] = preset
                else:
                    params["model"] = model
                    if tools:
                        params["tools"] = tools

                # Make the API call
                response = self.client.responses.create(**params)

                # Extract and return the output
                if hasattr(response, 'output_text'):
                    return response.output_text
                elif hasattr(response, 'output'):
                    return response.output
                elif isinstance(response, dict):
                    return response.get('output_text') or response.get('output', '')
                else:
                    return str(response)

            except Exception as e:
                last_exception = e

                # Sanitize error message before any processing
                sanitized_error = sanitize_text(str(e))

                # Try to get status code from exception
                status_code = getattr(e, 'status_code', None)

                # If no status_code attribute, try to extract from response
                if status_code is None and hasattr(e, 'response'):
                    status_code = getattr(e.response, 'status_code', None)

                # Map status codes to exception types
                if status_code:
                    if status_code == 401 or status_code == 403:
                        raise PerplexityAuthError(sanitized_error) from e
                    elif status_code == 429:
                        # Try to extract retry_after from headers
                        retry_after = 60  # default
                        if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                            retry_after = int(e.response.headers.get('Retry-After', 60))
                        raise PerplexityRateLimitError(sanitized_error, retry_after=retry_after) from e
                    elif status_code == 408 or status_code == 504:
                        raise TimeoutError(sanitized_error, timeout_seconds=timeout, provider="perplexity") from e
                    elif status_code >= 500:
                        raise PerplexityAPIError(sanitized_error, status_code=status_code) from e

                # Fallback: check exception type name if no status code
                exception_type = type(e).__name__.lower()
                if 'timeout' in exception_type:
                    raise TimeoutError(sanitized_error, timeout_seconds=timeout, provider="perplexity") from e
                elif 'connection' in exception_type or 'network' in exception_type:
                    raise NetworkError(sanitized_error, provider="perplexity") from e

                # Last resort: string matching only if we have NO other information
                # This is a fallback for unexpected SDK error formats
                if status_code is None:
                    error_str_lower = sanitized_error.lower()
                    if any(indicator in error_str_lower for indicator in [
                        '401', 'unauthorized', 'forbidden', '403', 'invalid api key',
                        'authentication failed', 'invalid key', 'api key'
                    ]):
                        raise PerplexityAuthError(sanitized_error) from e
                    elif any(indicator in error_str_lower for indicator in [
                        '429', 'rate limit', 'quota', 'insufficient credits',
                        'billing', 'payment required', 'too many requests'
                    ]):
                        raise PerplexityRateLimitError(sanitized_error) from e

                # For other errors, retry with exponential backoff
                if attempt < max_retries - 1:
                    wait_time = settings.RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                    print(f"⚠️  API call failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                    print(f"   Error: {sanitized_error}")
                    time.sleep(wait_time)
                else:
                    print(f"❌ API call failed after {max_retries} attempts")

        # If we exhausted all retries, provide detailed error message
        sanitized_last_error = sanitize_text(str(last_exception))
        error_msg = (
            f"\n❌ Perplexity API call failed after {max_retries} attempts.\n\n"
            f"Last error: {sanitized_last_error}\n\n"
            f"Possible causes:\n"
            f"  • Network connectivity issues\n"
            f"  • API service temporarily unavailable\n"
            f"  • Request timeout (current timeout: {timeout}s)\n\n"
            f"Suggestions:\n"
            f"  • Check your internet connection\n"
            f"  • Try again in a few minutes\n"
            f"  • Check Perplexity API status\n"
            f"  • Verify your API credits at: https://www.perplexity.ai/account/api/billing\n"
        )
        raise PerplexityAPIError(error_msg) from last_exception

    def parse_json_response(self, response_text: str) -> dict:
        """
        Parse JSON from Perplexity response, handling various formats.

        Args:
            response_text: Raw response text from Perplexity

        Returns:
            Parsed JSON as dictionary

        Raises:
            json.JSONDecodeError: If unable to parse JSON
        """
        # Try to parse as-is
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            if end > start:
                json_str = response_text[start:end].strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

        # Try to extract JSON from triple backticks without language tag
        if "```" in response_text:
            parts = response_text.split("```")
            for part in parts[1::2]:  # Get content between code blocks
                try:
                    return json.loads(part.strip())
                except json.JSONDecodeError:
                    continue

        # Try to find JSON object/array in the text
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start_idx = response_text.find(start_char)
            end_idx = response_text.rfind(end_char)
            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

        # If all else fails, raise the original error
        raise json.JSONDecodeError(
            "Could not extract valid JSON from response",
            response_text,
            0
        )


# Global client instances (one per provider)
_clients: dict[str, Any] = {}


def get_client(provider: Optional[str] = None):
    """
    Get or create the research client for the specified provider.

    Args:
        provider: "perplexity" or "anthropic". Defaults to settings.DEFAULT_PROVIDER.

    Returns:
        PerplexityClient or AnthropicClient instance

    Raises:
        ValueError: If the provider is not available (API key not set)
    """
    global _clients

    if provider is None:
        provider = settings.DEFAULT_PROVIDER

    if provider not in settings.AVAILABLE_PROVIDERS:
        available = ", ".join(settings.AVAILABLE_PROVIDERS)
        raise ValueError(
            f"Provider '{provider}' is not available. "
            f"Set the appropriate API key in .env. "
            f"Available providers: {available}"
        )

    if provider not in _clients:
        if provider == "perplexity":
            _clients[provider] = PerplexityClient()
        elif provider == "anthropic":
            from research.anthropic_client import AnthropicClient
            _clients[provider] = AnthropicClient()

    return _clients[provider]
