# AGBOFA EduTrack

Engineering foundation for E.P. Basic School, Ashaiman, extended with Prompt 03 institutional-configuration foundations. This repository contains a React/TypeScript PWA shell, a versioned Django REST API, identity/RBAC primitives, institution-scoped academic configuration, local developer tooling, and architecture documentation.

> **Scope:** Prompt 01/02 engineering and identity foundations plus Prompt 03 institutional configuration only. Prompt 02 remains accepted by the Owner as an engineering foundation, not as approval of authentication policy or production use. Prompt 03 remains pending Owner acceptance. This is not a school operations product: AIM-01 through AIM-06 and all later operational modules remain unimplemented. No live learner, guardian, staff, academic, or financial data is included; no operational mock, allowance, fee, payment, or finance workflow is implemented; and no production deployment has occurred.

## Architecture at a glance

- `frontend/` — React + TypeScript + Vite, Tailwind CSS, static-shell PWA, session-aware authentication, accessible dynamic institutional-configuration forms, and a permission-informed shell.
- `backend/` — Django + Django REST Framework modular-monolith foundation, `/api/v1/`, PostgreSQL settings, session/CSRF authentication, privileged MFA and server-enforced scoped RBAC.
- `backend/institutional/` — institution tenancy, versioned release and approval lifecycle, academic years/terms, levels/classes/streams, subject catalogue and offerings, teaching assignments, staff affiliations, typed settings, and opaque enrolment-placement foundations. No school values are seeded.
- `identity/` — data-defined roles/scopes, append-only ORM audit events, encrypted TOTP credentials, and a disabled-by-default account-recovery adapter seam.
- Redis/Celery — configured integration seams only; no business task is registered or run.
- `docs/` — architecture decisions, boundaries, data design, threat model, setup, requirements traceability, [Prompt 02 evidence](docs/prompt-02-foundation-identity.md), and the [Prompt 03 report](docs/prompt-03-institutional-configuration.md).
- `deploy/` — container and Railway service configuration templates only. Nothing has been deployed or provisioned.

See [local developer setup](docs/developer-setup.md), [architecture overview](docs/architecture/overview.md), [data architecture](docs/architecture/data-architecture.md), and [requirements traceability](docs/requirements-traceability.md).

## Quick start

1. Install Node.js 22+, Python 3.11+, PostgreSQL 16+ and Redis 7+ (or start only local infrastructure with `docker compose up -d db redis`).
2. Copy `.env.example` to `.env`; generate unique local values for `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`. Generate a separate 32-byte `MFA_ENCRYPTION_KEY` only if testing privileged MFA locally, then set a matching `DATABASE_URL`. Do not use local values in a shared or production environment.
3. Install backend dependencies: `python -m pip install -r backend/requirements/dev.txt`.
4. In the repository root, run backend development commands with `PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.development python backend/manage.py check`. See the setup guide for tests and local schema commands.
5. Install and run the frontend: `cd frontend && npm ci && npm run dev`.

The Vite development server binds to `0.0.0.0:5173` and proxies same-origin `/api/*` requests to the backend at `127.0.0.1:8000` by default. Browser code uses relative API paths and never calls localhost directly.

## Quality checks

```sh
cd frontend && npm ci && npm run typecheck && npm run lint && npm run format:check && npm test && npm run build
cd .. && python -m pip install -r backend/requirements/dev.txt
PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.test python backend/manage.py check
PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.test pytest backend
cd backend && ruff check . && ruff format --check . && mypy config core identity institutional
cd .. && python scripts/validate_config.py
```

Security/dependency checks are `npm audit --audit-level=high` in `frontend/`, `pip-audit -r backend/requirements/dev.txt`, and `make secrets-check` from the repository root. CI also runs source secret scanning and GitHub dependency review on pull requests.

## Important limitations and gates

- Prompt 03 adds an initial **institutional-app migration** for testable schema evolution. It has not been run against shared or production data. The identity security models retain the existing CI-only table-creation arrangement. A reviewed migration, rollback/forward-fix, backup/restore and release plan is still required before any shared or production use.
- Local backend tests use isolated in-memory SQLite. GitHub Actions verifies the backend suite against an ephemeral PostgreSQL 16 service, including the institutional migration. Neither validates production configuration, real data, performance, Redis connectivity, or backup/restore.
- No institutions, academic calendars, classes, streams, subjects, settings, user grants, or rates are preloaded. Institutional values are entered only by explicitly scoped actors. Enrolment foundations carry opaque learner-registry UUIDs only; they are not learner profiles.
- Recovery delivery remains disabled unless an Owner-approved adapter and token lifetime are configured. No email/SMS provider is assumed or enabled. MFA encryption requires a separately managed secret key.
- No real users, school role/permission matrix, role-grant management endpoint, operational mock or allowance workflow, payment integration, or credentials are seeded. Staff affiliation is distinct from RBAC and grants no role. Do not provision live access through direct model/database writes.
- Headmaster mock/allowance approval, Local Manager/Secretary arrangements and rate decisions, Finance Director rate configuration, JHS Contact Person preparation, and Finance payment processing remain governance boundaries for future work only. No rates or entitlements are encoded.
- Unresolved Prompt 02 decisions remain unapproved: MFA role mapping, recovery and proofing process, role/scope matrix, session/rate policy, maker-checker authority, audit retention, and production security. Prompt 03 does not resolve them.
- The role-aware shell reflects only server-derived permissions; navigation is not an authorization boundary. PWA caching remains limited to public static assets.
- The visual monogram is a generic placeholder, not an approved school logo. Committed PWA icons are unchanged.
- The API readiness endpoint verifies only the configured database connection. It does not claim that Redis, Celery, or any business module is healthy.
- The service files are templates for a future owner-controlled deployment. No Railway project, resource, variable, domain, or deployment was changed.
