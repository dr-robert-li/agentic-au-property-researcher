"""
Unit tests for the run comparison module (src/research/comparison.py)
and comparison data models (src/models/comparison.py).

Tests cover:
- Data models (RunSummary, SuburbDelta, SuburbRunMetrics, ComparisonResult)
- Overlap detection
- Delta computation
- Run summary generation
- compare_runs with filesystem reconstruction
- Edge cases: no overlap, single suburb, empty runs
- Error handling: invalid run count, missing runs
"""
import json
import sys
import os
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.inputs import UserInput
from models.suburb_metrics import (
    SuburbMetrics, SuburbIdentification, MarketMetricsCurrent,
    GrowthProjections,
)
from models.run_result import RunResult, SuburbReport
from models.comparison import (
    RunSummary, SuburbDelta, SuburbRunMetrics, ComparisonResult,
)
from research.comparison import (
    compare_runs, find_overlapping_suburbs, compute_run_summary,
    ComparisonError,
)


# ─── Test Data Factories ────────────────────────────────────────────────────

def make_suburb(name, state="QLD", price=500000, growth_score=70,
                composite_score=65, risk_score=30, projected_5yr=15.0,
                rank=1):
    """Create a SuburbReport for testing."""
    return SuburbReport(
        rank=rank,
        metrics=SuburbMetrics(
            identification=SuburbIdentification(
                name=name, state=state, lga="Test LGA", region="Test Region"
            ),
            market_current=MarketMetricsCurrent(median_price=price),
            growth_projections=GrowthProjections(
                projected_growth_pct={1: 3.0, 5: projected_5yr, 10: 30.0, 25: 80.0},
                growth_score=growth_score,
                risk_score=risk_score,
                composite_score=composite_score,
                key_drivers=["Growth driver 1"],
            ),
        ),
    )


def make_user_input(**overrides):
    """Create a UserInput for testing."""
    defaults = dict(
        max_median_price=700000,
        dwelling_type="house",
        regions=["South East Queensland"],
        num_suburbs=5,
        provider="perplexity",
        interface_mode="cli",
        run_id="test-run",
    )
    defaults.update(overrides)
    return UserInput(**defaults)


def make_run_result(run_id, suburbs, **input_overrides):
    """Create a RunResult for testing."""
    user_input = make_user_input(run_id=run_id, **input_overrides)
    return RunResult(
        run_id=run_id,
        user_input=user_input,
        suburbs=suburbs,
        status="completed",
    )


def save_run_metadata(run_result, base_dir):
    """Save a run's metadata to disk for reconstruct_run_result."""
    run_dir = base_dir / run_result.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "index.html").write_text("<html></html>")
    metadata = run_result.model_dump_json(indent=2)
    (run_dir / "run_metadata.json").write_text(metadata)
    return run_dir


passed = 0
failed = 0
errors = []


def run_test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  ✓ {name}")
        passed += 1
    except Exception as e:
        print(f"  ✗ {name}")
        errors.append((name, traceback.format_exc()))
        failed += 1


# ─── Model Tests ─────────────────────────────────────────────────────────────

def test_run_summary_creation():
    """RunSummary can be created with all fields."""
    s = RunSummary(
        run_id="test-1",
        timestamp="2024-01-01T00:00:00",
        dwelling_type="house",
        max_price=700000,
        regions=["QLD"],
        suburb_count=5,
        provider="perplexity",
    )
    assert s.run_id == "test-1"
    assert s.max_price == 700000


def test_suburb_run_metrics():
    """SuburbRunMetrics can be created."""
    m = SuburbRunMetrics(
        run_id="r1",
        median_price=500000,
        growth_score=75,
        composite_score=70,
        projected_5yr=18.0,
        rank=1,
    )
    assert m.run_id == "r1"
    assert m.median_price == 500000


def test_suburb_delta_price_delta():
    """SuburbDelta.price_delta computes correctly."""
    delta = SuburbDelta(
        suburb_name="Test",
        state="QLD",
        run_metrics=[
            SuburbRunMetrics(run_id="r1", median_price=500000, composite_score=70),
            SuburbRunMetrics(run_id="r2", median_price=550000, composite_score=75),
        ],
    )
    assert delta.price_delta == 50000


def test_suburb_delta_score_delta():
    """SuburbDelta.score_delta computes correctly."""
    delta = SuburbDelta(
        suburb_name="Test",
        state="QLD",
        run_metrics=[
            SuburbRunMetrics(run_id="r1", median_price=500000, composite_score=70),
            SuburbRunMetrics(run_id="r2", median_price=550000, composite_score=75),
        ],
    )
    assert delta.score_delta == 5.0


