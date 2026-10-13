# Environment variable reference

The tracked `.env.example` is a blank local template. Django reads the repository-root `.env` when present; production values must be injected by an Owner-controlled secret store. Do not commit `.env`, paste secret values into issues/PRs, or reuse local secrets in another environment.

| Variable | Required | Purpose / notes |
|---|---:|---|
| `DJANGO_ENV` | Yes | `development`, `test`, or `production`; settings module remains explicitly selected. |
| `DJANGO_DEBUG` | Dev only | Debug flag; must be false in production. Production settings force false. |
| `DJANGO_SECRET_KEY` | Yes outside isolated tests | Unique high-entropy Django signing secret. No production default exists. Rotate through a planned session invalidation process. |
| `MFA_ENCRYPTION_KEY` | When enrolling privileged MFA | Separate URL-safe Base64 encoding of exactly 32 random bytes for AES-256-GCM TOTP-secret encryption. There is no default; missing/invalid configuration fails closed. Keep it separate from `DJANGO_SECRET_KEY` and plan key backup/rotation before use. |
| `IDENTITY_MFA_SETUP_TTL_SECONDS` | No | Short-lived setup/pre-authentication window; technical default 300 seconds pending Owner policy review. |
| `IDENTITY_RECOVERY_DELIVERY_BACKEND` | No; disabled by default | Optional dotted Python backend implementing `deliver_recovery_token`. Do not configure until the Owner approves the recovery channel, identity proofing, and destination rules. No email/SMS backend is included. |
| `IDENTITY_RECOVERY_TOKEN_TTL_SECONDS` | Only with approved recovery adapter | Defaults to `0`, which disables token issuance. A positive expiry must be explicitly approved and configured before any adapter can send a token. |
| `IDENTITY_LOGIN_RATE_LIMIT` | No | DRF login throttle default `10/min`; an operational default pending Owner approval and reverse-proxy/client-IP review. |
| `IDENTITY_MFA_RATE_LIMIT` | No | DRF MFA challenge throttle default `10/min`; an operational default pending Owner approval and reverse-proxy/client-IP review. |
| `IDENTITY_RECOVERY_RATE_LIMIT` | No | DRF recovery throttle default `5/hour`; an operational default pending Owner approval and reverse-proxy/client-IP review. |
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

## Prompt 02 identity gates

- Recovery delivery is intentionally off unless both an Owner-approved adapter and positive token lifetime are supplied. There is no built-in email/SMS integration, no verified contact-channel model, and no provider credentials.
- Privileged TOTP setup uses `MFA_ENCRYPTION_KEY`; the API does not fall back to signing/encrypting with the Django session secret. The key is not populated in `.env.example`.
- The rate-limit defaults are implementation-level starting points, not approved school/security policy. Production rate-limit behavior depends on a trusted proxy/client-IP configuration and a shared cache; validate the actual deployment topology before exposure.
- These settings do not authorize schema migrations, account provisioning, a recovery channel, or production deployment.
