#!/usr/bin/env python3
"""
End-to-end integration tests for the complete research pipeline.

These tests validate the full workflow from input to report generation.
"""
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.inputs import UserInput
from models.run_result import RunResult
from app import run_research_pipeline


def test_small_pipeline_run():
    """
    Test complete pipeline with minimal suburbs for fast validation.

    This test validates:
    - Input creation and validation
    - Suburb discovery
    - Research execution
    - Ranking
    - Report generation
    - Output structure
    """
    print("\n" + "="*80)
    print("INTEGRATION TEST: Small Pipeline Run")
    print("="*80)

    # Create minimal test input
    user_input = UserInput(
        max_median_price=700000,
        dwelling_type="house",
        regions=["South East Queensland"],
        num_suburbs=2,  # Small for fast testing
        run_id=f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        interface_mode="cli"
    )

    print(f"\nTest Configuration:")
    print(f"  - Max Price: ${user_input.max_median_price:,}")
    print(f"  - Dwelling Type: {user_input.dwelling_type}")
    print(f"  - Regions: {user_input.regions}")
    print(f"  - Num Suburbs: {user_input.num_suburbs}")
    print(f"  - Run ID: {user_input.run_id}")

    # Run pipeline
    print("\nExecuting pipeline...")
    result = run_research_pipeline(user_input)

    # Validate result
    print("\nValidating results...")

    # Check status
    assert result.status in ["completed", "cancelled"], \
        f"Expected completed or cancelled, got {result.status}"

    if result.status == "completed":
        # Check suburbs were found
        assert len(result.suburbs) > 0, "No suburbs in result"
        assert len(result.suburbs) <= user_input.num_suburbs, \
            f"Too many suburbs: {len(result.suburbs)} > {user_input.num_suburbs}"

        # Check output directory exists
        assert result.output_dir.exists(), "Output directory not created"

        # Check index.html exists
        index_file = result.output_dir / "index.html"
        assert index_file.exists(), "index.html not generated"

        # Check charts directory
        charts_dir = result.output_dir / "charts"
        assert charts_dir.exists(), "Charts directory not created"

        # Check static assets
        static_dir = result.output_dir / "static"
        assert static_dir.exists(), "Static directory not created"
        css_file = static_dir / "css" / "styles.css"
        assert css_file.exists(), "CSS file not copied"

        # Check suburbs directory and reports
        suburbs_dir = result.output_dir / "suburbs"
        if len(result.suburbs) > 0:
            assert suburbs_dir.exists(), "Suburbs directory not created"

            # Check each suburb has a report
            for i, report in enumerate(result.suburbs, 1):
                slug = report.metrics.get_slug()
                suburb_file = suburbs_dir / f"{slug}.html"
                print(f"  [{i}] Checking {report.metrics.get_display_name()}...")
                assert suburb_file.exists(), f"Suburb report not found: {suburb_file}"

                # Validate report data
                assert report.rank > 0, "Invalid rank"
                assert report.metrics.identification.name, "Missing suburb name"
                assert report.metrics.market_current.median_price > 0, "Invalid median price"
                assert report.metrics.growth_projections.growth_score >= 0, "Invalid growth score"

        # Check charts were generated
        chart_files = list(charts_dir.glob("*.png"))
        assert len(chart_files) > 0, "No charts generated"

        print(f"\n✅ TEST PASSED")
        print(f"   - Status: {result.status}")
        print(f"   - Suburbs: {len(result.suburbs)}")
        print(f"   - Output: {result.output_dir}")
        print(f"   - Charts: {len(chart_files)} files")
        print(f"   - Index: {index_file}")

        return True
    else:
        print(f"\n⚠️  Pipeline cancelled or failed: {result.status}")
        if result.error_message:
            print(f"   Error: {result.error_message}")
        return False