def test_suburb_delta_single_run_no_delta():
    """SuburbDelta with single run has None deltas."""
    delta = SuburbDelta(
        suburb_name="Test",
        state="QLD",
        run_metrics=[
            SuburbRunMetrics(run_id="r1", median_price=500000, composite_score=70),
        ],
    )
    assert delta.price_delta is None
    assert delta.score_delta is None


def test_suburb_delta_zero_prices():
    """SuburbDelta with zero prices returns None for price_delta."""
    delta = SuburbDelta(
        suburb_name="Test",
        state="QLD",
        run_metrics=[
            SuburbRunMetrics(run_id="r1", median_price=0, composite_score=70),
            SuburbRunMetrics(run_id="r2", median_price=0, composite_score=75),
        ],
    )
    assert delta.price_delta is None


def test_comparison_result_creation():
    """ComparisonResult can be created with defaults."""
    cr = ComparisonResult()
    assert cr.run_summaries == []
    assert cr.overlapping_suburbs == []
    assert cr.unique_per_run == {}


# ─── compute_run_summary Tests ──────────────────────────────────────────────

def test_compute_run_summary():
    """compute_run_summary extracts correct data."""
    run = make_run_result("run-1", [
        make_suburb("Springfield", rank=1),
        make_suburb("Shelbyville", rank=2),
    ])
    summary = compute_run_summary(run)
    assert summary.run_id == "run-1"
    assert summary.dwelling_type == "house"
    assert summary.max_price == 700000
    assert summary.suburb_count == 2
    assert summary.provider == "perplexity"


def test_compute_run_summary_empty_suburbs():
    """compute_run_summary with no suburbs."""
    run = make_run_result("run-empty", [])
    summary = compute_run_summary(run)
    assert summary.suburb_count == 0


# ─── find_overlapping_suburbs Tests ──────────────────────────────────────────

def test_find_overlap_full():
    """Two runs with same suburbs detected as overlapping."""
    run1 = make_run_result("r1", [
        make_suburb("Springfield", price=500000, composite_score=70, rank=1),
        make_suburb("Shelbyville", price=600000, composite_score=60, rank=2),
    ])
    run2 = make_run_result("r2", [
        make_suburb("Springfield", price=520000, composite_score=72, rank=1),
        make_suburb("Shelbyville", price=610000, composite_score=62, rank=2),
    ])

    overlapping, unique = find_overlapping_suburbs([run1, run2])
    assert len(overlapping) == 2
    assert len(unique["r1"]) == 0
    assert len(unique["r2"]) == 0

    # Check Springfield appears with both runs' metrics
    springfield = next(d for d in overlapping if d.suburb_name == "Springfield")
    assert len(springfield.run_metrics) == 2
    assert springfield.run_metrics[0].median_price == 500000
    assert springfield.run_metrics[1].median_price == 520000


def test_find_overlap_partial():
    """Partial overlap: some suburbs unique to each run."""
    run1 = make_run_result("r1", [
        make_suburb("Springfield", rank=1),
        make_suburb("UniqueA", rank=2),
    ])
    run2 = make_run_result("r2", [
        make_suburb("Springfield", rank=1),
        make_suburb("UniqueB", rank=2),
    ])

    overlapping, unique = find_overlapping_suburbs([run1, run2])
    assert len(overlapping) == 1
    assert overlapping[0].suburb_name == "Springfield"
    assert len(unique["r1"]) == 1
    assert "UniqueA, QLD" in unique["r1"]
    assert len(unique["r2"]) == 1
    assert "UniqueB, QLD" in unique["r2"]


def test_find_overlap_none():
    """No overlap between runs."""
    run1 = make_run_result("r1", [make_suburb("A", rank=1)])
    run2 = make_run_result("r2", [make_suburb("B", rank=1)])

    overlapping, unique = find_overlapping_suburbs([run1, run2])
    assert len(overlapping) == 0
    assert len(unique["r1"]) == 1
    assert len(unique["r2"]) == 1


def test_find_overlap_case_insensitive():
    """Overlap detection is case-insensitive."""
    run1 = make_run_result("r1", [make_suburb("Springfield", state="QLD", rank=1)])
    run2 = make_run_result("r2", [make_suburb("springfield", state="qld", rank=1)])

    overlapping, unique = find_overlapping_suburbs([run1, run2])
    assert len(overlapping) == 1


