# ADR-0005: Railway-ready templates without deployment

- **Status:** Accepted for foundation; deployment is not authorized
- **Date:** 2026-10-13

## Decision

Include container builds for a Django API and React static web service, an Nginx same-origin API proxy, a backend Railway config at the repository root and a separate web Railway config template. Runtime secrets and service-to-service URLs are environment inputs. No default production password, project, service, database, Redis instance, domain, variable, migration or deployment is created.

## Consequences

An Owner or deployment administrator must configure/verify service config file paths, health-check behavior, networking, TLS/origin allowlists, `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `REDIS_URL`, `CELERY_BROKER_URL`, `API_UPSTREAM`, database backups and budgets before any deployment. These templates have not been validated against a Railway project.
