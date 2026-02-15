# Codebase Concerns

**Analysis Date:** 2026-02-15

## Tech Debt

**Bare Exception Handling in API Clients:**
- Issue: `src/research/perplexity_client.py` lines 148-174 catch broad exceptions without specific type checking for different API error modes. While there are specific error checks, the logic relies on string matching which is fragile.
- Files: `src/research/perplexity_client.py` (lines 148-174), `src/research/anthropic_client.py` (similar pattern)
- Impact: Error detection depends on error message strings which may change with API versions, causing silent failures or incorrect error classification
- Fix approach: Implement proper exception hierarchy and type-based catching instead of string pattern matching. Define canonical error codes/types from API responses before relying on message content

**JSON Parsing Fallback Chain:**
- Issue: `src/research/perplexity_client.py` lines 192-247 implement a complex fallback chain for JSON extraction (markdown blocks, triple backticks, direct object/array search)
- Files: `src/research/perplexity_client.py` (lines 192-247)
- Impact: If Perplexity API returns malformed JSON, the fallback extraction may parse partially-valid JSON silently, leading to incomplete suburb data being used in analysis
- Fix approach: Add validation layer that checks each extracted JSON against expected schema before caching. Log warnings for each fallback used to track API response quality degradation

**Incomplete Fallback Metrics Generation:**
- Issue: `src/research/suburb_research.py` lines 331-361 create fallback metrics with hardcoded default growth projections when research fails
- Files: `src/research/suburb_research.py` (lines 331-361)
- Impact: Failed suburb research produces generic metrics with 50/50 risk-growth scores that skew final rankings. If many suburbs fail, results become unreliable but still show as "completed"
- Fix approach: Track failure reasons and mark metrics with `data_quality: "fallback"` flag. Exclude or downweight fallback metrics in final ranking. Report fallback suburb count prominently

**Thread Safety in Singleton Cache:**
- Issue: `src/research/cache.py` implements thread-safe cache with locks, but singleton pattern in `get_cache()` (lines 300-312) could have race condition on first initialization
- Files: `src/research/cache.py` (lines 300-312)
- Impact: Multiple threads calling `get_cache()` simultaneously could create multiple cache instances before singleton is fully initialized
- Fix approach: Use double-checked locking or thread lock at module level before singleton initialization

## Known Bugs

**CSV/Excel Export Missing Demographic Data:**
- Symptoms: `src/reporting/excel_exporter.py` does not include household_types, income_distribution, or detailed infrastructure amenities in export
- Files: `src/reporting/excel_exporter.py` (entire file implements limited fields)
- Trigger: Generate Excel export for any completed run
- Workaround: Use HTML reports which contain full demographic data

**PDF Text Wrapping Issue (Recently Fixed):**
- Symptoms: Unicode characters and long text in PDF exports would cause rendering errors or text cutoff
- Files: `src/reporting/pdf_exporter.py` (lines 28-41 sanitization logic)
- Current Mitigation: `_sanitize()` function replaces problematic Unicode characters with ASCII equivalents
- Note: Related fixes in recent commits ("FIX: text wrapping pdf exports", "FIX: pdf generation error in typography")

**Cache Index Corruption Handling:**
- Symptoms: If `cache/cache_index.json` becomes corrupted, entire cache index is lost but no backup exists
- Files: `src/research/cache.py` (lines 63-78 loading logic)
- Trigger: Interrupted write operations during cache updates, or disk corruption
- Current Mitigation: Returns empty dict and logs warning (lines 76-78), but all cached research data becomes orphaned

## Security Considerations

**API Key Exposure in Error Messages:**
- Risk: Error handling in `src/research/perplexity_client.py` and `src/research/anthropic_client.py` could potentially log API keys if they appear in error responses
- Files: `src/research/perplexity_client.py` (lines 170-190), `src/research/anthropic_client.py` (similar pattern)
- Current Mitigation: Error messages are sanitized to only show error type and generic guidance, but full exception object is sometimes printed to console
- Recommendations: Filter API keys from all exception outputs. Implement structured logging that never logs raw API responses

**No Input Validation on Region Filters:**
- Risk: User-supplied region names are directly interpolated into API prompts without validation
- Files: `src/app.py` (line 332), `src/research/suburb_discovery.py` (lines 83-84, 123-124)
- Current Mitigation: Region list is provided via dropdown (web) or autocomplete (CLI), but CLI accepts arbitrary strings
- Recommendations: Implement strict whitelist validation for region names against predefined list before passing to API