def test_find_overlap_different_states():
    """Same suburb name in different states are NOT overlapping."""
    run1 = make_run_result("r1", [make_suburb("Springfield", state="QLD", rank=1)])
    run2 = make_run_result("r2", [make_suburb("Springfield", state="NSW", rank=1)])

    overlapping, unique = find_overlapping_suburbs([run1, run2])
    assert len(overlapping) == 0
    assert len(unique["r1"]) == 1
    assert len(unique["r2"]) == 1


def test_find_overlap_three_runs():
    """Three-way overlap detection."""
    run1 = make_run_result("r1", [make_suburb("Springfield", rank=1)])
    run2 = make_run_result("r2", [make_suburb("Springfield", rank=1)])
    run3 = make_run_result("r3", [make_suburb("Springfield", rank=1)])

    overlapping, unique = find_overlapping_suburbs([run1, run2, run3])
    assert len(overlapping) == 1
    assert len(overlapping[0].run_metrics) == 3


def test_find_overlap_sorted_by_score():
    """Overlapping suburbs are sorted by composite score descending."""
    run1 = make_run_result("r1", [
        make_suburb("Low", composite_score=30, rank=2),
        make_suburb("High", composite_score=90, rank=1),
    ])
    run2 = make_run_result("r2", [
        make_suburb("Low", composite_score=35, rank=2),
        make_suburb("High", composite_score=85, rank=1),
    ])

    overlapping, _ = find_overlapping_suburbs([run1, run2])
    assert overlapping[0].suburb_name == "High"
    assert overlapping[1].suburb_name == "Low"


def test_find_overlap_empty_runs():
    """Empty runs produce no overlap."""
    run1 = make_run_result("r1", [])
    run2 = make_run_result("r2", [])

    overlapping, unique = find_overlapping_suburbs([run1, run2])
    assert len(overlapping) == 0


# ─── compare_runs Tests (with filesystem) ────────────────────────────────────

def test_compare_runs_success():
    """compare_runs loads runs from filesystem and compares."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        run1 = make_run_result("run-1", [
            make_suburb("Springfield", price=500000, rank=1),
        ])
        run2 = make_run_result("run-2", [
            make_suburb("Springfield", price=520000, rank=1),
            make_suburb("Shelbyville", price=600000, rank=2),
        ])

        save_run_metadata(run1, base)
        save_run_metadata(run2, base)

        result = compare_runs(["run-1", "run-2"], base)
        assert len(result.run_summaries) == 2
        assert len(result.overlapping_suburbs) == 1
        assert result.overlapping_suburbs[0].suburb_name == "Springfield"
        assert "Shelbyville, QLD" in result.unique_per_run["run-2"]


def test_compare_runs_three():
    """compare_runs works with three runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        for i in range(1, 4):
            run = make_run_result(f"run-{i}", [
                make_suburb("Common", price=500000 + i * 10000, rank=1),
            ])
            save_run_metadata(run, base)

        result = compare_runs(["run-1", "run-2", "run-3"], base)
        assert len(result.run_summaries) == 3
        assert len(result.overlapping_suburbs) == 1
        assert len(result.overlapping_suburbs[0].run_metrics) == 3


def test_compare_runs_too_few():
    """compare_runs rejects fewer than 2 runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            compare_runs(["only-one"], Path(tmpdir))
            assert False, "Should have raised ComparisonError"
        except ComparisonError as e:
            assert "2 or 3" in str(e)


def test_compare_runs_too_many():
    """compare_runs rejects more than 3 runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            compare_runs(["a", "b", "c", "d"], Path(tmpdir))
            assert False, "Should have raised ComparisonError"
        except ComparisonError as e:
            assert "2 or 3" in str(e)


def test_compare_runs_missing_run():
    """compare_runs raises error for missing run directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        run1 = make_run_result("run-1", [make_suburb("A", rank=1)])
        save_run_metadata(run1, base)

        try:
            compare_runs(["run-1", "nonexistent"], base)
            assert False, "Should have raised ComparisonError"
        except ComparisonError as e:
            assert "not found" in str(e)


def test_compare_runs_missing_metadata():
    """compare_runs raises error when metadata file is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        # Create directory without metadata
        run_dir = base / "run-no-meta"
        run_dir.mkdir()
        (run_dir / "index.html").write_text("<html></html>")

        run1 = make_run_result("run-1", [make_suburb("A", rank=1)])
        save_run_metadata(run1, base)

        try:
            compare_runs(["run-1", "run-no-meta"], base)
            assert False, "Should have raised ComparisonError"
        except ComparisonError as e:
            assert "metadata" in str(e).lower()


# ─── Comparison Renderer Tests ───────────────────────────────────────────────