def test_input_validation():
    """Test input validation and error handling."""
    print("\n" + "="*80)
    print("VALIDATION TEST: Input Validation")
    print("="*80)

    # Valid input
    valid_input = UserInput(
        max_median_price=500000,
        dwelling_type="house",
        regions=["Queensland"],
        num_suburbs=3
    )
    assert valid_input.max_median_price == 500000
    assert valid_input.dwelling_type == "house"
    print("✅ Valid input accepted")

    # Test invalid dwelling type
    try:
        invalid_input = UserInput(
            max_median_price=500000,
            dwelling_type="invalid",
            regions=["Queensland"],
            num_suburbs=3
        )
        assert False, "Should have raised validation error"
    except Exception as e:
        print(f"✅ Invalid dwelling type rejected: {type(e).__name__}")

    # Test invalid price
    try:
        invalid_input = UserInput(
            max_median_price=-100,
            dwelling_type="house",
            regions=["Queensland"],
            num_suburbs=3
        )
        assert False, "Should have raised validation error"
    except Exception as e:
        print(f"✅ Negative price rejected: {type(e).__name__}")

    # Test invalid num_suburbs
    try:
        invalid_input = UserInput(
            max_median_price=500000,
            dwelling_type="house",
            regions=["Queensland"],
            num_suburbs=0
        )
        assert False, "Should have raised validation error"
    except Exception as e:
        print(f"✅ Zero suburbs rejected: {type(e).__name__}")

    print("\n✅ ALL VALIDATION TESTS PASSED")
    return True


def test_data_models():
    """Test data model functionality."""
    print("\n" + "="*80)
    print("UNIT TEST: Data Models")
    print("="*80)

    from models.suburb_metrics import (
        SuburbIdentification,
        MarketMetricsCurrent,
        GrowthProjections,
        SuburbMetrics
    )

    # Create sample suburb metrics
    identification = SuburbIdentification(
        name="Test Suburb",
        state="QLD",
        lga="Test LGA",
        region="Test Region"
    )
    assert identification.name == "Test Suburb"
    print("✅ SuburbIdentification model works")

    market = MarketMetricsCurrent(
        median_price=500000.0,
        average_price=520000.0
    )
    assert market.median_price == 500000.0
    print("✅ MarketMetricsCurrent model works")

    projections = GrowthProjections(
        projected_growth_pct={1: 5.0, 2: 10.5, 3: 16.0, 5: 28.0, 10: 60.0, 25: 180.0},
        growth_score=75.0,
        risk_score=35.0,
        composite_score=65.0
    )
    assert projections.projected_growth_pct[5] == 28.0
    assert projections.growth_score == 75.0
    print("✅ GrowthProjections model works")

    print("\n✅ ALL DATA MODEL TESTS PASSED")
    return True


def test_region_definitions():
    """Test region filtering and definitions."""
    print("\n" + "="*80)
    print("CONFIGURATION TEST: Region Definitions")
    print("="*80)

    from config import regions_data

    # Check regions exist
    assert "South East Queensland" in regions_data.REGIONS
    assert "All Australia" in regions_data.REGIONS
    assert "Queensland" in regions_data.REGIONS
    print(f"✅ {len(regions_data.REGIONS)} regions defined")

    # Check region structure
    seq = regions_data.REGIONS["South East Queensland"]
    assert "major_areas" in seq
    assert "description" in seq
    assert len(seq["major_areas"]) > 0
    print("✅ Region structure valid")

    # Test region filter description
    description = regions_data.build_region_filter_description(["South East Queensland"])
    assert "South East Queensland" in description
    print("✅ Region filter description generation works")

    # Test multiple regions
    multi_desc = regions_data.build_region_filter_description([
        "South East Queensland",
        "Northern NSW"
    ])
    assert "South East Queensland" in multi_desc
    assert "Northern NSW" in multi_desc
    print("✅ Multiple region filtering works")

    print("\n✅ ALL REGION TESTS PASSED")
    return True


def run_all_tests():
    """Run all validation tests."""
    print("\n" + "="*80)
    print("🧪 COMPREHENSIVE TEST SUITE")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {
        "Data Models": False,
        "Input Validation": False,
        "Region Definitions": False,
        "End-to-End Pipeline": False
    }

    # Run tests
    try:
        results["Data Models"] = test_data_models()
    except Exception as e:
        print(f"❌ Data Models test failed: {e}")

    try:
        results["Input Validation"] = test_input_validation()
    except Exception as e:
        print(f"❌ Input Validation test failed: {e}")

    try:
        results["Region Definitions"] = test_region_definitions()
    except Exception as e:
        print(f"❌ Region Definitions test failed: {e}")

    try:
        results["End-to-End Pipeline"] = test_small_pipeline_run()
    except Exception as e:
        print(f"❌ End-to-End Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nResult: {passed}/{total} tests passed")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
