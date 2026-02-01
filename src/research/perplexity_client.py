"""
Perplexity API client wrapper with retry logic and error handling.
"""
import json
import time
from typing import Optional, Any
import os

from config import settings


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
                if attempt < max_retries - 1:
                    wait_time = settings.RETRY_DELAY * (attempt + 1)
                    print(f"API call failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"API call failed after {max_retries} attempts: {e}")

        raise Exception(f"Perplexity API call failed after {max_retries} attempts: {last_exception}")

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