def test_comparison_report_generation():
    """generate_comparison_report creates an HTML file."""
    from reporting.comparison_renderer import generate_comparison_report

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        comparison = ComparisonResult(
            run_summaries=[
                RunSummary(run_id="r1", timestamp="2024-01-01", dwelling_type="house",
                           max_price=700000, regions=["QLD"], suburb_count=3, provider="perplexity"),
                RunSummary(run_id="r2", timestamp="2024-01-02", dwelling_type="house",
                           max_price=700000, regions=["QLD"], suburb_count=3, provider="anthropic"),
            ],
            overlapping_suburbs=[
                SuburbDelta(
                    suburb_name="Springfield",
                    state="QLD",
                    run_metrics=[
                        SuburbRunMetrics(run_id="r1", median_price=500000, composite_score=70, projected_5yr=15.0),
                        SuburbRunMetrics(run_id="r2", median_price=520000, composite_score=72, projected_5yr=16.0),
                    ],
                ),
            ],
            unique_per_run={"r1": ["UniqueA, QLD"], "r2": []},
        )

        output_dir = base / "compare_test"
        report_path = generate_comparison_report(comparison, output_dir)

        assert report_path.exists()
        assert report_path.name == "index.html"
        content = report_path.read_text()
        assert "Springfield" in content
        assert "Run Comparison" in content
        assert "UniqueA" in content


def test_comparison_report_empty_overlap():
    """Comparison report with no overlapping suburbs."""
    from reporting.comparison_renderer import generate_comparison_report

    with tempfile.TemporaryDirectory() as tmpdir:
        comparison = ComparisonResult(
            run_summaries=[
                RunSummary(run_id="r1", timestamp="2024-01-01", dwelling_type="house",
                           max_price=700000, regions=["QLD"], suburb_count=1, provider="perplexity"),
                RunSummary(run_id="r2", timestamp="2024-01-02", dwelling_type="house",
                           max_price=700000, regions=["QLD"], suburb_count=1, provider="perplexity"),
            ],
            overlapping_suburbs=[],
            unique_per_run={"r1": ["A, QLD"], "r2": ["B, QLD"]},
        )

        output_dir = Path(tmpdir) / "compare_empty"
        report_path = generate_comparison_report(comparison, output_dir)
        assert report_path.exists()
        content = report_path.read_text()
        assert "0" in content  # "Overlapping Suburbs" count


# ─── Run All Tests ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("COMPARISON UNIT TESTS")
    print("=" * 60)

    tests = [
        # Models
        ("Model: RunSummary creation", test_run_summary_creation),
        ("Model: SuburbRunMetrics", test_suburb_run_metrics),
        ("Model: SuburbDelta price delta", test_suburb_delta_price_delta),
        ("Model: SuburbDelta score delta", test_suburb_delta_score_delta),
        ("Model: SuburbDelta single run", test_suburb_delta_single_run_no_delta),
        ("Model: SuburbDelta zero prices", test_suburb_delta_zero_prices),
        ("Model: ComparisonResult defaults", test_comparison_result_creation),

        # compute_run_summary
        ("Summary: basic", test_compute_run_summary),
        ("Summary: empty suburbs", test_compute_run_summary_empty_suburbs),

        # find_overlapping_suburbs
        ("Overlap: full", test_find_overlap_full),
        ("Overlap: partial", test_find_overlap_partial),
        ("Overlap: none", test_find_overlap_none),
        ("Overlap: case insensitive", test_find_overlap_case_insensitive),
        ("Overlap: different states", test_find_overlap_different_states),
        ("Overlap: three runs", test_find_overlap_three_runs),
        ("Overlap: sorted by score", test_find_overlap_sorted_by_score),
        ("Overlap: empty runs", test_find_overlap_empty_runs),

        # compare_runs (filesystem)
        ("Compare: success", test_compare_runs_success),
        ("Compare: three runs", test_compare_runs_three),
        ("Compare: too few", test_compare_runs_too_few),
        ("Compare: too many", test_compare_runs_too_many),
        ("Compare: missing run", test_compare_runs_missing_run),
        ("Compare: missing metadata", test_compare_runs_missing_metadata),

        # Comparison renderer
        ("Renderer: report generation", test_comparison_report_generation),
        ("Renderer: empty overlap", test_comparison_report_empty_overlap),
    ]

    print(f"\nRunning {len(tests)} tests...\n")

    for name, fn in tests:
        run_test(name, fn)

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    print(f"{'=' * 60}")

    if errors:
        print("\nFailed tests:")
        for name, tb in errors:
            print(f"\n--- {name} ---")
            print(tb)

    sys.exit(0 if failed == 0 else 1)
