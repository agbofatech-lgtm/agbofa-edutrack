# Local developer setup

## Prerequisites

- Node.js 22.x and npm (the checked-in lockfile is the install source; use `npm ci`).
- Python 3.11+ and pip.
- PostgreSQL 16+ and Redis 7+ for a complete local API run. Docker Compose is optional and used only for local dependency containers.

## 1. Create local-only environment values

From the repository root:

```sh
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(64))'  # set DJANGO_SECRET_KEY in .env
python -c 'import secrets; print(secrets.token_hex(32))'       # set POSTGRES_PASSWORD in .env
```

Set `DATABASE_URL` to match the local `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and host, for example:

```text
postgresql://edutrack_local:<your-generated-hex-password>@127.0.0.1:5432/edutrack_local
```

Replace the placeholder yourself in `.env`; do not paste or commit generated secrets. The root `.env` is git-ignored. The example values are local-only and must not be reused in a shared environment.

If using Compose, start only the database and cache/broker:

```sh
docker compose up -d db redis
```

The Compose ports bind to `127.0.0.1` and the Postgres password is required. The local Redis container has no auth only because it is loopback-bound development infrastructure; use an authenticated, private/TLS endpoint outside local development.

## 2. Install backend and create a local-only schema

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements/dev.txt
```

The repository intentionally contains no committed Django migrations. If you want a complete local API login/session run, use the following only against a disposable local database after confirming `DATABASE_URL` points there:

```sh
PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.development \
  python backend/manage.py migrate --run-syncdb --noinput
PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.development \
  python backend/manage.py createsuperuser
PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.development \
  python backend/manage.py runserver 0.0.0.0:8000
```

`migrate --run-syncdb` here is a local developer convenience, not a reviewed production migration path. Do not run it against shared/staging/production infrastructure. A real, reviewed migration set is a future gated deliverable.

Liveness is available at `http://127.0.0.1:8000/api/v1/health/live/`; readiness at `/api/v1/health/ready/` checks PostgreSQL only. No Redis worker, role seed, learner record or business endpoint is created.

## 3. Install and run the frontend

```sh
cd frontend
npm ci
npm run dev
```

Vite binds to `0.0.0.0:5173`; the browser calls only relative `/api/v1/*` URLs. The dev server proxies `/api` to `http://127.0.0.1:8000` by default. Override the backend proxy target using the Node environment variable `API_PROXY_TARGET` when required. In Arena preview, `.e2b.app` is explicitly allowed as a Vite host.

## 4. Run checks

From `frontend/`:

```sh
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
npm audit --audit-level=high
```

From the repository root with `.venv` active:

```sh
PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.test python backend/manage.py check
PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.test pytest backend
cd backend && ruff check . && ruff format --check . && mypy config core identity
cd .. && python scripts/validate_config.py
pip-audit -r backend/requirements/dev.txt
```

Local backend test settings use an isolated in-memory SQLite database. The GitHub Actions backend job separately opts into `config.settings.ci_postgres` and a disposable PostgreSQL 16 service with trust authentication confined to that ephemeral CI container. This exercises PostgreSQL query/model behavior without production infrastructure or records; it does not validate production performance, migrations, Redis connectivity, or backup/restore behavior.

## 5. Code conventions

- Keep business domains behind the module boundaries in `architecture/module-boundaries.md`.
- Add tests for both authorized and unauthorized paths; negative record-scope tests are mandatory for future endpoints.
- Do not seed roles from job-title assumptions; obtain the approved matrix first.
- Never write secrets, raw passwords, request bodies, or real learner/financial data to logs or fixtures.
- Keep offline caching limited to public static shell assets until device-loss, consent and conflict policy has an Owner-approved design.
- Update ADRs, traceability and API contract docs when architecture changes.
