"""
Perplexity API client wrapper with retry logic and error handling.
"""
import json
import time
from typing import Optional, Any
import os

from config import settings


class PerplexityAPIError(Exception):
    """Base exception for Perplexity API errors."""
    pass


class PerplexityRateLimitError(PerplexityAPIError):
    """Exception raised when API rate limit is exceeded."""
    def __init__(self, message: str = None):
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
        super().__init__(message or default_msg)


class PerplexityAuthError(PerplexityAPIError):
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
        super().__init__(message or default_msg)


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
                error_str = str(e).lower()

                # Check for rate limiting or credit issues (401, 429 errors)
                if any(indicator in error_str for indicator in [
                    '401', 'unauthorized', 'rate limit', 'quota',
                    'insufficient credits', 'billing', 'payment required',
                    '429', 'too many requests'
                ]):
                    raise PerplexityRateLimitError()

                # Check for authentication issues
                if any(indicator in error_str for indicator in [
                    'invalid api key', 'authentication failed', 'invalid key',
                    'api key', 'forbidden', '403'
                ]):
                    raise PerplexityAuthError()

                # For other errors, retry with exponential backoff
                if attempt < max_retries - 1:
                    wait_time = settings.RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                    print(f"⚠️  API call failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                    print(f"   Error: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"❌ API call failed after {max_retries} attempts")

        # If we exhausted all retries, provide detailed error message
        error_msg = (
            f"\n❌ Perplexity API call failed after {max_retries} attempts.\n\n"
            f"Last error: {last_exception}\n\n"
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
        raise PerplexityAPIError(error_msg)

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


# Global client instance
_client: Optional[PerplexityClient] = None


def get_client() -> PerplexityClient:
    """Get or create the global Perplexity client instance."""
    global _client
    if _client is None:
        _client = PerplexityClient()
    return _client