**Cache Directory Path Traversal:**
- Risk: While unlikely, cache key generation could theoretically be exploited to write outside cache directory
- Files: `src/research/cache.py` (lines 169-171 where filename is constructed)
- Current Mitigation: Cache directory is under project root and filename uses hash-based key + type prefix
- Recommendations: Add assertions that cache file path is within cache directory before write operations

## Performance Bottlenecks

**Parallel Research Workers Exceeded by Timeout:**
- Problem: `src/research/suburb_research.py` sets `RESEARCH_TIMEOUT = 240s` but parallel execution with 3 workers on slow connections can exceed total job timeout
- Files: `src/research/suburb_research.py` (lines 433-562), `src/config/settings.py` (line 59)
- Cause: Each worker is given 4 minutes independently; with 3 workers and no coordination, worst case is 12 minutes total for sequential failures
- Improvement path: Implement shared timeout pool across workers. Set per-suburb timeout to (total_timeout / num_workers) * safety_factor

**Discovery Phase Cartesian Product:**
- Problem: `src/app.py` line 97 multiplies user suburbs by 3 for research phase, but discovery phase already returns `num_suburbs * 5` candidates
- Files: `src/app.py` (line 81, 97)
- Cause: Requesting 5*N candidates, then researching 3*N of them is wasteful; could parallelize discovery to fetch more regions simultaneously
- Improvement path: Batch region discovery in parallel instead of sequential, implement ranking early to select top candidates for detailed research

**DataFrame Creation Overhead in Excel Export:**
- Problem: `src/reporting/excel_exporter.py` creates entire DataFrame in memory before writing
- Files: `src/reporting/excel_exporter.py` (entire file)
- Cause: For 25+ suburbs with historical data, DataFrame can be large
- Improvement path: Stream write to Excel file using `openpyxl` directly instead of DataFrame intermediate

## Fragile Areas

**Perplexity API Response Parsing:**
- Files: `src/research/suburb_discovery.py`, `src/research/suburb_research.py`
- Why fragile: API responses are parsed as JSON after free-form text generation. No schema validation. If API introduces new fields or changes nesting, parsing fails silently with fallback metrics
- Safe modification: Implement Pydantic model validation for all API responses. Validate against schema before using data. Log schema mismatches
- Test coverage: `tests/test_models.py` covers data models but `tests/test_perplexity.py` is minimal; no tests for malformed response handling

**Ranking and Scoring Logic:**
- Files: `src/research/ranking.py` (entire file - 182 lines)
- Why fragile: Composite score calculation uses hardcoded weights (lines not shown but in code). No documentation of weighting strategy. If growth_score or risk_score distribution changes, ranking order changes unpredictably
- Safe modification: Extract scoring weights to configuration constants. Document weighting rationale. Add tests with known score distributions
- Test coverage: `tests/test_research_ranking.py` exists but coverage unclear

**Cache Invalidation Logic:**
- Files: `src/research/cache.py` (lines 191-207, 209-237)
- Why fragile: Manual invalidation requires exact key match. If calling code has slightly different key construction, cache isn't properly invalidated, leading to stale data being returned
- Safe modification: Add cache warmth/staleness metrics. Implement automatic re-validation on cache hit with optional background refresh
- Test coverage: `tests/test_cache.py` exists and includes resilience tests

**Concurrent Access to Completed Runs Dict:**
- Files: `src/ui/web/server.py` (lines 61-63 global dicts, 81-169 background task)
- Why fragile: `active_runs` and `completed_runs` are global dicts modified from background threads without explicit locking
- Safe modification: Use `threading.Lock()` to protect dict access. Consider using `concurrent.futures` result tracking instead
- Test coverage: No explicit tests for concurrent web requests

## Scaling Limits

**In-Memory Run Tracking in Web Server:**
- Current capacity: Server tracks runs in `active_runs` and `completed_runs` dicts (line 62-63 in `server.py`)
- Limit: No cleanup of old completed runs. After 1000+ runs, memory usage grows unbounded
- Scaling path: Persist run metadata to SQLite or file system. Implement cleanup of runs older than N days. Only keep recent runs in memory

