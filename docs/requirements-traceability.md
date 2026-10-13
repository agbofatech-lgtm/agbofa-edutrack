# Prompt 01 requirements traceability

**Baseline:** AGBOFA EduTrack Master Requirements v1.5, draft for Owner review, dated 13 October 2026. The pasted document retains v1.4/v1.3 headings in carry-forward sections; this implementation treats the supplied v1.5 sections and their stated precedence as the baseline.

**Authority:** The original Prompt 01 work was authorized only as an engineering foundation. The Owner subsequently authorized Prompt 02/12 — Foundation and Identity on the Arena-assigned branch from verified Prompt 01 commit `cf3b69ebfa711c8be88e135afb2b956c4703fe8b`. That scope authorizes independently testable identity/PWA foundations only. It does not approve business modules, production/shared migrations, live data, payment services, Railway resources/deployment, school-specific policies, or Prompt 03.

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
| Quality checks | `.github/workflows/ci.yml`, frontend and backend tests, Ruff, mypy, PyYAML/TOML config validation | Prompt 01 run [#38392078479](https://github.com/agbofatech-lgtm/agbofa-edutrack/actions/runs/38392078479) passed on the verified baseline |
| Architecture documentation | ADRs, module boundaries, threat model, data design, local setup, env reference and this traceability map | Some operational/policy details remain intentionally open |
| Railway-ready configuration | `deploy/*.Dockerfile`, `railway.toml`, `deploy/railway-web.toml`, Nginx proxy template | Templates only; not deployed, not validated against a Railway project |

## Scope exclusions preserved

No learner/candidate roster, grade policy, assessment/mocks, attendance, timetable, intervention, BECE analytics, reports, ranking, billing, payment capture, receipts, mock allowance payment, reconciliation, guardian portal, or business workflow is implemented. No school-specific classes, subjects, fees, grade bands, approval thresholds, financial accounts, or real data are invented. Future screens/integrations remain absent rather than advertised as live.

## Prompt 01 evidence gaps / blocked items

- **BLOCKED LOCALLY — PostgreSQL:** no local PostgreSQL client/service or Docker executable was available. Local Prompt 01 tests used isolated in-memory SQLite; the verified-baseline GitHub run passed against its disposable PostgreSQL 16 service.
- **BLOCKED — production migration review:** no migrations were included or run by design; no production/shared database was contacted.
- **NOT EXECUTED — WCAG 2.2 AA audit, assistive-technology pass, 320px physical-device test, performance/bandwidth test, threat-model workshop, backup/restore, UAT, and Railway config against a live Railway project.**
- **NOT APPROVED — actual school policies, roster, role-permission matrix, MFA/session policy, grade/ranking policy, fees/allowance schedules and payment providers.**

## Prompt 02/12 — Foundation and Identity

**Authorization:** Owner authorized Prompt 02 implementation on the Arena-assigned branch `arena/a3f38ba6-agbofa-edutrack`, from baseline `cf3b69ebfa711c8be88e135afb2b956c4703fe8b`. The authorization is limited to testable identity/PWA foundations; it is not an acceptance of school policies or production use.

**Implemented evidence:** see [Prompt 02 Foundation and Identity report](prompt-02-foundation-identity.md) and [successful Prompt 02 GitHub Actions run 38397982478](https://github.com/agbofatech-lgtm/agbofa-edutrack/actions/runs/38397982478). Work preserves Prompt 01 session/CSRF, custom user, dynamic scoped RBAC, ORM-append-only audit, static-shell PWA and generic navigation. Prompt 02 adds generic session-expiry handling, provisional throttles, TOTP MFA for Django platform admin flags, encrypted TOTP seeds, disabled-by-default recovery delivery interface, hashed single-use recovery tokens, policy-neutral maker-checker contract, role-informed shell, no-store API handling, and tests.

**Schema boundary:** `MfaCredential` and `AccountRecoveryToken` are identity security model definitions only. There are no committed migrations; CI may create their tables only inside its disposable PostgreSQL test service. No shared/production migration, seed, data import or deployment is authorized.

**Owner decisions still required:** privileged school roles beyond Django platform-admin flags; approved recovery channel and identity-proofing process; MFA enrollment/reset/backup policy and secret-key custody; session duration and rate limits/trusted proxy identity; approved role/permission/scope matrix; maker-checker policy; field-level schema/migration/rollback and audit retention/DB immutability; full accessibility and security review. Until these decisions are made, no external recovery adapter, production migration, business endpoint or deployment may be enabled.
