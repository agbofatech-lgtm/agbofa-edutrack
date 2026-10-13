# AGBOFA EduTrack

Foundation-only engineering baseline for E.P. Basic School, Ashaiman. This repository contains a React/TypeScript PWA shell, a versioned Django REST API foundation, identity/RBAC primitives, local developer tooling, and architecture documentation.

> **Scope:** Prompt 01 and Prompt 02 foundations only. This is not a school operations product. It contains no learner, assessment, report-card, mock-examination, intervention, billing, payment, or finance workflows; no live school data; and no production deployment. Master Requirements v1.5 remains subject to Owner decisions and its wider implementation/release gates remain closed.

## Architecture at a glance

- `frontend/` — React + TypeScript + Vite, Tailwind CSS, installable static-shell PWA, session-aware authentication and role-aware foundation shell.
- `backend/` — Django + Django REST Framework modular-monolith foundation, `/api/v1/`, PostgreSQL settings, session/CSRF authentication, privileged TOTP MFA, and server-side RBAC primitives.
- `identity/` — data-defined roles/scopes, append-only ORM audit events, encrypted TOTP credentials, and a disabled-by-default account-recovery adapter seam.
- Redis/Celery — configured integration seams only; no background business task is registered or run.
- `docs/` — architecture decisions, boundaries, conceptual data design, threat model, setup, requirements traceability and [Prompt 02 owner decisions](docs/prompt-02-foundation-identity.md).
- `deploy/` — container and Railway service configuration templates only. Nothing has been deployed or provisioned.

See [Local developer setup](docs/developer-setup.md), [architecture overview](docs/architecture/overview.md), and [requirements traceability](docs/requirements-traceability.md).

## Quick start

1. Install Node.js 22+, Python 3.11+, PostgreSQL 16+ and Redis 7+ (or start only local infrastructure with `docker compose up -d db redis`).
2. Copy `.env.example` to `.env`; generate unique local values for `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`. Generate a separate 32-byte `MFA_ENCRYPTION_KEY` only if testing privileged MFA locally, then set a matching `DATABASE_URL`. Do not use local values in any shared or production environment.
3. Install backend dependencies: `python -m pip install -r backend/requirements/dev.txt`.
4. In the repository root, run backend development commands with `PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.development python backend/manage.py check`. See the setup guide for tests and run commands.
5. Install and run the frontend: `cd frontend && npm ci && npm run dev`.

The Vite development server binds to `0.0.0.0:5173` and proxies same-origin `/api/*` requests to the backend at `127.0.0.1:8000` by default. Browser code uses relative API paths and never calls localhost directly.

## Quality checks

```sh
cd frontend && npm ci && npm run typecheck && npm run lint && npm run format:check && npm test && npm run build
cd .. && python -m pip install -r backend/requirements/dev.txt
PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.test python backend/manage.py check
PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.test pytest backend
cd backend && ruff check . && ruff format --check . && mypy config core identity
cd .. && python scripts/validate_config.py
```

Security/dependency checks are `npm audit --audit-level=high` in `frontend/`, `pip-audit -r backend/requirements/dev.txt`, and `make secrets-check` from the repository root. CI also runs source secret scanning and GitHub dependency review on pull requests.

## Important limitations

- No migrations are committed or run against a shared/production database. Identity MFA and recovery model definitions are exercised only in disposable test databases; a reviewed schema/migration set is required before any deployment.
- Local backend tests use in-memory SQLite; GitHub Actions runs the backend suite against an ephemeral PostgreSQL 16 service. Neither validates production migrations, Redis connectivity, performance, or backup/restore.
- Recovery delivery is disabled unless an Owner-approved adapter and token lifetime are configured. No email/SMS provider is assumed or enabled. MFA encryption requires a separately managed secret key.
- No real users, school role/permission matrix, operational records, payment integrations, or credentials are seeded. Role/grant management endpoints and automated grant-change auditing are not implemented; no live access should be assigned through direct model/database writes.
- The role-aware shell reflects only active data-derived roles and platform MFA state; no unapproved business navigation is exposed. Navigation is not an authorization boundary.
- The visual monogram is a generic application placeholder, not an approved school logo. Committed PWA icons are unchanged.
- The API readiness endpoint verifies only the configured database connection. It does not claim that Redis, Celery, or any business module is healthy.
- Session duration, rate-limit defaults, school-specific privileged roles, account proofing/recovery, factor-reset, scope hierarchy, audit retention/DB immutability, and maker-checker policies still need Owner decisions before external exposure.
- The service files are templates for a future owner-controlled deployment. No Railway project, resource, variable, domain, or deployment was changed.
