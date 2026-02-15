# Agentic RE Researcher v2.0

## What This Is

A Python application that uses Perplexity's Agentic Research API (and Anthropic Claude as fallback) to generate exhaustive, data-rich suburb-level investment reports for Australian property. Supports both a browser GUI (FastAPI) and an interactive CLI, with HTML/PDF/Excel reporting, chart generation, and file-based caching. v2.0 focuses on hardening the existing system: fixing bugs, closing security gaps, improving reliability, adding crash recovery, and achieving comprehensive test coverage.

## Core Value

Every research run produces trustworthy, complete suburb investment reports — no silent failures, no stale data presented as fresh, no security leaks.

## Requirements

### Validated

- ✓ Suburb discovery via Perplexity deep-research API with regional filtering — existing
- ✓ Parallel per-suburb detailed research with configurable workers — existing
- ✓ Composite ranking by projected equity growth with risk adjustment — existing
- ✓ HTML report generation (overview + per-suburb) with Jinja2 templates — existing
- ✓ Chart generation (price history, growth projections, DOM, comparison bars) — existing
- ✓ PDF export with embedded charts — existing
- ✓ Excel export with suburb data — existing
- ✓ FastAPI web UI with form input, run management, status polling — existing
- ✓ Interactive CLI with prompt_toolkit autocomplete and rich progress — existing
- ✓ File-based JSON cache with TTL (24h discovery, 7d research) — existing
- ✓ Anthropic Claude fallback when Perplexity unavailable — existing
- ✓ Run comparison across multiple research runs — existing
- ✓ Pydantic v2 data models with validation — existing
- ✓ Multi-region filtering (states, sub-regions, all Australia) — existing

### Active

- [ ] Fix all security vulnerabilities (API key exposure, input validation, path traversal)
- [ ] Replace fragile string-matching error handling with proper exception hierarchy
- [ ] Add JSON schema validation for all API responses (Perplexity + Anthropic)
- [ ] Fix thread safety issues (cache singleton race condition, concurrent web dict access)
- [ ] Fix Excel export to include full demographic and infrastructure data
- [ ] Add cache index backup and corruption recovery
- [ ] Implement crash recovery — resume interrupted runs from cached progress
- [ ] Add real-time progress streaming to web UI (WebSocket or SSE)
- [ ] Coordinate parallel worker timeouts with shared timeout pool
- [ ] Optimize discovery-to-research pipeline (reduce wasteful candidate multiplication)
- [ ] Make parallel worker count adaptive (based on CPU/memory)
- [ ] Add cache size limits with LRU eviction
- [ ] Clean up in-memory run tracking (persist to filesystem, auto-cleanup old runs)
- [ ] Document and extract ranking weights to configuration
- [ ] Mark fallback metrics with data_quality flag; exclude/downweight in rankings
- [ ] Achieve comprehensive test coverage for all identified gaps

### Out of Scope

- Batch mode with external input file — complexity not justified for v2.0
- Database migration (SQLite/PostgreSQL) — file-based approach sufficient for now
- Mobile app or native desktop packaging — web + CLI sufficient
- OAuth/SSO authentication for web UI — single-user tool

## Context

This is a brownfield v2.0 milestone. The v1 application is functional end-to-end but has accumulated technical debt, security gaps, and reliability concerns identified during codebase mapping (see `.planning/codebase/CONCERNS.md`). The codebase is ~4,000+ lines of Python across 20+ modules. Breaking changes are acceptable — this is a clean-break version upgrade.

Key existing architecture:
- Layered pipeline: discovery → research → ranking → reporting
- Parallel execution via ThreadPoolExecutor
- Pluggable research providers (Perplexity, Anthropic)
- Dual UI (FastAPI web, prompt_toolkit CLI)
- File-based caching with JSON index

## Constraints

- **Tech stack**: Python 3.14+, existing dependency set (FastAPI, Pydantic v2, matplotlib, etc.)
- **API providers**: Must continue supporting Perplexity and Anthropic as research backends
- **Breaking changes**: Allowed for v2.0 — no backwards compatibility requirement with v1 cache/config
- **Test coverage**: All identified gaps in CONCERNS.md must have tests

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Clean break for v2.0 | Allows restructuring error handling, cache format, config without migration complexity | — Pending |
| Resume-only (no batch mode) | Crash recovery via cache is highest value; batch mode adds scope without proportional benefit | — Pending |
| WebSocket/SSE for progress | Real-time streaming superior to polling for long research runs | — Pending |
| Adaptive worker count | Hardcoded workers cause issues on varied hardware | — Pending |

---
*Last updated: 2026-02-15 after initialization*
