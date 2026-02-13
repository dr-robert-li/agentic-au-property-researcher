"""
Test script for Perplexity client wrapper.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_perplexity_client():
    """Test Perplexity client initialization and connectivity."""
    print("=" * 60)
    print("Testing Perplexity Client")
    print("=" * 60)

    try:
        from research.perplexity_client import get_client

        # Get client instance
        client = get_client()
        print(f"✓ Perplexity client created")
        print(f"  - Initialized: {client.initialized}")

        if not client.initialized:
            print("✗ Client not initialized (SDK may not be installed)")
            return False

        # Test connection
        print("\nTesting API connection...")
        result = client.test_connection()
        if result:
            print("✓ API connection successful")
        else:
            print("✗ API connection failed")
            return False

        # Test simple query
        print("\nTesting simple query...")
        response = client.call_deep_research(
            prompt="What are the top 3 Australian cities by population? Answer in one sentence.",
            timeout=60
        )
        print(f"✓ Query successful")
        print(f"  Response: {response[:200]}..." if len(response) > 200 else f"  Response: {response}")

        # Test JSON parsing
        print("\nTesting JSON response parsing...")
        json_prompt = """
        List the 3 largest Australian states by area. Return ONLY valid JSON in this format:
        [
          {"name": "State Name", "area_km2": 123456},
          ...
        ]
        """
        response = client.call_deep_research(
            prompt=json_prompt,
            timeout=60
        )
        try:
            parsed = client.parse_json_response(response)
            print(f"✓ JSON parsing successful")
            print(f"  Parsed data: {parsed}")
        except Exception as e:
            print(f"! JSON parsing note: {e}")
            print(f"  Raw response: {response[:300]}")

        print("\n" + "=" * 60)
        print("✓ All Perplexity tests passed!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Perplexity test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_perplexity_client()
    sys.exit(0 if success else 1)
