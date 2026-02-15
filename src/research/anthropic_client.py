"""
Anthropic Claude API client wrapper with retry logic and error handling.
Provides the same interface as PerplexityClient for interchangeable use.
"""
import json
import time
from typing import Optional

from config import settings
from security.exceptions import RateLimitError, AuthenticationError, APIError, TimeoutError, NetworkError
from security.sanitization import sanitize_text


# Provider-specific exception subclasses
class AnthropicAPIError(APIError):
    """Base exception for Anthropic API errors."""
    def __init__(self, message: str = None, status_code: Optional[int] = None):
        default_msg = (
            "\n⚠️  ANTHROPIC API ERROR\n\n"
            "The Anthropic API request failed.\n\n"
            "Possible causes:\n"
            "  • Network connectivity issues\n"
            "  • API service temporarily unavailable\n"
            "  • Request timeout\n\n"
            "Suggestions:\n"
            "  • Check your internet connection\n"
            "  • Try again in a few minutes\n"
            "  • Check Anthropic API status at: https://status.anthropic.com\n"
            "  • Verify your API key at: https://console.anthropic.com/settings/keys\n"
        )
        super().__init__(
            message=message or default_msg,
            status_code=status_code,
            provider="anthropic"
        )


class AnthropicRateLimitError(RateLimitError):
    """Exception raised when API rate limit is exceeded."""
    def __init__(self, message: str = None, retry_after: Optional[int] = 60):
        default_msg = (
            "\n⚠️  API RATE LIMIT EXCEEDED\n\n"
            "Your Anthropic API request was rate limited. This typically means:\n"
            "  1. You've exceeded your API rate limit\n"
            "  2. Your API credit balance is insufficient\n\n"
            "ACTION REQUIRED:\n"
            "  → Check your usage at: https://console.anthropic.com/settings/billing\n"
            "  → If rate limited, wait a few minutes and try again\n"
            "  → Consider reducing the number of suburbs\n"
        )
        super().__init__(
            message=message or default_msg,
            retry_after=retry_after,
            provider="anthropic"
        )


class AnthropicAuthError(AuthenticationError):
    """Exception raised when API authentication fails."""
    def __init__(self, message: str = None):
        default_msg = (
            "\n⚠️  API AUTHENTICATION FAILED\n\n"
            "Your Anthropic API key appears to be invalid or inactive.\n\n"
            "ACTION REQUIRED:\n"
            "  → Check your API key in the .env file\n"
            "  → Verify the key at: https://console.anthropic.com/settings/keys\n"
            "  → Generate a new API key if needed\n"
        )
        super().__init__(message=message or default_msg, provider="anthropic")


