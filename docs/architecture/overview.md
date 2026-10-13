# Architecture overview — Prompt 01/02 foundation

## Status and scope

This is a modular-monolith foundation, not a deployed or school-approved production system. Prompt 01 and the Owner-authorized Prompt 02 scope are limited to engineering/identity foundations. Business modules, policy activation, external recovery channels, live data, migration execution, pilot and release gates remain closed. The stack follows the Prompt 01 recommendation; no architecture deviation is proposed.

## System context

```mermaid
flowchart LR
    Browser[Mobile / desktop browser\nReact + TypeScript PWA]
    Web[Nginx static web service\nCSP + same-origin /api proxy]
    API[Django REST Framework\nversioned modular monolith]
    DB[(PostgreSQL\ntransactional persistence)]
    Cache[(Redis\ncache / Celery broker)]
    Worker[Celery worker\nnot started; no business tasks]

    Browser -->|HTTPS, same origin| Web
    Web -->|/api/v1/*| API
    API --> DB
    API -. optional cache/broker .-> Cache
    Worker -. justified future jobs only .-> Cache
```

Local development uses Vite on `:5173`, Django on `:8000`, PostgreSQL and Redis on loopback-bound development ports. Vite proxies relative `/api/*` requests to Django; browser code has no localhost URL or CORS bypass. The future web service uses Nginx to proxy `/api/*` to a separately configured API service, preserving same-origin session cookies and CSRF checks.

## Dependency direction

```mermaid
flowchart TD
    UI[frontend shell] --> HTTP[versioned API contracts]
    HTTP --> CORE[core: health, request IDs, logging]
    HTTP --> ID[identity: user, role, permission, scope, audit]
    ID --> DB[(PostgreSQL)]
    CORE --> DB
    JOBS[future justified jobs] -. Celery .-> REDIS[(Redis)]
    ID -. cache only when needed .-> REDIS
    DOMAIN[future academic / assessment / attendance / recovery / reporting / finance] -. must depend on shared identity and contracts .-> CORE
```

The future business domains must remain separate packages with explicit service/API boundaries. They must not import one another's private models. Shared invariants (authorization, audit, configuration versioning, transaction ownership) belong in the platform layer or in narrowly defined domain services.

## Runtime contracts

- API prefix: `/api/v1/`, using DRF namespace versioning. `v1` is the only accepted version in this foundation.
- Health: `/api/v1/health/live/` reports process liveness only; `/api/v1/health/ready/` checks one constant PostgreSQL query. Neither checks Redis, Celery, or future business functionality.
- Authentication: Django session cookies, JSON CSRF-token endpoint, same-origin no-store requests, generic credential errors, server-reported expiry and client expiry handling. Django `is_staff`/`is_superuser` accounts must complete RFC 6238 TOTP; seeds are AES-GCM encrypted using a separate environment key. Recovery tokens are hashed, single-use, and deliverable only through an explicitly configured adapter; no adapter is included or active.
- Authorization: API defaults to authenticated access. Role and permission identifiers are derived from effective server-side grants; `HasRBACPermission` and `scope_queryset` fail closed for missing contracts and scope grants. No school role matrix, domain permission catalog, grant-management API, or business endpoint is created. A client-side navigation item is not an authorization check.
- Jobs: Celery app and Redis settings are present; no task is registered or dispatched. Add a job only after the process, retry, idempotency, visibility, privacy and failure-handling need is reviewed.
- Offline: the service worker precaches public static shell assets only, prompts before activating updates, excludes `/api/` navigations, and has no runtime cache rules. API fetches and responses carry no-store directives; no credentials, learner records, financial data, or writes are cached or queued.

## Data and environment

PostgreSQL is the target persistence engine. Local `config.settings.test` uses an isolated in-memory SQLite database. GitHub Actions runs the backend suite against a disposable PostgreSQL 16 service using the explicit `config.settings.ci_postgres` module; it does not use production infrastructure or records. The first domain schema is a conceptual design in [data architecture](data-architecture.md); there are no committed migrations, seed records, or production database actions in this milestone.

All runtime secrets are supplied via environment variables. The tracked `.env.example` contains blank secret fields and local-only variable names, never credentials. Railway files are templates; they do not create a project or resources.

## Quality and operational posture

GitHub Actions validates frontend build/type/lint/tests, backend checks/tests/types/lint, dependency advisories and repository configuration. Merge/deploy approval, backup/restore evidence, Postgres production tuning, observability, incident response and security review remain separate Owner gates.
