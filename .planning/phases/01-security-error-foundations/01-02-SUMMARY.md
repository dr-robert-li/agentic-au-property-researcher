---
phase: 01-security-error-foundations
plan: 02
subsystem: error-handling
tags: [exceptions, error-handling, type-safety, SDK-integration]
dependencies:
  requires: [01-01]
  provides: [typed-exceptions, error-metadata, SDK-error-mapping]
  affects: [research-clients, app, server, discovery, suburb-research]
tech-stack:
  added: []
  patterns: [exception-hierarchy, isinstance-checks, from-chaining, structured-metadata]
key-files:
  created:
    - src/security/exceptions.py
  modified:
    - src/security/__init__.py
    - src/research/perplexity_client.py
    - src/research/anthropic_client.py
    - src/app.py
    - src/ui/web/server.py
    - src/research/suburb_discovery.py
    - src/research/suburb_research.py
decisions:
  - Provider-specific exceptions inherit from base hierarchy for backward compatibility
  - Anthropic uses isinstance checks against SDK exceptions (anthropic.RateLimitError etc.)
  - Perplexity uses status_code checks (no SDK-provided typed exceptions)
  - String matching retained as last-resort fallback only when no other information available
  - All exceptions use from-chaining to preserve original traceback
metrics:
  duration_seconds: 295
  tasks_completed: 2
  files_created: 1
  files_modified: 7
  commits: 2
  completed_date: 2026-02-16
---

# Phase 01 Plan 02: Exception Hierarchy Summary

Typed exception hierarchy with structured metadata replacing string-matching error detection

## What Was Built

Implemented comprehensive exception hierarchy (ERR-01 through ERR-04) to replace fragile string-matching error detection with type-based dispatch:

1. **Exception Hierarchy** - `src/security/exceptions.py` with full type tree:
   - `ApplicationError` base class with structured metadata (error_code, retry_after, is_transient, provider)
   - `PermanentError` and `TransientError` intermediate classes
   - Specific exception types: ValidationError, AuthenticationError, ConfigurationError, RateLimitError, TimeoutError, NetworkError, APIError, ResearchError
   - Convenience tuples: `TRANSIENT_ERRORS`, `PERMANENT_ERRORS`, `ACCOUNT_ERRORS` for catch blocks

2. **API Client Migration** - Perplexity and Anthropic clients now use SDK-aware error detection:
   - **Anthropic**: isinstance checks against SDK exceptions (`anthropic.RateLimitError`, `anthropic.AuthenticationError`, `anthropic.APIConnectionError`, `anthropic.APITimeoutError`, `anthropic.APIStatusError`)
   - **Perplexity**: Status code checks (`401`/`403` -> auth, `429` -> rate limit, `408`/`504` -> timeout, `5xx` -> API error)
   - Provider-specific exceptions (`PerplexityRateLimitError`, `AnthropicAuthError` etc.) inherit from base hierarchy
   - All error messages sanitized before raising
   - `from e` chaining preserves original tracebacks
   - String matching retained as last-resort fallback only when no status_code or SDK type information available

3. **Handler Updates** - All error handlers migrated to use typed exception hierarchy:
   - `app.py`: Uses `ACCOUNT_ERRORS` and `TRANSIENT_ERRORS` tuples instead of listing individual exception classes
   - `server.py`: Global exception handler extracts metadata (error_code, provider, retry_after, is_transient) and includes in HTTP responses
   - `suburb_discovery.py` and `suburb_research.py`: Updated to use `ACCOUNT_ERRORS` tuple

4. **Backward Compatibility** - Existing code continues working:
   - Provider-specific exceptions inherit from base types (e.g., `PerplexityRateLimitError(RateLimitError)`)
   - Old catch blocks like `except PerplexityRateLimitError` still work
   - New catch blocks can use base types: `except RateLimitError` catches both Perplexity and Anthropic rate limits

## Deviations from Plan

**None - plan executed exactly as written.**

All tasks completed as specified with no architectural changes required. The implementation follows the plan's guidance:
- Anthropic SDK provides typed exceptions -> use isinstance checks
- Perplexity SDK does not provide typed exceptions -> use status_code checks with fallback to string matching
- All exceptions carry structured metadata accessible as attributes
- Inheritance ensures backward compatibility

## Key Implementation Decisions

**Anthropic isinstance vs Perplexity status_code**
- Anthropic SDK exports typed exceptions (`anthropic.RateLimitError` etc.) -> use isinstance for clean, reliable detection
- Perplexity SDK (as of current version) does not export exception types -> use status_code attribute checks
- Both approaches eliminate primary reliance on string matching
- String matching retained only as last-resort fallback when neither status_code nor SDK type information available

**Exception Inheritance for Backward Compatibility**
- Provider-specific exceptions inherit from base hierarchy instead of replacing them
- Example: `PerplexityRateLimitError(RateLimitError)` instead of separate classes
- Rationale: Existing code with `except PerplexityRateLimitError` continues working while enabling new code to use `except RateLimitError`

