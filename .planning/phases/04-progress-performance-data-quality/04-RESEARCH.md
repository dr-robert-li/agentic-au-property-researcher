# Phase 4 Research: Progress, Performance & Data Quality

**Research Question**: What do I need to know to PLAN Phase 4 well?

**Date**: 2026-02-16

---

## Executive Summary

Phase 4 requires implementing three distinct but complementary features:
1. **Live Progress Streaming**: Replace polling-based progress with Server-Sent Events (SSE)
2. **Adaptive Worker Scaling**: Detect container CPU limits and scale workers appropriately
3. **Data Quality Tracking**: Track data confidence, adjust rankings, and improve Excel exports

All three features have existing foundations in the codebase but require targeted enhancements.

---

## 1. Server-Sent Events (SSE) for Live Progress

### Current State Analysis

**Existing Infrastructure** (from `src/ui/web/server.py`):
- ✅ Thread-safe `progress_queues: dict[str, queue.Queue]` (line 109)
- ✅ Progress callback in `run_pipeline_background()` (lines 144-152)
- ✅ `/api/progress/{run_id}` GET endpoint (lines 549-568) that drains queue
- ✅ Browser polling in `run_status.html` (lines 250-298) - polls every 3 seconds

**What Needs to Change**:
- Convert `/api/progress/{run_id}` from polling JSON to SSE streaming
- Update browser client to use `EventSource` API instead of `fetch()` polling
- Add SSE connection lifecycle management (cleanup on disconnect)
- Add percentage calculation to progress messages

### SSE Implementation Pattern (FastAPI)

**Recommended Approach**: Use `sse-starlette` library for production-ready SSE

