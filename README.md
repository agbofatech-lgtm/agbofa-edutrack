# AGBOFA EduTrack

AGBOFA EduTrack is an owner-controlled Django/React engineering project for E.P. Basic School, Ashaiman. The current branch adds **Phase 04 candidate and academic source operations** to the accepted Phase 01–03 identity and institutional-configuration foundations. This is code for Owner review, **not** an approved production school system. No live pupil/guardian data, school policies, financial rates, official WAEC outcomes or payment rails are included. No shared/production database was migrated and nothing was deployed.

> **Requirements caveat:** The complete Master Requirements v1.5 (Sections 1–37) and 64-prompt roadmap were not available for this session. Phase 04 implements the Owner's explicit directive without guessing their contents. Review [the Phase 04 engineering report](docs/prompt-04-candidate-academic-operations.md) against the full documents before any acceptance or activation. [Phase 03's report](docs/prompt-03-institutional-configuration.md) is historical; Phase 03 has since been accepted by the Owner at `3e3058096b9a846c3134522e346ebf4e8eb8ffea`.

## Source architecture

- `frontend/` — React/TypeScript PWA, session and MFA-aware shell, institutional-configuration forms, and institution-scoped academic tabs for the candidate register/360°, controlled CSV import, BA-0, weekly and monthly mock operations. It does not cache academic API responses or private drafts offline.
- `backend/identity/` — session/CSRF authentication, privileged TOTP, exact role/scope grants, audit and disabled-by-default recovery seam. No school roles or grants are seeded.
- `backend/institutional/` — approved versioned settings, academic structure, teacher/staff affiliations and opaque learner placements from Phase 03.
- `backend/academic/` — Phase 04 candidate/guardian records, typed links to institutional placements, validated import, BA-0 and weekly/mock source/result lifecycles, independent review, immutable approved snapshots and authorized successor revisions. Its initial migration is for disposable test/CI databases only until separate release review.
- `docs/` — [Phase 04 report](docs/prompt-04-candidate-academic-operations.md), [governance decision](docs/adr/0007-academic-source-governance.md), architecture and historical Phase 01–03 records.
- `.github/workflows/ci.yml` — frontend/backend/security checks; disposable PostgreSQL 16 tests and academic-migration forward/reversal checks. `deploy/` contains *templates*, not evidence of deployment.

See [module boundaries](docs/architecture/module-boundaries.md), [security limits](docs/architecture/security.md), and [developer setup](docs/developer-setup.md).

## Run locally, with a disposable database only

1. Install Node.js 22+, Python 3.11+, PostgreSQL 16+ and Redis 7+ (or use `docker compose up -d db redis` for loopback-only local dependencies).
2. Copy `.env.example` to `.env`. Generate distinct local `DJANGO_SECRET_KEY` and (for privileged MFA) `MFA_ENCRYPTION_KEY`; set `DATABASE_URL` **only to a database you control and can discard**. Leave the three `ACADEMIC_*` mock role/level mappings empty unless an Owner-approved policy is being tested. Never use this quick start with a shared or production DB.
3. `python -m pip install -r backend/requirements/dev.txt`; for an intentionally disposable local DB, `PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.development python backend/manage.py migrate --run-syncdb --noinput`, then `python backend/manage.py runserver 0.0.0.0:8000` under the same environment. This is **not** a production migration path.
4. `cd frontend && npm ci && npm run dev`. Vite binds `0.0.0.0:5173` and proxies same-origin `/api/` to the backend. The browser never needs to call localhost across its sandbox boundary.

## Engineering checks

```sh
# Frontend
cd frontend && npm ci && npm run typecheck && npm run lint && npm run format:check && npm test && npm run build
cd ..

# Backend, isolated in-memory SQLite tests
PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.test python backend/manage.py check
PYTHONPATH=backend DJANGO_SETTINGS_MODULE=config.settings.test pytest backend
(cd backend && ruff check . && ruff format --check . && mypy config core identity institutional academic)
python scripts/validate_config.py

# Dependency and tracked-source checks (no secrets in fixtures/logs)
(cd frontend && npm audit --audit-level=high)
pip-audit -r backend/requirements/dev.txt
make secrets-check
```

CI repeats the checks and runs migrations/tests against **ephemeral PostgreSQL 16**, not a school database. Review the committed migration and its reversal in a disposable environment before proposing any real release plan. Tests use invented users, institutions and candidate records; they do not demonstrate production readiness, accessibility certification, a consent basis, scaling or backup/restore.

## Governance and exclusions

- All academic reads/writes require authenticated session, exact institution/action RBAC, record dependency checks and no-store responses; writes require CSRF and transactional validation. Effective `context.permissions` are tenant-specific UI hints, never substitutes for server checks. Import replays are actor/key/payload bound; concurrent drafts require fresh versions; approved records require independent authorizers for corrections.
- No **mock** can be prepared without an approved JHS Contact Person role mapping and Basic 9 level mapping. Headmaster approval/publication/authorization additionally requires the Headmaster mapping and a privileged MFA session; a Local Manager is not the operational mock approver. Blank mappings are deliberate, and a role label or staff membership does not implicitly grant the relevant `academic.*` code.
- BA-0 observation resolution is **not** a verified complete baseline; no coverage policy exists. Weekly/mock quality refers only to explicitly declared blueprints. A scored zero differs from absent, missing and not assessed. No grading, ranking, intelligence, intervention, official BECE prediction or WAEC integration exists.
- Attendance, guardian engagement/messaging, interventions, full reporting, allowances, fee billing, collections, payments and Phase 05+ remain outside this milestone. No financial workflow is created or inferred from mock approval.
- Identity and domain audit managers protect ordinary ORM operations; privileged direct SQL/DB owners remain outside those protections. Review secret rotation, data retention, legal consent, roles, performance, penetration testing, accessibility, UAT, migration/backfill and backup/restore before any live use. The readiness endpoint checks the database only, not worker or academic workflow health. Do not merge, deploy or migrate production solely because these checks pass.
