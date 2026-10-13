# Prompt 01 requirements traceability

**Baseline:** AGBOFA EduTrack Master Requirements v1.5, draft for Owner review, dated 13 October 2026. The pasted document retains v1.4/v1.3 headings in carry-forward sections; this implementation treats the supplied v1.5 sections and their stated precedence as the baseline.

**Authority:** The baseline itself says Owner Gate CLOSED and prohibits coding. The Owner separately confirmed that the direct Prompt 01 instruction is the explicit authorization for foundation-only implementation. This approval is limited to Prompt 01. It does not approve business modules, production migrations, live data, payment services, Railway resource changes/deployment, any school policy, DG/IG/RG gates, or Prompt 02.

| Prompt 01 deliverable | Implemented evidence | Limit / status |
|---|---|---|
| Repository structure | `frontend/`, `backend/`, `docs/`, `deploy/`, `.github/workflows/`, root Makefile and local-only Compose file | Foundation only; no operational modules |
| Recommended architecture assessment | [ADR-001](adr/0001-modular-monolith-stack.md), [overview](architecture/overview.md) | React/TypeScript/Vite/Tailwind, DRF, PostgreSQL, Redis/Celery, PWA and Actions selected; no deviation |
| Green/white responsive shell | `frontend/src/components/AppShell.tsx`, `LoginForm.tsx`, `styles.css` | No fictional business dashboard/data; one Overview route only; generic monogram is not an official school logo |
| Accessible states and reduced motion | Loading/error/form states, labels/landmarks/skip links, 44px-class targets, 320 CSS px minimum, reduced-motion CSS and frontend tests | WCAG 2.2 AA contrast/keyboard/screen-reader validation not fully executed |
| API versioning/health | `/api/v1/health/live/`, `/api/v1/health/ready/`, namespace versioning | Readiness checks PostgreSQL only; Redis/Celery not reported |
| Environment and logging | `config/settings/`, `.env.example`, request-ID middleware and JSON formatter | Production env has not been populated or deployed |
| Auth/RBAC foundation | Session + CSRF endpoints, custom User, dynamic role/permission/scope models, fail-closed permission service, audit append-only ORM guards | No user/role seed, role/grant management API, automated grant-change auditing, MFA, login throttling, DB trigger or approved school permission matrix |
| PostgreSQL data architecture | [Conceptual schema](architecture/data-architecture.md) | No migrations or business tables; no production DB connection |
| Quality checks | `.github/workflows/ci.yml`, frontend and backend tests, Ruff, mypy, PyYAML/TOML config validation | CI has not run on GitHub until PR checks execute |
| Architecture documentation | ADRs, module boundaries, threat model, data design, local setup, env reference and this traceability map | Some operational/policy details remain intentionally open |
| Railway-ready configuration | `deploy/*.Dockerfile`, `railway.toml`, `deploy/railway-web.toml`, Nginx proxy template | Templates only; not deployed, not validated against a Railway project |

## Scope exclusions preserved

No learner/candidate roster, grade policy, assessment/mocks, attendance, timetable, intervention, BECE analytics, reports, ranking, billing, payment capture, receipts, mock allowance payment, reconciliation, guardian portal, or business workflow is implemented. No school-specific classes, subjects, fees, grade bands, approval thresholds, financial accounts, or real data are invented. Future screens/integrations remain absent rather than advertised as live.

## Evidence gaps / blocked items

- **BLOCKED LOCALLY — PostgreSQL:** no local PostgreSQL client/service or Docker executable was available. Local tests use isolated in-memory SQLite; the PR CI backend job is configured for an ephemeral PostgreSQL 16 service, with its result pending until GitHub checks run.
- **BLOCKED — production migration review:** no migrations are included or run by design; Prompt 01 is limited to conceptual schema and identity model definitions.
- **NOT EXECUTED — WCAG 2.2 AA audit, assistive-technology pass, 320px physical-device test, performance/bandwidth test, threat-model workshop, backup/restore, UAT, Railway config against live Railway, and GitHub CI results.**
- **NOT APPROVED — actual school policies, names/signatures, roster, role-permission matrix, MFA/session policy, grade/ranking policy, fees/allowance schedules and payment providers.**

## Prompt 02 preconditions

Do not proceed without explicit Owner approval. Prompt 02 should begin with a read-only review of this PR and resulting CI/security findings, resolve the relevant P0 authority/policy decisions, approve the schema and migration strategy, define MFA and account provisioning, perform a threat-model/accessibility review, and specify tests/evidence/rollback before any next milestone.