**Parallel Worker Count Hardcoded:**
- Current capacity: `DISCOVERY_MAX_WORKERS = 4`, `RESEARCH_MAX_WORKERS = 3` (settings.py line 56-57)
- Limit: Not tuned per machine CPU count or memory. On single-core or memory-limited systems, this causes thread overhead
- Scaling path: Implement adaptive worker count based on `os.cpu_count()` and available memory. Add CLI flag `--workers` to override

**Cache Directory Size Unbounded:**
- Current capacity: Cache TTL is 24h for discovery, 7d for research, but no size limit
- Limit: Cache directory can grow to GBs if many runs are executed. No automatic cleanup
- Scaling path: Implement LRU eviction when cache size exceeds threshold (e.g., 500MB). Add `--cache-limit` configuration

## Dependencies at Risk

**Perplexity SDK Stability:**
- Risk: `perplexityai>=0.1.0` in `requirements.txt` is pinned to v0.1.0+ but `perplexity_client.py` includes SDK import/exception handling suggesting early-stage API (lines 57-67)
- Impact: If Perplexity SDK changes significantly, response parsing may break
- Migration plan: Switch to OpenAI API client for consistency if Perplexity proves unstable. Implement adapter pattern to abstract API client

**Matplotlib Non-Interactive Backend:**
- Risk: `src/reporting/charts.py` line 5 sets `matplotlib.use('Agg')` globally, which affects all subsequent matplotlib usage. If other code uses interactive matplotlib, it will fail
- Impact: Cannot use any interactive plotting features anywhere in application
- Migration plan: Use `matplotlib.backends.backend_agg.FigureCanvasAgg` directly instead of setting global backend

**Pydantic V2 Migration:**
- Risk: `pydantic>=2.0.0` in requirements but models use V2 APIs (validated, model_dump). If downgrade to V1, breaks immediately
- Impact: Cannot run on systems with only Pydantic V1 installed
- Migration plan: Add explicit version constraint `pydantic>=2.0.0,<3.0.0`. If V1 support needed, use compatibility layer

## Missing Critical Features

**No Run Recovery After Crash:**
- Problem: If application crashes mid-research, partially completed data is lost. No way to resume from checkpoint
- Blocks: Users cannot resume 2-hour research runs if network interrupts at hour 1.5
- Workaround: Cache system preserves discovery and per-suburb research, so can re-run discovery phase and research only missing suburbs manually

**No Batch Mode with External Input File:**
- Problem: `src/app.py` only accepts command-line args or web form. No ability to load multiple runs from CSV/JSON file
- Blocks: Users cannot schedule 100 different property searches in batch
- Recommended approach: Add `--input-file` argument that reads run specifications from JSON file, execute sequentially

**No Real-Time Progress Streaming to Web UI:**
- Problem: Web server collects progress messages in dict (server.py line 96) but HTML doesn't poll for updates
- Blocks: User cannot see live progress while run is executing, only final result
- Recommended approach: Add WebSocket endpoint for real-time progress streaming, or implement server-sent events (SSE)

## Test Coverage Gaps

**Untested Area: PDF Export with Missing Chart Images:**
- What's not tested: PDF generation when chart files don't exist
- Files: `src/reporting/pdf_exporter.py` (lines 276-300 attempt to handle missing files but untested)
- Risk: PDF export could fail silently or produce incomplete PDFs without clear error message
- Priority: Medium - occurs only if chart generation fails

**Untested Area: Concurrent Web Requests During Active Run:**
- What's not tested: Multiple simultaneous requests to start runs or query status
- Files: `src/ui/web/server.py` (entire file)
- Risk: Race conditions in `active_runs` dict access could cause inconsistent state
- Priority: High - web UI is production interface

**Untested Area: API Error Recovery in Batch Research:**
- What's not tested: Behavior when some suburbs fail API research but others succeed (partial batch)
- Files: `src/research/suburb_research.py` (lines 433-562)
- Risk: Fallback metrics are created but not clearly marked as unreliable in final reports
- Priority: High - common scenario with large suburb counts

**Untested Area: Cache Corruption and Index Corruption:**
- What's not tested: Behavior when cache files are corrupted or index is deleted while system is running
- Files: `src/research/cache.py` (lines 63-78, 140-154)
- Risk: Application could crash or get into inconsistent state if cache directory becomes corrupted mid-operation
- Priority: Medium - edge case but no graceful recovery

