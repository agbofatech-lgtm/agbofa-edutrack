# Environment variable reference

The tracked `.env.example` is a blank local template. Django reads the repository-root `.env` when present; production values must be injected by an Owner-controlled secret store. Do not commit `.env`, paste secret values into issues/PRs, or reuse local secrets in another environment.

| Variable | Required | Purpose / notes |
|---|---:|---|
| `DJANGO_ENV` | Yes | `development`, `test`, or `production`; settings module remains explicitly selected. |
| `DJANGO_DEBUG` | Dev only | Debug flag; must be false in production. Production settings force false. |
| `DJANGO_SECRET_KEY` | Yes outside isolated tests | Unique high-entropy Django signing secret. No production default exists. Rotate through a planned session invalidation process. |
| `DJANGO_ALLOWED_HOSTS` | Production | Comma-separated hostnames accepted by Django. Never use `*` in production. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | When required | Comma-separated trusted scheme+host origins; configure only the final approved same-origin service/domain. |
| `DATABASE_URL` | Yes outside isolated tests | PostgreSQL connection URL; use TLS/private networking and least-privilege DB credentials in shared environments. |
| `DB_CONN_MAX_AGE` | No | Persistent connection lifetime in seconds; default 60 pending load/connection-pool review. |
| `DB_CONNECT_TIMEOUT` | No | PostgreSQL connection timeout in seconds; default 5, subject to deployment/network review. |
| `REDIS_URL` | Required by production settings | Private Redis cache URL. Local example is loopback only; production must use access control and transport protection. |
| `CELERY_BROKER_URL` | If using Celery | Defaults to `REDIS_URL`; no task worker or production task is enabled in this milestone. |
| `SESSION_COOKIE_AGE` | No | Session lifetime in seconds; default 28,800 (eight hours) is a proposed technical default pending formal session-policy approval. |
| `SESSION_EXPIRE_AT_BROWSER_CLOSE` | No | Expire session at browser close; defaults true, subject to Owner-approved session policy. |
| `LOG_LEVEL` | No | Structured console logging level; defaults to `INFO`. Avoid verbose/debug logging with real data. |
| `API_PROXY_TARGET` | Local web only | Vite proxy destination, default `http://127.0.0.1:8000`; not used by browser code. |
| `API_UPSTREAM` | Future web service | Owner-configured backend origin for Nginx `/api/` proxy; origin only (no credentials, path, query or default service address). |
| `PORT` | Railway/container | Platform-provided listening port; web entrypoint uses 8080 only as a local/container fallback. |
| `POSTGRES_DB` | Compose only | Local Postgres database name. |
| `POSTGRES_USER` | Compose only | Local Postgres user name. |
| `POSTGRES_PASSWORD` | Compose only | Generated local-only database secret; Compose fails if it is blank. |

## Production fail-closed requirements

`config.settings.production` requires a non-empty `DJANGO_SECRET_KEY`, `DATABASE_URL`, `DJANGO_ALLOWED_HOSTS`, and `REDIS_URL`, and sets secure cookies, HTTPS redirect/HSTS and proxy-header handling. `SECURE_PROXY_SSL_HEADER` is safe only when the origin is reachable exclusively through a trusted TLS-terminating proxy. The Railway template is not proof that this topology exists.
