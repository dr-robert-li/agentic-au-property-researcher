"""
Test script for suburb discovery functionality.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_suburb_discovery():
    """Test suburb discovery with a small search."""
    print("=" * 60)
    print("Testing Suburb Discovery")
    print("=" * 60)

    try:
        from models.inputs import UserInput
        from research.suburb_discovery import discover_suburbs, get_discovery_summary

        # Create a test search - looking for affordable houses in SEQ
        print("\nCreating test search parameters...")
        user_input = UserInput(
            max_median_price=700000,
            dwelling_type="house",
            regions=["South East Queensland"],
            num_suburbs=5,
            interface_mode="cli"
        )

        print(f"✓ Search parameters:")
        print(f"  - Max price: ${user_input.max_median_price:,.0f}")
        print(f"  - Dwelling type: {user_input.dwelling_type}")
        print(f"  - Regions: {', '.join(user_input.regions)}")
        print(f"  - Target suburbs: {user_input.num_suburbs}")

        # Run discovery
        print(f"\nRunning suburb discovery...")
        print("(This may take 1-3 minutes with deep research...)")
        candidates = discover_suburbs(user_input, max_results=15)

        if not candidates:
            print("✗ No suburbs found!")
            return False

        print(f"\n✓ Discovery completed successfully!")
        print(f"  - Found {len(candidates)} suburbs")

        # Show summary
        print("\n" + "=" * 60)
        print("DISCOVERY SUMMARY")
        print("=" * 60)
        summary = get_discovery_summary(candidates)
        print(summary)

        # Show detailed info for first few
        print("\n" + "=" * 60)
        print("DETAILED INFO (First 3 suburbs)")
        print("=" * 60)
        for i, candidate in enumerate(candidates[:3], 1):
            print(f"\n{i}. {candidate.name}, {candidate.state}")
            print(f"   LGA: {candidate.lga}")
            print(f"   Region: {candidate.region}")
            print(f"   Median Price: ${candidate.median_price:,.0f}")
            print(f"   Data Quality: {candidate.data_quality}")
            if candidate.growth_signals:
                print(f"   Growth Signals:")
                for signal in candidate.growth_signals[:3]:
                    print(f"     - {signal}")
            if candidate.major_events_relevance:
                print(f"   Events: {candidate.major_events_relevance[:100]}...")

        print("\n" + "=" * 60)
        print("✓ Suburb discovery test passed!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Suburb discovery test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_suburb_discovery()
    sys.exit(0 if success else 1)