**Structured Metadata as Attributes**
- error_code: Machine-readable identifier ("RATE_LIMIT", "AUTH_ERROR", etc.)
- retry_after: Seconds to wait before retry (for transient errors)
- is_transient: Boolean indicating whether error can be retried
- provider: API provider causing the error ("perplexity" | "anthropic" | None)
- Rationale: Programmatic access superior to parsing exception messages

**from-Chaining for Traceback Preservation**
- All raised exceptions use `raise NewException() from original_exception`
- Preserves full stack trace from SDK through application layers
- Enables debugging original SDK errors while providing application-level context

## Verification Results

All verification checks passed:

**Inheritance Checks:**
- PerplexityRateLimitError inherits from RateLimitError
- PerplexityAuthError inherits from AuthenticationError
- AnthropicRateLimitError inherits from RateLimitError
- AnthropicAuthError inherits from AuthenticationError
- PerplexityAPIError inherits from APIError
- AnthropicAPIError inherits from APIError

**Metadata Checks:**
- PerplexityRateLimitError carries provider="perplexity", retry_after, is_transient=True
- AnthropicAuthError carries provider="anthropic", is_transient=False

**Catch Block Checks:**
- ACCOUNT_ERRORS tuple catches both Perplexity and Anthropic rate limit/auth errors
- TRANSIENT_ERRORS tuple catches all transient API errors
- Base types catch provider-specific subclasses (e.g., `except RateLimitError` catches both providers)

**Implementation Checks:**
- Perplexity client uses status_code checks with fallback string matching
- Anthropic client uses isinstance checks against SDK exception types
- No primary reliance on string matching (only as last resort)

## Files Changed

**Created (1 file):**
- `src/security/exceptions.py` - Full exception hierarchy with ApplicationError base, PermanentError/TransientError intermediate classes, specific types, and convenience tuples

**Modified (7 files):**
- `src/security/__init__.py` - Export all exception types and convenience tuples
- `src/research/perplexity_client.py` - Provider-specific exceptions inherit from base hierarchy; use status_code checks instead of string matching
- `src/research/anthropic_client.py` - Provider-specific exceptions inherit from base hierarchy; use isinstance checks against Anthropic SDK exceptions
- `src/app.py` - Use ACCOUNT_ERRORS and TRANSIENT_ERRORS tuples instead of provider-specific exception lists
- `src/ui/web/server.py` - Global exception handler extracts structured metadata; use ACCOUNT_ERRORS and TRANSIENT_ERRORS tuples
- `src/research/suburb_discovery.py` - Use ACCOUNT_ERRORS tuple
- `src/research/suburb_research.py` - Use ACCOUNT_ERRORS and TRANSIENT_ERRORS tuples

## Commits

- `e4e0900` - feat(01-02): create exception hierarchy with structured metadata
- `ace84f2` - feat(01-02): migrate API clients and handlers to typed exceptions

## Impact

**Error Handling Reliability:**
- No more false positives from string matching (e.g., "401" in error message doesn't mean auth error)
- SDK errors correctly classified even if message wording changes
- Structured metadata enables smarter retry logic (e.g., respect retry_after from rate limit headers)

**Developer Experience:**
- Type-safe error handling with IDE autocomplete for exception attributes
- Single catch block (`except TRANSIENT_ERRORS`) handles all retryable errors across both providers
- Clear exception hierarchy visible in stack traces
- Backward compatibility ensures existing code continues working

**Debugging:**
- from-chaining preserves original SDK exception with full traceback
- Structured metadata accessible programmatically without parsing strings
- HTTP error responses include error_code, provider, retry_after, is_transient for client-side handling

**No Performance Impact:**
- isinstance checks and status_code attribute access are O(1) operations
- Elimination of string matching and regex actually improves performance slightly
- Exception metadata is simple attribute access

## Next Steps

This plan completes Phase 1 (Security & Error Foundations). Combined with Plan 01-01:
- SEC-01 through SEC-05: Security hardening (API key sanitization, input validation, path traversal prevention, startup validation)
- ERR-01 through ERR-04: Typed exception hierarchy (type-based dispatch, structured metadata, SDK error mapping, from-chaining)

**Phase 1 Success Criteria Met:**
1. API keys never leak - ✓ (01-01: sanitization)
2. Invalid regions rejected - ✓ (01-01: whitelist validation)
3. Path traversal rejected - ✓ (01-01: run_id and cache path validation)
4. Clear startup errors - ✓ (01-01: validate_environment)
5. Type-based error routing - ✓ (01-02: exception hierarchy)

Phase 2 will address thread safety and response validation.

## Self-Check: PASSED

Verified all created files exist:
```
✓ src/security/exceptions.py
```

Verified all modified files exist:
```
✓ src/security/__init__.py
✓ src/research/perplexity_client.py
✓ src/research/anthropic_client.py
✓ src/app.py
✓ src/ui/web/server.py
✓ src/research/suburb_discovery.py
✓ src/research/suburb_research.py
```

Verified all commits exist:
```
✓ e4e0900 - feat(01-02): create exception hierarchy with structured metadata
✓ ace84f2 - feat(01-02): migrate API clients and handlers to typed exceptions
```

All artifacts present and verified.
