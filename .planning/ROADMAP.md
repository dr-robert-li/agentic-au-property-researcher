# Roadmap: Agentic RE Researcher v2.0

## Overview

This roadmap hardens the existing v1 property research application into a production-ready system. Five phases address security vulnerabilities, replace fragile error handling, fix thread safety issues, improve cache reliability with crash recovery, add real-time progress and performance optimizations, and validate everything with comprehensive tests. Each phase builds on the previous -- foundations first, enhancements second, testing last.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Security & Error Foundations** - Close security gaps and establish exception hierarchy for all downstream error handling
- [ ] **Phase 2: Thread Safety & Response Validation** - Fix concurrency bugs and validate all API responses before caching
- [ ] **Phase 3: Cache Hardening & Crash Recovery** - Make cache corruption-proof and enable interrupted runs to resume
- [ ] **Phase 4: Progress, Performance & Data Quality** - Add real-time feedback, adaptive scaling, and data quality tracking
- [ ] **Phase 5: Comprehensive Testing** - Validate all hardening work with unit, integration, async, and concurrency tests

## Phase Details

### Phase 1: Security & Error Foundations
**Goal**: The application rejects malicious input, never leaks credentials, and classifies errors by type instead of string matching
**Depends on**: Nothing (first phase)
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, ERR-01, ERR-02, ERR-03, ERR-04
**Success Criteria** (what must be TRUE):
  1. API keys never appear in log output, error messages, or stack traces -- even when exceptions propagate through multiple layers
  2. Submitting a region name not in the predefined whitelist is rejected with a clear error before any API call is made
  3. Run IDs and cache paths containing path traversal characters (../, special chars) are rejected at input boundaries
  4. A misconfigured or missing API key produces a clear startup error with instructions, not a cryptic runtime failure
  5. Catching a rate limit error, a timeout, and an auth error each routes to different handling logic (retry vs fail vs stop) without string matching
**Plans:** 2 plans

Plans:
- [ ] 01-01-PLAN.md -- Security hardening: global log sanitization, input validation (regions/run_id/cache paths), startup API key validation, FastAPI error handler sanitization
- [ ] 01-02-PLAN.md -- Exception hierarchy: typed ApplicationError hierarchy with structured metadata, SDK exception wrapping, handler migration from string matching to isinstance

### Phase 2: Thread Safety & Response Validation
**Goal**: Concurrent research runs do not corrupt shared state, and malformed API responses are caught before they enter the cache
**Depends on**: Phase 1 (exception hierarchy needed for validation errors and thread-safe error handling)
**Requirements**: THR-01, THR-02, THR-03, VAL-01, VAL-02, VAL-03, VAL-04
**Success Criteria** (what must be TRUE):
  1. Starting two research runs simultaneously from the web UI never produces corrupted run state or cache entries
  2. Cache initialization from multiple threads always returns the same singleton instance with no duplicate initialization
  3. A Perplexity response with a string price like "450000" instead of integer is coerced and accepted, not rejected
  4. A response missing required fields (e.g., no median_price) produces a structured warning with field-level detail, and the suburb is flagged rather than silently dropped
**Plans**: TBD

Plans:
- [ ] 02-01: Thread-safe singleton cache and web server state protection
- [ ] 02-02: API response validation schemas with flexible coercion

### Phase 3: Cache Hardening & Crash Recovery
**Goal**: Cache files survive crashes without corruption, and interrupted research runs can be resumed from the last completed suburb
**Depends on**: Phase 1 (exception hierarchy for CacheError), Phase 2 (thread safety for concurrent cache access)
**Requirements**: CACHE-01, CACHE-02, CACHE-03, CACHE-04, CACHE-05, REC-01, REC-02, REC-03, REC-04, REC-05
**Success Criteria** (what must be TRUE):
  1. Killing the process mid-write (kill -9) never leaves a corrupted cache file -- the previous valid version remains intact
  2. Running the app after deleting the cache index recovers from backup and reports what was restored
  3. Cache directory stays within the configured size limit by automatically evicting least-recently-used entries
  4. Running with --resume after a crash skips already-completed suburbs and continues from the last checkpoint
  5. If the latest checkpoint is corrupted, the system falls back to the previous checkpoint automatically
**Plans**: TBD

Plans:
- [ ] 03-01: Atomic cache writes, backup/restore, orphan cleanup, and LRU eviction
- [ ] 03-02: Checkpoint system with resume capability

### Phase 4: Progress, Performance & Data Quality
**Goal**: Users see live progress during long research runs, worker count adapts to hardware, and reports clearly indicate data confidence levels
**Depends on**: Phase 2 (thread-safe progress queue for SSE), Phase 1 (exception types for retry classification)
**Requirements**: PROG-01, PROG-02, PROG-03, PROG-04, PERF-01, PERF-02, PERF-03, PERF-04, QUAL-01, QUAL-02, QUAL-03, QUAL-04, RPT-01, RPT-02
**Success Criteria** (what must be TRUE):
  1. The web UI shows a live progress bar with percentage and status messages that update in real-time during a research run (no page refresh needed)
  2. Closing and reopening the browser tab reconnects to the progress stream and shows current state
  3. Running in a 2-CPU Docker container uses 2-4 workers instead of detecting 64 host CPUs and spawning 64 workers
  4. Suburb reports display visible warnings when data comes from fallback sources or has low confidence
  5. Excel exports include full demographic breakdowns (household types, income) and infrastructure data (transport, schools, crime)
**Plans**: TBD

Plans:
- [ ] 04-01: SSE progress streaming endpoint and browser client
- [ ] 04-02: Adaptive worker scaling and pipeline optimization
- [ ] 04-03: Data quality tracking, ranking adjustments, and Excel export improvements

### Phase 5: Comprehensive Testing
**Goal**: All hardening work from Phases 1-4 is validated with automated tests covering critical paths, concurrency, and async behavior
**Depends on**: Phases 1-4 (tests validate all prior work)
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06
**Success Criteria** (what must be TRUE):
  1. Cache tests verify that concurrent reads and writes from multiple threads produce no corruption or lost entries
  2. Exception hierarchy tests confirm that every error type (rate limit, timeout, auth, validation) routes to the correct handler
  3. API validation tests pass malformed, partial, and type-mismatched responses through the validators and confirm correct coercion or rejection
  4. End-to-end pipeline test runs discovery through research with mocked API responses and produces valid report output
  5. SSE endpoint tests verify event streaming, client disconnect cleanup, and reconnection using pytest-asyncio
**Plans**: TBD

Plans:
- [ ] 05-01: Unit tests (cache, exceptions, validation, adaptive workers)
- [ ] 05-02: Integration and async tests (pipeline, SSE, thread safety under load)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Security & Error Foundations | 2/2 | Complete | 2026-02-16 |
| 2. Thread Safety & Response Validation | 0/2 | Not started | - |
| 3. Cache Hardening & Crash Recovery | 0/2 | Not started | - |
| 4. Progress, Performance & Data Quality | 0/3 | Not started | - |
| 5. Comprehensive Testing | 0/2 | Not started | - |
