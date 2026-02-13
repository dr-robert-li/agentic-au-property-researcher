"""
Test script for configuration and data models.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_config():
    """Test configuration loading."""
    print("Testing configuration...")
    try:
        from config import settings, regions_data

        print(f"✓ Settings loaded successfully")
        print(f"  - API Key present: {'Yes' if settings.PERPLEXITY_API_KEY else 'No'}")
        print(f"  - Output dir: {settings.OUTPUT_DIR}")
        print(f"  - Default port: {settings.DEFAULT_PORT}")

        regions = regions_data.get_region_names()
        print(f"✓ Regions data loaded: {len(regions)} regions available")
        print(f"  - Sample regions: {', '.join(regions[:5])}")

        # Test region filter
        desc = regions_data.build_region_filter_description(["South East Queensland", "Northern NSW"])
        print(f"  - Filter description test: {desc}")

        return True
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_models():
    """Test data models."""
    print("\nTesting data models...")
    try:
        from models.inputs import UserInput
        from models.suburb_metrics import SuburbMetrics, SuburbIdentification, MarketMetricsCurrent, GrowthProjections
        from models.run_result import RunResult, SuburbReport

        # Test UserInput
        user_input = UserInput(
            max_median_price=800000,
            dwelling_type="house",
            regions=["South East Queensland"],
            num_suburbs=5
        )
        print(f"✓ UserInput model works")
        print(f"  - Run ID: {user_input.run_id}")
        print(f"  - Region description: {user_input.get_region_description()}")

        # Test SuburbMetrics
        metrics = SuburbMetrics(
            identification=SuburbIdentification(
                name="Test Suburb",
                state="QLD",
                lga="Brisbane",
                region="South East Queensland"
            ),
            market_current=MarketMetricsCurrent(
                median_price=650000
            ),
            growth_projections=GrowthProjections(
                projected_growth_pct={1: 5.0, 2: 10.5, 3: 16.2, 5: 28.5, 10: 65.0, 25: 180.0},
                growth_score=75.5
            )
        )
        print(f"✓ SuburbMetrics model works")
        print(f"  - Display name: {metrics.get_display_name()}")
        print(f"  - Slug: {metrics.get_slug()}")

        # Test SuburbReport
        report = SuburbReport(
            metrics=metrics,
            rank=1
        )
        print(f"✓ SuburbReport model works")

        # Test RunResult
        run_result = RunResult(
            run_id="test-run",
            user_input=user_input,
            suburbs=[report],
            status="completed"
        )
        print(f"✓ RunResult model works")
        print(f"  - Summary: {run_result.to_summary_dict()}")

        return True
    except Exception as e:
        print(f"✗ Model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Configuration and Data Models")
    print("=" * 60)

    success = True
    success = test_config() and success
    success = test_models() and success

    print("\n" + "=" * 60)
    if success:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed")
    print("=" * 60)

    sys.exit(0 if success else 1)
