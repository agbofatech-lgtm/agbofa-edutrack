# ADR-0001: Foundation stack and modular-monolith boundaries

- **Status:** Accepted for Prompt 01 foundation only
- **Date:** 2026-10-13
- **Decision owners:** Owner approval for Prompt 01; technical decision recorded by implementation

## Context

Master Requirements v1.5 recommends a React/TypeScript/Vite PWA, Django REST Framework, PostgreSQL, Redis/Celery and GitHub Actions as a proposed stack, but does not itself approve implementation. The Prompt 01 instruction explicitly authorizes only the engineering foundation. Business-module activation remains gated.

## Decision

Use a modular monolith:

- React 19 + TypeScript 5.9 + Vite 7 for the frontend.
- Tailwind CSS 4 design tokens and reusable low-level components.
- `vite-plugin-pwa` for install metadata and a precache-only service worker.
- Django 5.2 LTS + Django REST Framework 3.18 for a URL-versioned JSON API.
- PostgreSQL as the target persistence engine.
- Redis as optional shared cache and Celery broker seam; do not run a worker or define a task until justified.
- GitHub Actions for CI, dependency/security checks, formatting, lint, type checking, tests and build.
- Separate frontend/API Railway Docker/config templates and same-origin Nginx `/api` proxy; do not deploy or provision anything.

No architecture deviation is proposed from the Prompt 01 recommendation. Version choices are engineering dependencies, not school policy decisions.

## Consequences

Positive: familiar ecosystem, explicit module seams, API/web separation, shared school data model can expand without recreating identity/academic hierarchy, same-origin session/CSRF model, and testable local CI.

Trade-offs: two app build artifacts and two potential deployment services; Python dependency constraints need an explicit lock/refresh process; database schema and all business domains still require approved migrations and contracts; Redis/Celery add operational components only when later work uses them.

## Rejected alternatives

- Microservices: unnecessary deployment and data consistency burden for the current scope.
- Client-side-only auth/role checks: insufficient for learner and finance data protection.
- Browser-stored bearer token/JWT: unnecessary for same-origin web use and increases credential exposure.
- Runtime caching/queueing of authenticated API data: conflicts with the unresolved offline/device-loss policy.
