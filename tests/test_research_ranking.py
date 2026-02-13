"""
Test script for suburb research and ranking functionality.
Tests with mock data for quick validation.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_ranking_logic():
    """Test ranking logic with mock data."""
    print("=" * 60)
    print("Testing Ranking Logic (Mock Data)")
    print("=" * 60)

    try:
        from models.suburb_metrics import (
            SuburbMetrics,
            SuburbIdentification,
            MarketMetricsCurrent,
            GrowthProjections
        )
        from research.ranking import (
            rank_suburbs,
            get_ranking_summary,
            calculate_comparison_stats,
            filter_by_criteria
        )

        # Create mock suburb data
        mock_suburbs = [
            SuburbMetrics(
                identification=SuburbIdentification(
                    name="Acacia Ridge",
                    state="QLD",
                    lga="Brisbane",
                    region="Greater Brisbane"
                ),
                market_current=MarketMetricsCurrent(median_price=650000),
                growth_projections=GrowthProjections(
                    projected_growth_pct={1: 5.0, 2: 10.5, 3: 16.2, 5: 28.5, 10: 65.0, 25: 180.0},
                    growth_score=82.5,
                    risk_score=35.0,
                    composite_score=75.8
                )
            ),
            SuburbMetrics(
                identification=SuburbIdentification(
                    name="Woodridge",
                    state="QLD",
                    lga="Logan",
                    region="Greater Brisbane"
                ),
                market_current=MarketMetricsCurrent(median_price=580000),
                growth_projections=GrowthProjections(
                    projected_growth_pct={1: 6.2, 2: 13.0, 3: 20.5, 5: 35.2, 10: 82.0, 25: 220.0},
                    growth_score=88.2,
                    risk_score=45.0,
                    composite_score=78.5
                )
            ),
            SuburbMetrics(
                identification=SuburbIdentification(
                    name="Redbank Plains",
                    state="QLD",
                    lga="Ipswich",
                    region="Greater Brisbane"
                ),
                market_current=MarketMetricsCurrent(median_price=620000),
                growth_projections=GrowthProjections(
                    projected_growth_pct={1: 4.8, 2: 9.8, 3: 15.0, 5: 26.0, 10: 58.0, 25: 160.0},
                    growth_score=78.0,
                    risk_score=38.0,
                    composite_score=72.5
                )
            ),
            SuburbMetrics(
                identification=SuburbIdentification(
                    name="Caboolture",
                    state="QLD",
                    lga="Moreton Bay",
                    region="South East Queensland"
                ),
                market_current=MarketMetricsCurrent(median_price=595000),
                growth_projections=GrowthProjections(
                    projected_growth_pct={1: 5.5, 2: 11.5, 3: 18.0, 5: 31.0, 10: 72.0, 25: 200.0},
                    growth_score=85.0,
                    risk_score=40.0,
                    composite_score=77.0
                )
            )
        ]

        print(f"\n✓ Created {len(mock_suburbs)} mock suburbs")

        # Test ranking by composite score
        print("\n1. Testing ranking by composite score...")
        reports = rank_suburbs(mock_suburbs, ranking_method="composite_score")
        print(f"✓ Ranked {len(reports)} suburbs")
        print(f"  Top suburb: {reports[0].metrics.get_display_name()}")
        print(f"  Composite score: {reports[0].metrics.growth_projections.composite_score}")

        # Test ranking by growth score
        print("\n2. Testing ranking by growth score...")
        reports_growth = rank_suburbs(mock_suburbs, ranking_method="growth_score")
        print(f"✓ Ranked {len(reports_growth)} suburbs")
        print(f"  Top suburb: {reports_growth[0].metrics.get_display_name()}")
        print(f"  Growth score: {reports_growth[0].metrics.growth_projections.growth_score}")

        # Test ranking by 5-year growth
        print("\n3. Testing ranking by 5-year growth...")
        reports_5yr = rank_suburbs(mock_suburbs, ranking_method="5yr_growth")
        print(f"✓ Ranked {len(reports_5yr)} suburbs")
        print(f"  Top suburb: {reports_5yr[0].metrics.get_display_name()}")
        print(f"  5-year growth: {reports_5yr[0].metrics.growth_projections.projected_growth_pct[5]}%")

        # Test top N selection
        print("\n4. Testing top N selection...")
        top_2 = rank_suburbs(mock_suburbs, top_n=2)
        print(f"✓ Selected top {len(top_2)} suburbs")
        for report in top_2:
            print(f"  #{report.rank}: {report.metrics.get_display_name()}")

        # Test ranking summary
        print("\n5. Testing ranking summary...")
        summary = get_ranking_summary(reports)
        print(summary)

        # Test comparison stats
        print("\n6. Testing comparison statistics...")
        stats = calculate_comparison_stats(reports)
        print(f"✓ Calculated statistics:")
        print(f"  Total suburbs: {stats['total_suburbs']}")
        print(f"  Price range: ${stats['price_range']['min']:,.0f} - ${stats['price_range']['max']:,.0f}")
        print(f"  Avg price: ${stats['price_range']['avg']:,.0f}")
        print(f"  Growth score range: {stats['growth_score_range']['min']:.1f} - {stats['growth_score_range']['max']:.1f}")
        print(f"  Top suburb: {stats['top_suburb']}")

        # Test filtering
        print("\n7. Testing filtering...")
        filtered = filter_by_criteria(
            mock_suburbs,
            min_growth_score=80.0,
            max_price=600000
        )
        print(f"✓ Filtered suburbs (growth > 80, price < $600k): {len(filtered)}")
        for m in filtered:
            print(f"  - {m.get_display_name()}: ${m.market_current.median_price:,.0f}, score {m.growth_projections.growth_score}")

        print("\n" + "=" * 60)
        print("✓ All ranking tests passed!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Ranking test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_research_fallback():
    """Test research fallback functionality."""
    print("\n" + "=" * 60)
    print("Testing Research Fallback Logic")
    print("=" * 60)

    try:
        from research.suburb_discovery import SuburbCandidate
        from research.suburb_research import _create_fallback_metrics

        # Create a mock candidate
        candidate = SuburbCandidate({
            "name": "Test Suburb",
            "state": "QLD",
            "lga": "Test LGA",
            "region": "Test Region",
            "median_price": 500000,
            "growth_signals": ["New train station", "Shopping center development"],
            "major_events_relevance": "Near Olympic venue",
            "data_quality": "medium"
        })

        print(f"\n✓ Created mock candidate: {candidate}")

        # Test fallback metrics creation
        print("\nTesting fallback metrics creation...")
        metrics = _create_fallback_metrics(candidate)
        print(f"✓ Fallback metrics created")
        print(f"  Name: {metrics.get_display_name()}")
        print(f"  Price: ${metrics.market_current.median_price:,.0f}")
        print(f"  Growth drivers: {len(metrics.growth_projections.key_drivers)}")
        print(f"  5-year growth estimate: {metrics.growth_projections.projected_growth_pct[5]}%")

        print("\n" + "=" * 60)
        print("✓ Research fallback test passed!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Research fallback test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("*" * 60)
    print("SUBURB RESEARCH & RANKING TEST SUITE")
    print("*" * 60)

    success = True
    success = test_ranking_logic() and success
    success = test_research_fallback() and success

    print("\n" + "*" * 60)
    if success:
        print("✓ ALL TESTS PASSED!")
    else:
        print("✗ SOME TESTS FAILED")
    print("*" * 60)

    sys.exit(0 if success else 1)