**Key Resources**:
- [sse-starlette PyPI](https://pypi.org/project/sse-starlette/) - Official FastAPI SSE extension
- [FastAPI SSE with Starlette](https://mahdijafaridev.medium.com/implementing-server-sent-events-sse-with-fastapi-real-time-updates-made-simple-6492f8bfc154) - Implementation guide
- [Server-Sent Events with Python FastAPI](https://medium.com/@nandagopal05/server-sent-events-with-python-fastapi-f1960e0c8e4b) - Real-time updates pattern

**Installation**:
```bash
pip install sse-starlette
```

**Backend Pattern**:
```python
from sse_starlette.sse import EventSourceResponse
from fastapi import Request
import asyncio

@app.get("/api/progress/{run_id}/stream")
async def stream_progress(run_id: str, request: Request):
    """Stream progress updates via SSE."""
    async def event_generator():
        progress_queue = progress_queues.get(run_id)
        if not progress_queue:
            yield {
                "event": "error",
                "data": json.dumps({"error": "Run not found"})
            }
            return

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                # Non-blocking queue check
                try:
                    msg = progress_queue.get_nowait()
                    if msg is None:  # Completion signal
                        yield {
                            "event": "complete",
                            "data": json.dumps({"status": "completed"})
                        }
                        break

                    yield {
                        "event": "progress",
                        "data": json.dumps({
                            "message": msg["message"],
                            "timestamp": msg["timestamp"],
                            "percent": msg.get("percent", 0)
                        })
                    }
                except queue.Empty:
                    # Send keepalive comment every 15 seconds
                    yield {"comment": "keepalive"}
                    await asyncio.sleep(0.5)  # Check queue twice per second

        finally:
            # Cleanup connection (remove from tracking dict if needed)
            pass

    return EventSourceResponse(event_generator())
```

**Frontend Pattern** (Browser EventSource):
```javascript
// Replace the existing fetch() polling with EventSource
const eventSource = new EventSource(`/api/progress/${runId}/stream`);

eventSource.addEventListener('progress', function(e) {
    const data = JSON.parse(e.data);
    updateProgressUI(data.message, data.percent, data.timestamp);
});

eventSource.addEventListener('complete', function(e) {
    eventSource.close();
    window.location.reload();  // Show final status
});

eventSource.onerror = function(err) {
    console.error('EventSource error:', err);
    eventSource.close();

    // Auto-reconnect after 5 seconds
    setTimeout(() => {
        window.location.reload();
    }, 5000);
};

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    eventSource.close();
});
```

**Browser Compatibility**: `EventSource` is supported in all modern browsers (Chrome, Firefox, Safari, Edge) since 2015. Auto-reconnection is built-in.

### Progress Percentage Calculation

**Challenge**: Current progress messages are text-only; need to add percentage for progress bars.

**Solution**: Add progress tracking to `run_research_pipeline()` in `src/app.py`:

```python
def run_research_pipeline(user_input: UserInput, progress_callback: Optional[Callable[[str, float], None]] = None):
    """
    Execute the complete research pipeline.

    Args:
        progress_callback: Optional callback(message: str, percent: float)
    """
    def _progress(message: str, percent: float = 0.0):
        """Report progress with percentage."""
        print(f"[{percent:.1f}%] {message}")
        if progress_callback:
            progress_callback(message, percent)

    # Discovery: 0-20%
    _progress("Starting suburb discovery...", 0)
    candidates = parallel_discover_suburbs(...)
    _progress(f"Found {len(candidates)} candidates", 20)

    # Research: 20-80% (divided by number of suburbs)
    research_count = min(len(candidates), user_input.num_suburbs * 3)
    for i, batch in enumerate(batches):
        percent = 20 + (60 * (i + 1) / len(batches))
        _progress(f"Researching batch {i+1}/{len(batches)}", percent)
        ...

    # Ranking: 80-85%
    _progress("Ranking suburbs...", 80)
    reports = rank_suburbs(...)
    _progress(f"Selected top {len(reports)} suburbs", 85)

    # Report generation: 85-100%
    _progress("Generating reports...", 90)
    generate_all_reports(...)
    _progress("Complete!", 100)
```

**Update Callback Signature** in `server.py`:
```python
def progress_callback(message: str, percent: float = 0.0):
    """Push progress message with percentage to queue."""
    try:
        progress_queue.put({
            "message": message,
            "percent": percent,
            "timestamp": datetime.now().isoformat()
        }, timeout=1)
    except queue.Full:
        pass
```

### Connection Cleanup Strategy

**Memory Leak Prevention**:
```python
# Track SSE connections per run
sse_connections: dict[str, set] = defaultdict(set)
sse_connections_lock = threading.Lock()

@app.get("/api/progress/{run_id}/stream")
async def stream_progress(run_id: str, request: Request):
    connection_id = id(request)

    # Register connection
    with sse_connections_lock:
        sse_connections[run_id].add(connection_id)

    try:
        async def event_generator():
            # ... streaming logic ...

        return EventSourceResponse(event_generator())
    finally:
        # Unregister connection
        with sse_connections_lock:
            sse_connections[run_id].discard(connection_id)
            if not sse_connections[run_id]:
                del sse_connections[run_id]
```

---

## 2. Adaptive Worker Scaling & Container CPU Detection

### Current State Analysis

**Fixed Worker Counts** (from `src/config/settings.py` lines 134-137):
```python
DISCOVERY_MAX_WORKERS = int(os.getenv("DISCOVERY_MAX_WORKERS", "4"))
RESEARCH_MAX_WORKERS = int(os.getenv("RESEARCH_MAX_WORKERS", "3"))
```

**Problem**: These values are:
- Hardcoded defaults that don't adapt to hardware
- Using `os.cpu_count()` in Docker reports host CPU count (e.g., 64), not container limit (e.g., 2)

### Container CPU Detection Strategy

**cgroup v1 and v2 Detection** (Linux containers):

```python
# src/config/cpu_detection.py

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def detect_cpu_limit() -> int:
    """
    Detect CPU limit in container or host environment.

    Returns:
        Number of CPUs available (minimum 1)
    """
    # Try cgroup v2 first (newer Docker versions)
    cpu_max = _read_cgroup_v2_cpu()
    if cpu_max is not None:
        return cpu_max

    # Fallback to cgroup v1
    cpu_quota = _read_cgroup_v1_cpu()
    if cpu_quota is not None:
        return cpu_quota

    # No cgroup limits, use os.cpu_count()
    return os.cpu_count() or 1


def _read_cgroup_v2_cpu() -> Optional[int]:
    """Read CPU limit from cgroup v2."""
    try:
        # Path: /sys/fs/cgroup/cpu.max
        # Format: "$MAX $PERIOD" or "max $PERIOD" (unlimited)
        with open('/sys/fs/cgroup/cpu.max', 'r') as f:
            line = f.read().strip()
            parts = line.split()
            if parts[0] == 'max':
                return None  # No limit

            quota = int(parts[0])
            period = int(parts[1])
            cpus = quota / period
            return max(1, int(cpus))
    except (FileNotFoundError, ValueError, IndexError):
        return None


def _read_cgroup_v1_cpu() -> Optional[int]:
    """Read CPU limit from cgroup v1."""
    try:
        # Paths:
        # - /sys/fs/cgroup/cpu/cpu.cfs_quota_us (CPU quota in microseconds)
        # - /sys/fs/cgroup/cpu/cpu.cfs_period_us (CPU period in microseconds)
        quota_path = '/sys/fs/cgroup/cpu/cpu.cfs_quota_us'
        period_path = '/sys/fs/cgroup/cpu/cpu.cfs_period_us'

        with open(quota_path, 'r') as f:
            quota = int(f.read().strip())

        if quota == -1:
            return None  # No limit

        with open(period_path, 'r') as f:
            period = int(f.read().strip())

        cpus = quota / period
        return max(1, int(cpus))
    except (FileNotFoundError, ValueError):
        return None
```

**References**:
- [Docker Resource Constraints Docs](https://docs.docker.com/engine/containers/resource_constraints/) - Official Docker CPU limit documentation
- [Python Issue 36054](https://bugs.python.org/issue36054) - os.cpu_count() should read cgroup limits
- [How to Debug Docker Container Resource Limits](https://oneuptime.com/blog/post/2026-01-25-debug-docker-container-resource-limits/view) - 2026 guide to cgroup debugging

### Adaptive Worker Count Formula

**Best Practices** from research:

**General Formula**: `workers = (2 × CPU cores) + 1` for web applications (Gunicorn pattern)

**For I/O-Bound Tasks** (our case - API calls):
- Can safely use 2-4x CPU count without performance penalty
- ThreadPoolExecutor is optimal for I/O-bound work

**Memory-Aware Adjustment**:
```python
# src/config/worker_scaling.py

import psutil
from typing import Tuple

def calculate_worker_counts(override_discovery: Optional[int] = None,
                           override_research: Optional[int] = None) -> Tuple[int, int]:
    """
    Calculate optimal worker counts based on CPU and memory.

    Args:
        override_discovery: Environment variable override
        override_research: Environment variable override

    Returns:
        (discovery_workers, research_workers)
    """
    # Detect CPU limit (container-aware)
    cpu_count = detect_cpu_limit()

    # Get available memory in GB
    memory_info = psutil.virtual_memory()
    available_gb = memory_info.available / (1024 ** 3)

    # Base calculation for I/O-bound work (API calls)
    # Discovery: lighter work, more parallelism (3x CPUs)
    base_discovery = min(cpu_count * 3, 8)  # Cap at 8

    # Research: heavier work, moderate parallelism (2x CPUs)
    base_research = min(cpu_count * 2, 6)  # Cap at 6

    # Memory-based adjustment (assume 500MB per worker)
    max_workers_by_memory = int((available_gb - 2) / 0.5)  # Reserve 2GB for system

    discovery_workers = min(base_discovery, max_workers_by_memory)
    research_workers = min(base_research, max_workers_by_memory)

    # Apply environment variable overrides
    if override_discovery is not None:
        discovery_workers = override_discovery
    if override_research is not None:
        research_workers = override_research

    # Ensure minimum of 1
    discovery_workers = max(1, discovery_workers)
    research_workers = max(1, research_workers)

    logger.info(f"Worker scaling: CPU={cpu_count}, Memory={available_gb:.1f}GB")
    logger.info(f"Discovery workers: {discovery_workers}, Research workers: {research_workers}")

    return discovery_workers, research_workers
```

**Update `settings.py`**:
```python
from config.worker_scaling import calculate_worker_counts

# Calculate adaptive worker counts
DISCOVERY_MAX_WORKERS, RESEARCH_MAX_WORKERS = calculate_worker_counts(
    override_discovery=int(os.getenv("DISCOVERY_MAX_WORKERS")) if os.getenv("DISCOVERY_MAX_WORKERS") else None,
    override_research=int(os.getenv("RESEARCH_MAX_WORKERS")) if os.getenv("RESEARCH_MAX_WORKERS") else None
)
```

**New Dependencies**:
```txt
psutil>=6.0.0  # For memory detection
```

**References**:
- [How Many Workers Do I Need for My Python Web Application?](https://medium.com/delivus/how-many-workers-do-i-need-for-my-python-web-application-bd5e2e8dbdf7) - (2 × CPU) + 1 formula
- [Python Multiprocessing Pool Number of Workers](https://superfastpython.com/multiprocessing-pool-num-workers/) - I/O-bound vs CPU-bound guidance
- [ThreadPoolExecutor Number of Threads](https://superfastpython.com/threadpoolexecutor-number-of-threads/) - For I/O work, can safely exceed cpu_count()

### Discovery Pipeline Optimization

**Current Issue** (from phase description):
> "Discovery-to-research pipeline is optimized to reduce wasteful candidate multiplication"

**Analysis**: From `src/app.py` line 110:
```python
candidates = parallel_discover_suburbs(
    user_input,
    max_results=user_input.num_suburbs * 5,  # ← Multiplier here
    progress_callback=progress_callback,
)
```

And line 136:
```python
research_count = min(len(candidates), user_input.num_suburbs * 3)  # ← Another multiplier
```

**Problem**: If user requests 10 suburbs:
- Discovery fetches 50 candidates (10 × 5)
- Research processes 30 candidates (10 × 3)
- Only 10 are used in final report
- Wasted API calls: 40 suburbs researched but discarded

**Solution**: Reduce multipliers or make them configurable:
```python
# In settings.py
DISCOVERY_MULTIPLIER = float(os.getenv("DISCOVERY_MULTIPLIER", "2.0"))  # Down from 5
RESEARCH_MULTIPLIER = float(os.getenv("RESEARCH_MULTIPLIER", "1.5"))   # Down from 3

# In app.py
max_results = int(user_input.num_suburbs * settings.DISCOVERY_MULTIPLIER)
research_count = min(len(candidates), int(user_input.num_suburbs * settings.RESEARCH_MULTIPLIER))
```

**Rationale**: With improved ranking (from data quality adjustments below), we need less over-sampling.

---

## 3. Data Quality Tracking & Ranking Adjustments

### Current State Analysis

**Existing Data Quality Infrastructure**:
- ✅ `SuburbCandidate` has `data_quality` field (src/research/suburb_discovery.py line 55)
- ✅ `ValidatedSuburbCandidate` validates quality levels (src/research/validation.py lines 77-85)
- ✅ Discovery responses include `data_quality` in JSON schema (line 121)
- ❌ `SuburbMetrics` model **does NOT have** `data_quality` field
- ❌ Ranking logic **does NOT consider** data quality

**Gap**: Data quality is captured during discovery but lost during research. No impact on final rankings.

### Adding data_quality to SuburbMetrics

**Update Model** (src/models/suburb_metrics.py):
```python
class SuburbMetrics(BaseModel):
    """Complete metrics for a suburb."""

    identification: SuburbIdentification
    market_current: MarketMetricsCurrent
    market_history: MarketMetricsHistory = Field(default_factory=MarketMetricsHistory)
    physical_config: PhysicalConfig = Field(default_factory=PhysicalConfig)
    demographics: Demographics = Field(default_factory=Demographics)
    infrastructure: Infrastructure = Field(default_factory=Infrastructure)
    growth_projections: GrowthProjections = Field(default_factory=GrowthProjections)

    # NEW: Data quality tracking
    data_quality: str = Field(
        default="medium",
        description="Overall data quality: high (official sources), medium (mixed), low (estimates), fallback (calculated)"
    )
    data_quality_details: dict = Field(
        default_factory=dict,
        description="Per-field quality indicators, e.g. {'median_price': 'high', 'demographics': 'fallback'}"
    )
```

**Quality Levels**:
- `"high"`: Official government/real estate data (e.g., ABS, CoreLogic, Domain, REA)
- `"medium"`: Mixed sources, some third-party estimates
- `"low"`: Mostly estimates or old data
- `"fallback"`: Calculated/interpolated when real data unavailable

### Research Response Schema Update

**Update Perplexity/Anthropic Prompts** (src/research/suburb_research.py):
```python
prompt = f"""
...
Return a single JSON object with this structure ONLY:

{{
  "identification": {{ ... }},
  "market_current": {{ ... }},
  ...
  "data_quality": "high|medium|low|fallback",
  "data_quality_details": {{
    "median_price": "high",
    "demographics": "medium",
    "infrastructure": "low",
    "crime_stats": "fallback"
  }},
  "growth_projections": {{ ... }}
}}

Set data_quality based on source reliability:
- "high": Official sources (ABS, CoreLogic, Domain, REA Group, government)
- "medium": Mixed sources, some third-party data
- "low": Mostly estimates or outdated data
- "fallback": Calculated/interpolated when direct data unavailable
"""
```

### Ranking Weight Adjustment

**Current Ranking** (src/research/ranking.py line 40):
```python
reports.sort(key=lambda r: r.metrics.growth_projections.composite_score, reverse=True)
```

**Problem**: No consideration of data quality. A suburb with "fallback" data gets equal weight to one with "high" quality data.

**Solution**: Add quality penalty to composite score:

```python
# In src/research/ranking.py

QUALITY_WEIGHTS = {
    "high": 1.0,      # No penalty
    "medium": 0.95,   # 5% penalty
    "low": 0.85,      # 15% penalty
    "fallback": 0.70  # 30% penalty
}

def calculate_quality_adjusted_score(metrics: SuburbMetrics) -> float:
    """Calculate composite score with data quality adjustment."""
    base_score = metrics.growth_projections.composite_score
    quality_weight = QUALITY_WEIGHTS.get(metrics.data_quality, 0.95)
    return base_score * quality_weight

def rank_suburbs(
    metrics_list: list[SuburbMetrics],
    ranking_method: Literal["growth_score", "composite_score", "5yr_growth", "quality_adjusted"] = "quality_adjusted",
    top_n: Optional[int] = None
) -> list[SuburbReport]:
    """Rank suburbs with optional quality adjustment."""
    if not metrics_list:
        return []

    reports = [SuburbReport(metrics=m) for m in metrics_list]

    if ranking_method == "quality_adjusted":
        reports.sort(key=lambda r: calculate_quality_adjusted_score(r.metrics), reverse=True)
    elif ranking_method == "growth_score":
        reports.sort(key=lambda r: r.metrics.growth_projections.growth_score, reverse=True)
    # ... existing logic
```

**Extract Weights to Configuration** (src/config/settings.py):
```python
# Ranking configuration
RANKING_QUALITY_WEIGHTS = {
    "high": float(os.getenv("QUALITY_WEIGHT_HIGH", "1.0")),
    "medium": float(os.getenv("QUALITY_WEIGHT_MEDIUM", "0.95")),
    "low": float(os.getenv("QUALITY_WEIGHT_LOW", "0.85")),
    "fallback": float(os.getenv("QUALITY_WEIGHT_FALLBACK", "0.70")),
}
DEFAULT_RANKING_METHOD = os.getenv("DEFAULT_RANKING_METHOD", "quality_adjusted")
```

### HTML Report Warning Display

**Update Templates** to show data quality warnings:

```html
<!-- In suburb_report.html -->
{% if suburb.metrics.data_quality in ['low', 'fallback'] %}
<div class="data-quality-warning" style="background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 6px; margin: 20px 0;">
    <h3 style="color: #856404; margin-top: 0;">⚠️ Data Quality Notice</h3>
    <p>
        This report contains {{ suburb.metrics.data_quality }} quality data.
        {% if suburb.metrics.data_quality == 'fallback' %}
        Some metrics are calculated estimates due to limited official data availability.
        {% else %}
        Some metrics are based on estimates or older data sources.
        {% endif %}
    </p>

    {% if suburb.metrics.data_quality_details %}
    <details style="margin-top: 10px;">
        <summary style="cursor: pointer; font-weight: 600;">View field-level quality details</summary>
        <ul style="margin-top: 10px;">
            {% for field, quality in suburb.metrics.data_quality_details.items() %}
            {% if quality in ['low', 'fallback'] %}
            <li><strong>{{ field }}</strong>: {{ quality }}</li>
            {% endif %}
            {% endfor %}
        </ul>
    </details>
    {% endif %}
</div>
{% endif %}
```

**Ranking Summary Update**:
```html
<!-- In index.html ranking table -->
<td>
    {{ suburb.metrics.get_display_name() }}
    {% if suburb.metrics.data_quality == 'fallback' %}
    <span title="Fallback data quality" style="color: #dc3545; margin-left: 5px;">⚠️</span>
    {% elif suburb.metrics.data_quality == 'low' %}
    <span title="Low data quality" style="color: #ffc107; margin-left: 5px;">⚠</span>
    {% endif %}
</td>
```

### Excel Export Enhancement

**Current Excel Sheets** (src/reporting/excel_exporter.py):
- ✅ Demographics sheet exists (lines 261-281) with Household Types and Income Distribution
- ✅ Infrastructure sheet exists (lines 284-313) with transport, schools, crime, shopping
- ❌ Data is rendered as semicolon-separated strings (not ideal for analysis)

**Improvement 1: Add Data Quality Column**

```python
def _create_overview_sheet(ws, run_result: RunResult):
    """Create overview sheet with run metadata and rankings."""
    headers = ['Rank', 'Suburb', 'State', 'LGA', 'Region', 'Median Price',
               '5yr Growth %', 'Growth Score', 'Risk Score', 'Composite Score',
               'Data Quality']  # ← NEW COLUMN

    for i, report in enumerate(run_result.get_top_suburbs()):
        # ... existing cells ...
        ws.cell(row=row, column=11, value=report.metrics.data_quality.upper())
```

**Improvement 2: Better Demographics Formatting**

```python
def _create_demographics_sheet(ws, run_result: RunResult):
    """Create demographics sheet with expanded columns."""
    # Instead of semicolon-separated, create individual columns per household type
    headers = ['Suburb', 'State', 'Median Age', 'Population Trend',
               'Families with Children %', 'Couples %', 'Single Person %', 'Group Households %',
               'Low Income %', 'Medium Income %', 'High Income %']

    for i, report in enumerate(run_result.get_top_suburbs()):
        row = 2 + i
        m = report.metrics
        d = m.demographics

        ws.cell(row=row, column=1, value=m.identification.name)
        ws.cell(row=row, column=2, value=m.identification.state)
        ws.cell(row=row, column=3, value=d.median_age)
        ws.cell(row=row, column=4, value=_safe_str(d.population_trend))

        # Expand household_types dict into columns
        ht = d.household_types or {}
        ws.cell(row=row, column=5, value=ht.get('families_with_children', 0))
        ws.cell(row=row, column=6, value=ht.get('couples', 0))
        ws.cell(row=row, column=7, value=ht.get('single_person', 0))
        ws.cell(row=row, column=8, value=ht.get('group_households', 0))

        # Expand income_distribution dict into columns
        inc = d.income_distribution or {}
        ws.cell(row=row, column=9, value=inc.get('low', 0))
        ws.cell(row=row, column=10, value=inc.get('medium', 0))
        ws.cell(row=row, column=11, value=inc.get('high', 0))
```

**Improvement 3: Infrastructure Detail Columns**

```python
def _create_infrastructure_sheet(ws, run_result: RunResult):
    """Create infrastructure sheet with list expansion."""
    headers = ['Suburb', 'State',
               'Train Stations', 'Bus Routes', 'Future Transport Projects',
               'Planned Infrastructure', 'Major Events Impact',
               'Schools Count', 'Shopping Centers', 'Crime Rate']

    for i, report in enumerate(run_result.get_top_suburbs()):
        row = 2 + i
        m = report.metrics
        inf = m.infrastructure

        # Parse current_transport list
        current = inf.current_transport or []
        trains = [t for t in current if 'train' in t.lower() or 'station' in t.lower()]
        buses = [t for t in current if 'bus' in t.lower()]

        ws.cell(row=row, column=3, value=len(trains))
        ws.cell(row=row, column=4, value=len(buses))
        ws.cell(row=row, column=5, value=_safe_str(inf.future_transport))
        # ... etc
```

---

## 4. Testing Strategy

### Unit Tests

**SSE Endpoint Tests**:
```python
# tests/test_sse_progress.py

import pytest
from fastapi.testclient import TestClient
from src.ui.web.server import app

def test_sse_stream_not_found():
    """Test SSE endpoint returns error for unknown run_id."""
    client = TestClient(app)
    with client.stream("GET", "/api/progress/invalid-run/stream") as response:
        assert response.status_code == 200
        # Read first event
        line = next(response.iter_lines())
        assert b"error" in line

def test_sse_stream_with_messages():
    """Test SSE endpoint streams progress messages."""
    # Setup: create a run with progress queue
    # ... implementation
```

**CPU Detection Tests**:
```python
# tests/test_cpu_detection.py

import pytest
from src.config.cpu_detection import detect_cpu_limit, _read_cgroup_v2_cpu
from unittest.mock import patch, mock_open

def test_detect_cpu_limit_cgroup_v2():
    """Test CPU detection from cgroup v2 format."""
    mock_data = "200000 100000\n"  # 2 CPUs
    with patch("builtins.open", mock_open(read_data=mock_data)):
        assert _read_cgroup_v2_cpu() == 2

def test_detect_cpu_limit_unlimited():
    """Test detection when no CPU limit is set."""
    mock_data = "max 100000\n"
    with patch("builtins.open", mock_open(read_data=mock_data)):
        assert _read_cgroup_v2_cpu() is None
```

**Data Quality Tests**:
```python
# tests/test_data_quality_ranking.py

import pytest
from src.models.suburb_metrics import SuburbMetrics
from src.research.ranking import rank_suburbs, calculate_quality_adjusted_score

def test_quality_adjusted_ranking():
    """Test that fallback quality data is penalized in rankings."""
    high_quality = SuburbMetrics(
        data_quality="high",
        growth_projections=GrowthProjections(composite_score=80.0),
        # ... required fields
    )

    fallback_quality = SuburbMetrics(
        data_quality="fallback",
        growth_projections=GrowthProjections(composite_score=85.0),  # Higher base score
        # ... required fields
    )

    # With quality adjustment, high_quality should rank higher
    high_adj = calculate_quality_adjusted_score(high_quality)  # 80.0 * 1.0 = 80.0
    fallback_adj = calculate_quality_adjusted_score(fallback_quality)  # 85.0 * 0.7 = 59.5

    assert high_adj > fallback_adj
```

### Integration Tests

**SSE Integration Test**:
```python
# tests/test_sse_integration.py

def test_sse_progress_lifecycle():
    """Test full SSE lifecycle: connect, receive messages, disconnect."""
    # Start a background run
    # Connect to SSE stream
    # Verify progress events arrive
    # Verify completion event
    # Verify connection cleanup
```

**Container CPU Test** (requires Docker):
```bash
# Run in Docker with CPU limit
docker run --cpus=2 -v $(pwd):/app python:3.12 python -c "
from src.config.cpu_detection import detect_cpu_limit
print(f'Detected CPUs: {detect_cpu_limit()}')
assert detect_cpu_limit() == 2
"
```

---

## 5. Dependencies & Installation

**New Requirements**:
```txt
# requirements.txt additions

# SSE support
sse-starlette>=2.0.0

# Memory/CPU detection
psutil>=6.0.0

# (Existing dependencies already support SSE via FastAPI/Starlette)
```

**No Breaking Changes**: All new features are additive.

---

## 6. Migration & Backward Compatibility

### Data Model Changes

**SuburbMetrics Schema Evolution**:
- ✅ Adding `data_quality` and `data_quality_details` fields is **backward compatible** (both have defaults)
- ✅ Old checkpoints/cache entries will load with default `data_quality="medium"`
- ✅ Pydantic v2 validation handles missing fields gracefully

### Configuration Changes

**settings.py Updates**:
- ✅ Adaptive worker scaling is transparent (falls back to existing values if detection fails)
- ✅ New environment variables have sensible defaults
- ✅ Existing `.env` files continue to work

### API Changes

**New Endpoints**:
- `/api/progress/{run_id}/stream` - NEW SSE endpoint (polling endpoint remains for legacy clients)
- Existing `/api/progress/{run_id}` continues to work (deprecated but functional)

**Progress Callback Signature**:
- Change from `callback(message: str)` to `callback(message: str, percent: float = 0.0)`
- Old signature still works (percent is optional, defaults to 0.0)

---

## 7. Performance Considerations

### SSE Performance

**Connection Overhead**:
- Each SSE connection is a long-lived HTTP connection
- FastAPI's async design handles this efficiently
- Memory per connection: ~50KB (negligible)
- Keepalive comments prevent timeout (15s interval)

**Scalability**:
- Current design: 1 connection per active run (low volume)
- If needed, can add connection pooling or Redis pub/sub for multi-instance deployments

### Worker Scaling Performance

**Impact on Run Time**:
- 2 CPUs (container) → 6 discovery workers, 4 research workers (vs. hardcoded 4 and 3)
- 64 CPUs (host) → 8 discovery workers, 6 research workers (capped, vs. potential 64)
- **Prevents resource exhaustion** in high-CPU environments

**Memory Impact**:
- psutil adds ~5MB to runtime memory
- Worker count adjustment prevents OOM in low-memory containers

### Data Quality Performance

**Ranking Impact**:
- Quality adjustment adds 1 dictionary lookup per suburb (negligible)
- No API calls, purely computational
- Performance: O(n) where n = number of suburbs (typically < 30)

---

## 8. Documentation Requirements

### User-Facing Documentation

**README.md Updates**:
```markdown
## Features

### Live Progress Tracking
Research runs now show real-time progress with percentage completion. The browser automatically updates without polling, and you can safely refresh the page to reconnect.

### Adaptive Performance
Worker counts automatically adjust to your hardware:
- Docker containers: Detects CPU limits (e.g., `--cpus=2`)
- Host systems: Scales based on available CPUs and memory
- Override with environment variables if needed

### Data Quality Indicators
Reports now include data quality warnings:
- **High**: Official government/real estate sources
- **Medium**: Mixed sources
- **Low**: Estimates or old data
- **Fallback**: Calculated when direct data unavailable

Suburbs with fallback data are ranked lower to prioritize reliable information.
```

**Environment Variables**:
```markdown
## Configuration

### Worker Scaling
- `DISCOVERY_MAX_WORKERS`: Override adaptive discovery workers (default: auto-detect)
- `RESEARCH_MAX_WORKERS`: Override adaptive research workers (default: auto-detect)
- `DISCOVERY_MULTIPLIER`: Discovery over-sampling factor (default: 2.0)
- `RESEARCH_MULTIPLIER`: Research over-sampling factor (default: 1.5)

### Ranking Weights
- `QUALITY_WEIGHT_HIGH`: Ranking weight for high-quality data (default: 1.0)
- `QUALITY_WEIGHT_MEDIUM`: Ranking weight for medium-quality data (default: 0.95)
- `QUALITY_WEIGHT_LOW`: Ranking weight for low-quality data (default: 0.85)
- `QUALITY_WEIGHT_FALLBACK`: Ranking weight for fallback data (default: 0.70)
- `DEFAULT_RANKING_METHOD`: Ranking method (default: quality_adjusted)
```

### Developer Documentation

**Code Comments**:
```python
# src/ui/web/server.py
"""
SSE Progress Streaming

The /api/progress/{run_id}/stream endpoint uses Server-Sent Events (SSE) to push
real-time progress updates to the browser. This replaces the old polling mechanism.

Connection Lifecycle:
1. Client connects via EventSource API
2. Server streams progress messages from queue.Queue
3. Server sends keepalive comments every 15s to prevent timeout
4. On completion, server sends 'complete' event and closes stream
5. Client auto-reconnects if connection drops (built-in EventSource behavior)

Memory Management:
- Connections tracked in sse_connections dict
- Cleanup in finally block prevents leaks
- Empty queues deleted when all connections close
"""
```

---

## 9. Risk Assessment

### High Risk

**SSE Browser Compatibility**:
- **Risk**: EventSource not supported in very old browsers
- **Mitigation**: All modern browsers (2015+) support it; add graceful fallback to polling for ancient browsers
- **Impact**: Low (target audience uses modern browsers)

**cgroup Detection Failures**:
- **Risk**: cgroup file formats change across Docker versions
- **Mitigation**: Multi-version detection (v1 and v2) with fallback to os.cpu_count()
- **Impact**: Medium (graceful degradation, but may over-allocate workers)

### Medium Risk

**Data Quality Schema Drift**:
- **Risk**: AI providers return inconsistent quality labels
- **Mitigation**: Validation with default fallback to "medium"
- **Impact**: Low (affects ranking precision, not correctness)

**Progress Percentage Accuracy**:
- **Risk**: Research time varies widely; percentage may not reflect actual progress
- **Mitigation**: Use conservative estimates; document as approximate
- **Impact**: Low (cosmetic, doesn't affect results)

### Low Risk

**Excel Format Changes**:
- **Risk**: Expanding demographics/infrastructure columns breaks existing analysis scripts
- **Mitigation**: Version Excel export format; add version sheet
- **Impact**: Very Low (users rarely script against Excel exports)

---

## 10. Open Questions

1. **SSE Keepalive Interval**: 15 seconds or 30 seconds? (Trade-off: connection stability vs. server overhead)
   - **Recommendation**: Start with 15s, can increase if load is high

2. **Quality Weight Tuning**: Are the penalty factors (0.95, 0.85, 0.70) appropriate?
   - **Recommendation**: Start conservative, tune based on real-world results after Phase 4 deployment

3. **Excel Column Expansion**: Should demographics/infrastructure be in separate sheets or expanded in-place?
   - **Recommendation**: In-place expansion for now, consider pivot tables in future

4. **Worker Count Caps**: Current caps are 8 (discovery) and 6 (research). Should these be configurable?
   - **Recommendation**: Make configurable via env vars for power users

---

## 11. Success Metrics

### Progress Streaming (PROG-01 to PROG-04)

**Acceptance Criteria**:
- [ ] Browser shows live progress updates without page refresh
- [ ] Progress includes percentage (0-100%)
- [ ] Reconnecting after tab close resumes showing current state
- [ ] No memory leaks after 10 consecutive runs

**Measurement**:
```python
# Test: Start run, close tab, reopen after 30s
# Expected: Progress stream reconnects and shows current percentage
```

### Adaptive Worker Scaling (PERF-01 to PERF-04)

**Acceptance Criteria**:
- [ ] 2-CPU Docker container uses ≤4 workers (not 64)
- [ ] 64-CPU host uses ≤8 discovery workers (not 64)
- [ ] Environment variable overrides work correctly
- [ ] Pipeline multipliers reduce wasteful research

**Measurement**:
```bash
# Test: docker run --cpus=2 app
docker run --cpus=2 -e DISCOVERY_MAX_WORKERS=auto app
# Check logs for "Worker scaling: CPU=2, Discovery workers: X"
```

### Data Quality Tracking (QUAL-01 to QUAL-04, RPT-01 to RPT-02)

**Acceptance Criteria**:
- [ ] Suburb reports show data quality badge/warning
- [ ] Fallback data is ranked lower than high-quality data
- [ ] Excel export includes data_quality column
- [ ] Excel demographics are in separate columns (not semicolon-separated)

**Measurement**:
```python
# Test: Compare two suburbs with same growth but different quality
# Expected: High-quality suburb ranks higher
```

---

## 12. Implementation Roadmap (Suggested)

### Plan 04-01: SSE Progress Streaming (~4 hours)

**Tasks**:
1. Install `sse-starlette` dependency
2. Create `/api/progress/{run_id}/stream` SSE endpoint
3. Update `progress_callback()` to include percentage
4. Add percentage tracking to `run_research_pipeline()`
5. Replace browser polling with EventSource client
6. Add connection cleanup logic
7. Write unit tests for SSE endpoint
8. Update documentation

**Success**: Live progress bar updates in browser without polling

### Plan 04-02: Adaptive Worker Scaling (~5 hours)

**Tasks**:
1. Install `psutil` dependency
2. Create `src/config/cpu_detection.py` with cgroup detection
3. Create `src/config/worker_scaling.py` with adaptive calculation
4. Update `settings.py` to use adaptive scaling
5. Add env var overrides for discovery/research multipliers
6. Reduce default multipliers from 5/3 to 2/1.5
7. Write unit tests for CPU detection (with mocks)
8. Test in Docker container with `--cpus=2`
9. Update documentation with new env vars

**Success**: 2-CPU container uses 2-4 workers; 64-CPU host uses ≤8 workers

### Plan 04-03: Data Quality Tracking (~6 hours)

**Tasks**:
1. Add `data_quality` and `data_quality_details` to `SuburbMetrics` model
2. Update research prompts to request quality fields
3. Create `QUALITY_WEIGHTS` config in settings
4. Add `calculate_quality_adjusted_score()` to ranking
5. Update `rank_suburbs()` to use quality-adjusted ranking by default
6. Add HTML warning display to `suburb_report.html`
7. Add quality icons to `index.html` ranking table
8. Add `data_quality` column to Excel Overview sheet
9. Expand demographics/infrastructure Excel columns
10. Write unit tests for quality-adjusted ranking
11. Update documentation with quality level definitions

**Success**: Fallback data shows warnings; rankings prioritize high-quality data

---

## 13. Key Takeaways for Planning

### What's Already Built
- Progress queue infrastructure (Phase 2)
- Data quality field in discovery (Phase 1)
- Excel exporter with demographics/infrastructure sheets
- Thread-safe progress callbacks

### What Needs Building
- SSE streaming endpoint and browser client
- Container CPU detection and adaptive scaling
- Data quality propagation from discovery to metrics
- Quality-adjusted ranking algorithm
- HTML/Excel quality warnings

### Critical Dependencies
- `sse-starlette` for production SSE
- `psutil` for memory detection
- FastAPI async support (already present)

### Biggest Risks
- cgroup detection across Docker versions (mitigated by multi-version support)
- Progress percentage accuracy (mitigated by documentation)
- AI quality label consistency (mitigated by validation + defaults)

### Recommended Approach
1. Start with SSE (highest user impact, lowest risk)
2. Add adaptive scaling (medium complexity, high operational value)
3. Finish with data quality (highest complexity, requires careful tuning)

---

## Sources

- [sse-starlette PyPI](https://pypi.org/project/sse-starlette/)
- [FastAPI SSE Implementation Guide](https://mahdijafaridev.medium.com/implementing-server-sent-events-sse-with-fastapi-real-time-updates-made-simple-6492f8bfc154)
- [Server-Sent Events with Python FastAPI](https://medium.com/@nandagopal05/server-sent-events-with-python-fastapi-f1960e0c8e4b)
- [Docker Resource Constraints Documentation](https://docs.docker.com/engine/containers/resource_constraints/)
- [Python Issue 36054: os.cpu_count() should read cgroup limits](https://bugs.python.org/issue36054)
- [How to Debug Docker Container Resource Limits (2026)](https://oneuptime.com/blog/post/2026-01-25-debug-docker-container-resource-limits/view)
- [How Many Workers Do I Need for My Python Web Application?](https://medium.com/delivus/how-many-workers-do-i-need-for-my-python-web-application-bd5e2e8dbdf7)
- [ThreadPoolExecutor Number of Threads](https://superfastpython.com/threadpoolexecutor-number-of-threads/)
- [Python Multiprocessing Pool Number of Workers](https://superfastpython.com/multiprocessing-pool-num-workers/)
