"""
Test script for chart generation functionality.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_chart_generation():
    """Test chart generation with mock data."""
    print("=" * 60)
    print("Testing Chart Generation")
    print("=" * 60)

    try:
        from models.suburb_metrics import (
            SuburbMetrics,
            SuburbIdentification,
            MarketMetricsCurrent,
            MarketMetricsHistory,
            GrowthProjections,
            TimePoint
        )
        from models.run_result import SuburbReport
        from reporting.charts import (
            generate_price_history_chart,
            generate_dom_history_chart,
            generate_growth_projection_chart,
            generate_comparison_chart,
            generate_all_suburb_charts,
            generate_overview_charts
        )

        # Create test output directory
        test_dir = Path(__file__).parent / "test_output" / "charts"
        test_dir.mkdir(parents=True, exist_ok=True)

        print(f"\nTest output directory: {test_dir}")

        # Create mock suburb with data
        mock_suburb = SuburbMetrics(
            identification=SuburbIdentification(
                name="Test Suburb",
                state="QLD",
                lga="Brisbane",
                region="Greater Brisbane"
            ),
            market_current=MarketMetricsCurrent(median_price=650000),
            market_history=MarketMetricsHistory(
                price_history=[
                    TimePoint(year=2020, value=520000),
                    TimePoint(year=2021, value=550000),
                    TimePoint(year=2022, value=590000),
                    TimePoint(year=2023, value=620000),
                    TimePoint(year=2024, value=650000),
                ],
                dom_history=[
                    TimePoint(year=2020, value=45),
                    TimePoint(year=2021, value=38),
                    TimePoint(year=2022, value=42),
                    TimePoint(year=2023, value=35),
                    TimePoint(year=2024, value=32),
                ]
            ),
            growth_projections=GrowthProjections(
                projected_growth_pct={
                    1: 5.2,
                    2: 11.5,
                    3: 18.3,
                    5: 32.5,
                    10: 78.2,
                    25: 245.0
                },
                confidence_intervals={
                    1: (3.5, 7.0),
                    2: (8.0, 15.0),
                    3: (13.0, 24.0),
                    5: (22.0, 43.0),
                    10: (55.0, 102.0),
                    25: (180.0, 310.0)
                },
                growth_score=85.5,
                composite_score=78.2
            )
        )

        print("\n✓ Created mock suburb data")

        # Test 1: Price history chart
        print("\n1. Testing price history chart...")
        price_chart_path = test_dir / "test_price_history.png"
        result = generate_price_history_chart(mock_suburb, price_chart_path)
        if result and price_chart_path.exists():
            print(f"✓ Price history chart generated: {price_chart_path.name}")
            print(f"  File size: {price_chart_path.stat().st_size:,} bytes")
        else:
            print("✗ Price history chart generation failed")
            return False

        # Test 2: DOM history chart
        print("\n2. Testing DOM history chart...")
        dom_chart_path = test_dir / "test_dom_history.png"
        result = generate_dom_history_chart(mock_suburb, dom_chart_path)
        if result and dom_chart_path.exists():
            print(f"✓ DOM history chart generated: {dom_chart_path.name}")
            print(f"  File size: {dom_chart_path.stat().st_size:,} bytes")
        else:
            print("✗ DOM history chart generation failed")
            return False

        # Test 3: Growth projection chart
        print("\n3. Testing growth projection chart...")
        growth_chart_path = test_dir / "test_growth_projection.png"
        result = generate_growth_projection_chart(mock_suburb, growth_chart_path)
        if result and growth_chart_path.exists():
            print(f"✓ Growth projection chart generated: {growth_chart_path.name}")
            print(f"  File size: {growth_chart_path.stat().st_size:,} bytes")
        else:
            print("✗ Growth projection chart generation failed")
            return False

        # Test 4: Comparison chart with multiple suburbs
        print("\n4. Testing comparison chart...")

        # Create mock reports
        mock_reports = [
            SuburbReport(metrics=mock_suburb, rank=1),
            SuburbReport(
                metrics=SuburbMetrics(
                    identification=SuburbIdentification(
                        name="Another Suburb",
                        state="QLD",
                        lga="Logan",
                        region="Greater Brisbane"
                    ),
                    market_current=MarketMetricsCurrent(median_price=580000),
                    growth_projections=GrowthProjections(
                        projected_growth_pct={5: 38.2},
                        growth_score=90.0,
                        composite_score=82.5
                    )
                ),
                rank=2
            ),
            SuburbReport(
                metrics=SuburbMetrics(
                    identification=SuburbIdentification(
                        name="Third Suburb",
                        state="QLD",
                        lga="Ipswich",
                        region="Greater Brisbane"
                    ),
                    market_current=MarketMetricsCurrent(median_price=620000),
                    growth_projections=GrowthProjections(
                        projected_growth_pct={5: 28.5},
                        growth_score=78.0,
                        composite_score=72.0
                    )
                ),
                rank=3
            )
        ]

        comparison_chart_path = test_dir / "test_comparison.png"
        result = generate_comparison_chart(mock_reports, comparison_chart_path, metric='5yr_growth')
        if result and comparison_chart_path.exists():
            print(f"✓ Comparison chart generated: {comparison_chart_path.name}")
            print(f"  File size: {comparison_chart_path.stat().st_size:,} bytes")
        else:
            print("✗ Comparison chart generation failed")
            return False

        # Test 5: All suburb charts
        print("\n5. Testing generate_all_suburb_charts...")
        report = SuburbReport(metrics=mock_suburb, rank=1)
        charts = generate_all_suburb_charts(report, test_dir)
        print(f"✓ Generated {len(charts)} charts for suburb:")
        for name, filename in charts.items():
            print(f"  - {name}: {filename}")

        # Test 6: Overview charts
        print("\n6. Testing generate_overview_charts...")
        overview_charts = generate_overview_charts(mock_reports, test_dir)
        print(f"✓ Generated {len(overview_charts)} overview charts:")
        for name, filename in overview_charts.items():
            print(f"  - {name}: {filename}")

        print("\n" + "=" * 60)
        print("✓ All chart generation tests passed!")
        print(f"\nGenerated charts saved to: {test_dir}")
        print("\nYou can view the charts by opening the PNG files:")
        print(f"  open {test_dir}")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n✗ Chart generation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_chart_generation()
    sys.exit(0 if success else 1)
