# Phase 1: Security & Error Foundations - Context

**Gathered:** 2026-02-15
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase closes security gaps (API key sanitization, input validation for regions/run IDs/cache paths, API key format validation) and establishes a typed exception hierarchy to replace all string-matching error detection in API clients. No new user-facing features — this is internal hardening.

</domain>

<decisions>
## Implementation Decisions

### API Key Leak Prevention
- **Redaction style:** Claude's discretion — choose the best approach based on security best practices (full redaction vs partial masking)
- **Sanitization scope:** Everywhere — logs, error messages, HTTP responses, HTML error pages, stack traces. All output paths must be sanitized
- **Third-party library logs:** Claude's discretion — evaluate whether third-party libraries (Perplexity SDK, httpx, etc.) actually log keys and handle accordingly
- **Secrets scope:** All `.env` values are treated as sensitive, not just API keys. Every value loaded from `.env` should be sanitized from all output paths

### Claude's Discretion
- Redaction format (full `[REDACTED]` vs partial masking like `pplx-****...db`) — pick based on security best practices
- Whether to add a global logging filter for third-party libraries or only sanitize our own code's output
- Error messaging style and verbosity for users (CLI vs web)
- Region whitelist strictness and matching rules
- Startup validation behavior when .env is missing or malformed
- Exception hierarchy granularity

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for all areas not explicitly discussed.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-security-error-foundations*
*Context gathered: 2026-02-15*
