# ADR-0004: Static-shell PWA; no authenticated offline data

- **Status:** Accepted for foundation
- **Date:** 2026-10-13

## Decision

Provide a web manifest and service worker that precaches the static application shell. Service worker navigation fallback does not intercept `/api/` requests. The UI has honest loading, retryable error and offline copy. Never persist session tokens, learner records, academic marks or finance actions in browser storage or service-worker caches in this milestone.

## Rationale

The requirements require an installable mobile-first experience but record an unresolved offline conflict/device-loss design gap. A static shell supports low-bandwidth/reload behavior without implying unsafe offline workflow semantics.

## Consequences

Offline forms, draft sync, conflict resolution, encrypted device storage, queued writes and payment offline behavior are explicitly out of scope until the school/security policy and lost-device threat model are approved.