class AnthropicClient:
    """Wrapper for Anthropic Claude API, matching PerplexityClient interface."""

    def __init__(self):
        """Initialize the Anthropic client."""
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            self.model = settings.DEFAULT_ANTHROPIC_MODEL
            self.initialized = True
        except ImportError:
            print("Warning: anthropic package not installed. Install with: pip install anthropic")
            self.initialized = False
        except Exception as e:
            print(f"Warning: Failed to initialize Anthropic client: {e}")
            self.initialized = False

    def test_connection(self) -> bool:
        """Test the API connection with a simple query."""
        if not self.initialized:
            return False

        try:
            response = self.call_deep_research(
                prompt="What is the capital of Australia? Reply in one sentence.",
                timeout=30
            )
            return response is not None and len(response) > 0
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    def call_deep_research(
        self,
        prompt: str,
        preset: str = None,
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        timeout: int = None,
        max_retries: int = None
    ) -> str:
        """
        Make a research call to Anthropic Claude.

        Uses extended thinking for deep analysis. The preset parameter is
        accepted for interface compatibility but not used (Anthropic doesn't
        have presets).

        Args:
            prompt: The research prompt/question
            preset: Ignored (for interface compatibility with PerplexityClient)
            model: Optional model override
            tools: Ignored (for interface compatibility)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts

        Returns:
            Response text from Claude

        Raises:
            AnthropicAPIError: If the API call fails after retries
        """
        if not self.initialized:
            raise AnthropicAPIError("Anthropic client not initialized")

        if timeout is None:
            timeout = settings.API_TIMEOUT
        if max_retries is None:
            max_retries = settings.MAX_RETRIES

        use_model = model or self.model
        last_exception = None

        # Add context about data limitations since Claude doesn't have live web search
        augmented_prompt = (
            "IMPORTANT: You are being used as a research provider without live web search. "
            "Base your analysis on your training data. Where you have concrete knowledge of "
            "Australian property data, demographics, infrastructure projects, and market trends, "
            "provide it. Where data is uncertain, clearly indicate this and provide your best "
            "estimates with appropriate caveats.\n\n"
            f"{prompt}"
        )

        for attempt in range(max_retries):
            try:
                import anthropic

                response = self.client.messages.create(
                    model=use_model,
                    max_tokens=16384,
                    messages=[
                        {"role": "user", "content": augmented_prompt}
                    ]
                )

                # Extract text from response
                if response.content:
                    text_parts = []
                    for block in response.content:
                        if hasattr(block, 'text'):
                            text_parts.append(block.text)
                    return "\n".join(text_parts)

                return ""

            except Exception as e:
                last_exception = e
                import anthropic

                # Sanitize error message before any processing
                sanitized_error = sanitize_text(str(e))

                # Use isinstance checks for Anthropic SDK exceptions
                if isinstance(e, anthropic.RateLimitError):
                    # Extract retry_after if available
                    retry_after = getattr(e, 'retry_after', None) or 60
                    raise AnthropicRateLimitError(sanitized_error, retry_after=retry_after) from e

                elif isinstance(e, anthropic.AuthenticationError):
                    raise AnthropicAuthError(sanitized_error) from e

                elif isinstance(e, anthropic.APIConnectionError):
                    raise NetworkError(sanitized_error, provider="anthropic") from e

                elif isinstance(e, anthropic.APITimeoutError):
                    raise TimeoutError(sanitized_error, timeout_seconds=timeout, provider="anthropic") from e

                elif isinstance(e, anthropic.APIStatusError):
                    # Extract status code
                    status_code = getattr(e, 'status_code', None)
                    if status_code and status_code >= 500:
                        raise AnthropicAPIError(sanitized_error, status_code=status_code) from e
                    elif status_code == 429:
                        # Secondary catch for rate limits not caught by RateLimitError
                        raise AnthropicRateLimitError(sanitized_error) from e
                    elif status_code in (401, 403):
                        # Secondary catch for auth not caught by AuthenticationError
                        raise AnthropicAuthError(sanitized_error) from e
                    else:
                        # Other status errors
                        raise AnthropicAPIError(sanitized_error, status_code=status_code) from e

                # For other errors, retry with exponential backoff
                if attempt < max_retries - 1:
                    wait_time = settings.RETRY_DELAY * (2 ** attempt)
                    print(f"⚠️  API call failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                    print(f"   Error: {sanitized_error}")
                    time.sleep(wait_time)
                else:
                    print(f"❌ API call failed after {max_retries} attempts")

        sanitized_last_error = sanitize_text(str(last_exception))
        error_msg = (
            f"\n❌ Anthropic API call failed after {max_retries} attempts.\n\n"
            f"Last error: {sanitized_last_error}\n\n"
            f"Possible causes:\n"
            f"  • Network connectivity issues\n"
            f"  • API service temporarily unavailable\n"
            f"  • Request timeout (current timeout: {timeout}s)\n\n"
            f"Suggestions:\n"
            f"  • Check your internet connection\n"
            f"  • Try again in a few minutes\n"
            f"  • Check Anthropic API status at: https://status.anthropic.com\n"
            f"  • Verify your API key at: https://console.anthropic.com/settings/keys\n"
        )
        raise AnthropicAPIError(error_msg) from last_exception

    def parse_json_response(self, response_text: str) -> dict:
        """
        Parse JSON from Claude response, handling various formats.

        Args:
            response_text: Raw response text from Claude

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
            for part in parts[1::2]:
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

        raise json.JSONDecodeError(
            "Could not extract valid JSON from response",
            response_text,
            0
        )
