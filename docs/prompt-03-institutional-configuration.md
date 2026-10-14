# Prompt 03 — Institutional Configuration Implementation Report

> **Historical report.** Its pending-acceptance and CI statements describe the state when this report was written; the Owner subsequently accepted Phase 03 at `3e3058096b9a846c3134522e346ebf4e8eb8ffea` with historical Actions run `38445876874`. Phase 04 is on this session's fixed `arena/08c6c981-agbofa-edutrack` branch, not on the branch named below. See [Phase 04 report](prompt-04-candidate-academic-operations.md).

**Status:** Engineering implementation and local verification are complete; PostgreSQL-backed GitHub Actions evidence is pending after the authorized branch push. Owner acceptance has not been granted. This is not production authorization.

**Authorized branch:** `arena/a3f38ba6-agbofa-edutrack` (fixed for this Arena session)

**Session base:** `d74844381523af9d554d1072dfb0d43f463b348c`

**Scope:** Prompt 03 only. Prompt 01/02 identity, privileged MFA, recovery safeguards, RBAC, audit, PWA safety and CI are preserved. No merge to `main`, production deployment/migration, live-data access, Prompt 04+, or automatic advancement is included.

## Delivered

### Institution-aware versioned configuration

- Added the `institutional` Django app, `0001_initial` migration and `/api/v1/` endpoints for scoped institution reads/registration, schemas, release lifecycle, versioned resources, staff memberships and opaque enrolment placements.
- Added release revisions with immutable identity/effective date, optional cloning from an approved revision, draft-only content writes, validated submission, distinct independent approval and immutable approved history. Release/resource writes serialize on the current release/institution rows; the effective-release resolver requires an explicit institution-local date.
- Added typed, versioned institutional settings; academic year/term; educational levels, classes/streams; subjects and class/term/stream offerings; effective-dated teaching assignments; staff affiliation; and enrolment foundation.
- Enforced institution/revision dependency checks, date ordering, resource-specific RBAC, exact institution scope, read/manage permission boundaries and allow-listed audit events. Institution creation requires a separate global grant and does not implicitly grant subsequent access.
- Staff affiliation remains separate from roles/permissions. Enrolment carries only an opaque learner-registry UUID and placement references—no learner profile, names, contact or guardian data. Membership/enrolment API updates can only close an open effective period and audit before/after dates.
- No permission grants, calendar, classes, streams, subjects, policy values, rates, fees, entitlements, or records are seeded. Timezone and locale were removed from the unversioned institution row; date resolution does not infer them.

### Accessible configuration workbench

- Added a permission-informed application-shell entry, server-authored resource/field metadata, accessible labelled and keyboard-operable dynamic controls, relation selectors, typed setting values, release creation/submission/approval, draft edits and end-date-only membership/enrolment closure.
- The client uses same-origin no-store API calls, CSRF for writes, and permission metadata only to inform visibility. All authorization remains server-side. Existing PWA static-shell-only cache rules remain unchanged.

### AIM-01 through AIM-06 compatibility boundary

Stable UUID institution/release/calendar/class/subject references, staff affiliations/teaching assignments and an opaque learner reference are available for future separately authorized work. No AIM module, learner registry, assessment/mock, attendance, intervention, report, finance, allowance, payment or operational approval workflow is implemented.

The governance boundary remains explicit and unencoded: the Headmaster approves BECE mocks and related allowances; the Local Manager and Secretary establish arrangements/rates, but the Local Manager is not mock approver; the Finance Director configures authorized rates; the JHS Contact Person prepares mocks; Finance processes authorized payments. No financial rates or entitlements are included.

## Local verification evidence

| Check | Result |
|---|---|
| Django migration consistency (`makemigrations --check --dry-run`) | Passed — no model/migration drift |
| Django system check | Passed — no issues |
| Backend tests | **45 passed** using isolated in-memory SQLite and synthetic fixtures |
| Ruff lint and format | Passed — all backend files clean/formatted |
| mypy | Passed — no issues in 49 source files, including `institutional` |
| Frontend typecheck | Passed |
| ESLint | Passed |
| Prettier format check | Passed |
| Frontend tests | **21 passed** across 11 test files, including dynamic academic-year form submission and restricted membership closure form |
| Production frontend build | Passed; static PWA assets generated |
| npm audit (`--audit-level=high`) | Passed — **0 vulnerabilities** |
| pip-audit | Passed — **no known vulnerabilities** |
| Configuration validation | Passed — CI YAML/action pins, Compose, Railway templates, shell, environment template and npm lock structurally valid |

These local checks use synthetic data and disposable databases only. They do not constitute PostgreSQL CI verification, an accessibility certification, production security review, or owner acceptance.

## PostgreSQL CI evidence

**Pending.** The Prompt 03 GitHub Actions run must execute after this branch is pushed. The backend workflow is configured for `config.settings.ci_postgres` and a disposable PostgreSQL 16 service; this will exercise the institutional migration and backend suite without contacting a shared/production database. Earlier Prompt 01/02 runs are historical and are not evidence for Prompt 03.

## Security findings and limitations

- Tenant identity comes from the route and every resource is filtered/validated against that institution and (where versioned) release. Negative cross-tenant API coverage is included.
- Draft contents are checked against current database release state under row locks before ordinary model writes; review actions have an independent checker boundary. Staff affiliation does not grant RBAC. Enrollment audit metadata excludes the opaque learner reference.
- Settings reject secret-like keys/nested fields; no credentials are stored in institutional settings. No live personal or financial data was loaded or processed.
- Ordinary ORM guards are not database-level immutability: raw SQL, bulk operations, database owners/compromise and retention remain residual risks. Grant-management APIs and automated grant-change audit remain absent. Exact permission assignments have not been approved or seeded.
- The initial institutional migration is committed as schema source and exercised in disposable test/CI databases only. It has not been run against shared/production infrastructure. No deployment or Railway project was changed.
- Full WCAG 2.2 AA/assistive-technology validation, penetration testing, production TLS/secret-store review, concurrency testing against a real service, performance testing, backup/restore and UAT remain incomplete.

## Unresolved approvals and governance blockers

Prompt 03 does not approve or resolve Prompt 02 decisions: MFA role mapping; recovery proofing/provider/lifetime and factor reset; role/scope matrix; session/rate/trusted-proxy policy; maker-checker authority; audit retention/DB immutability; production security. It also does not determine school calendars, local-date/timezone/locale semantics, class/subject values, operational mock authorities, rates, financial rules or payment workflows. Those decisions require the appropriate Owner/governance approvals before use.

## Owner Acceptance Gate

**Decision: PENDING — not accepted by this report.** Review the implementation and CI evidence, then accept or request changes. This report is the stopping point: no merge, deployment, production migration, live-data activity or next prompt will occur without the Owner's explicit decision.
