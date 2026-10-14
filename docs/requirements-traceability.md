> **Historical Phase 01–03 document.** The full v1.5 Sections 1–37 and 64-prompt roadmap were not available in the Phase 04 session; the assertions below document earlier work, not fresh access to those source requirements. Phase 03 was subsequently accepted at `3e3058096b9a846c3134522e346ebf4e8eb8ffea`. For implemented Phase 04 scope and unresolved governance see [Phase 04 engineering report](prompt-04-candidate-academic-operations.md). No Phase 04 acceptance or production authorization is implied.

# Prompt 01–03 requirements traceability

**Baseline:** AGBOFA EduTrack Master Requirements v1.5, draft for Owner review, dated 13 October 2026. The pasted document retains v1.4/v1.3 headings in carry-forward sections; implementations preserve its stated precedence and unresolved Owner gates.

**Authority:** Prompt 01 established an engineering foundation. Prompt 02/12 was accepted by the Owner as an engineering foundation only; it did not approve production identity policy. Prompt 03 was separately authorized on the fixed Arena branch `arena/a3f38ba6-agbofa-edutrack` to implement institutional-configuration foundations, preserving Prompt 01/02. Prompt 03 acceptance remains for the Owner. No Prompt 04 or later work, shared/production migrations, live data access, merge to `main`, or deployment is authorized by this implementation.

| Deliverable | Implemented evidence | Limit / status |
|---|---|---|
| Foundation repository and architecture | `frontend/`, `backend/`, `docs/`, `deploy/`, `.github/workflows/`, root Makefile and local-only Compose; [architecture overview](architecture/overview.md) | Engineering foundation; no production deployment |
| Prompt 01/02 authentication, MFA, recovery safeguards, RBAC, audit and PWA | [Prompt 02 report](prompt-02-foundation-identity.md); identity, core and frontend tests | Prompt 02 accepted only as engineering foundation. Its open identity/security decisions remain unresolved |
| Institution tenant and scoped API | `backend/institutional/models.py`, `permissions.py`, `serializers.py`, `api/v1/views.py`, and versioned `/api/v1/` routes | No permission or role grants are seeded; each action remains server-enforced at exact scope |
| Versioned settings and releases | `ConfigurationRelease`, typed `InstitutionSetting`, release clone/submit/independent-approve/effective-release services, `0001_initial.py` | Effective date is explicitly supplied by the caller as institution-local; no timezone/calendar or policy is inferred. Approved history is immutable |
| Academic configuration | `AcademicYear`, `AcademicTerm`, `EducationalLevel`, `SchoolClass`, `Stream`, `Subject`, `SubjectOffering`, and `TeachingAssignment`; server-authored schema | User-entered values only; no academic calendar, class, subject, or stream is seeded |
| Staff and enrolment foundations | `InstitutionStaffMembership` distinct from RBAC; `Enrolment` with opaque registry UUID; effective-date checks and audit metadata | No staff accounts are provisioned and no roles are granted. Enrolment is not a learner profile and carries no learner name/contact/guardian data |
| Accessible dynamic configuration forms | `frontend/src/components/InstitutionConfiguration.tsx`, typed same-origin API client, server-authored field/resource schema, associated tests | Navigation/form visibility is not authorization; full WCAG 2.2 AA/assistive-technology audit remains unexecuted |
| Future AIM-01 through AIM-06 compatibility | Stable UUID institution/release/year/class/subject references and opaque learner reference; [data architecture](architecture/data-architecture.md) | No AIM module, learner registry, mock/assessment, reporting, intervention, finance or operational workflow is implemented |
| PostgreSQL schema/test isolation | Institutional initial migration; `config.settings.ci_postgres` is explicitly restricted to disposable CI PostgreSQL 16 | Migration is not authorized for or executed against shared/production databases; identity test tables retain existing CI-only creation behavior |
| Quality, CI and security controls | `.github/workflows/ci.yml`, backend/frontend checks, configuration validation, npm/pip audits and secret scanning | GitHub run on the Prompt 03 commit is the required PostgreSQL-backed evidence; previous Prompt 01/02 runs are historical only |

## Scope exclusions and preserved governance

No learner or guardian profile, BECE mock workflow, operational approval, allowance entitlement or payment, assessment result, attendance, timetable, intervention, report, billing, payment capture, receipt, reconciliation, general ledger, or provider integration is implemented. No school-specific classes, subjects, fees, rates, grade bands, approval thresholds, financial accounts, permission grants or real data are invented.

The future governance boundary is retained without implementation: the Headmaster approves BECE mocks and related allowances; the Local Manager and Secretary establish arrangements/rates, but the Local Manager is not operational mock approver; the Finance Director configures authorized rates; the JHS Contact Person prepares mocks; Finance processes authorized payments. No rates or entitlements are encoded, and maker-checker responsibilities remain subject to approved policy.

## Prompt 01/02 historical evidence

- Prompt 01 verified-baseline GitHub Actions run [#38392078479](https://github.com/agbofatech-lgtm/agbofa-edutrack/actions/runs/38392078479) passed on its verified baseline.
- Prompt 02 historical GitHub Actions run [#38397982478](https://github.com/agbofatech-lgtm/agbofa-edutrack/actions/runs/38397982478) passed frontend, backend and secret/dependency review; backend tests ran against disposable PostgreSQL 16.
- Prompt 02 latest-HEAD run [#38398168480](https://github.com/agbofatech-lgtm/agbofa-edutrack/actions/runs/38398168480) passed frontend, backend and secret/dependency jobs; dependency review was skipped because it was push-triggered.
- These are historical Prompt 01/02 checks, **not** Prompt 03 PostgreSQL migration evidence.

## Prompt 03 local verification and CI evidence

Local check results and the Prompt 03-specific GitHub Actions run are recorded in the [Prompt 03 implementation report](prompt-03-institutional-configuration.md). A PostgreSQL-backed Prompt 03 Actions run must pass after the implementation commit is pushed. Until then, the earlier PostgreSQL runs do not verify this change.

## Owner decisions and remaining gates

- Privileged school roles and MFA mapping; MFA enrollment/reset/lost-device policy, key custody and production secret-store ownership.
- Recovery identity proofing, permitted delivery channel/provider, verified contact, token lifetime/retention, support procedure and privileged-factor reset; recovery delivery stays disabled.
- Session lifetime, idle/absolute expiry, throttling, trusted proxy identity, shared cache and deployment policy.
- Role/permission/scope matrix, global-scope authority, account/grant provisioning, administrative review and atomic grant-change audit.
- Maker-checker authority, operational approvers, maker/processor separation and audit requirements. The generic configuration release checker does not approve future mocks or finance workflows.
- Institutional local-date/timezone/locale policy; academic calendar, term sequencing, class/subject catalogues and effective-date conventions.
- Production field-level schema/security review; migration ownership, rollback/forward-fix and backup/restore; audit retention and database-level immutability.
- Full WCAG 2.2 AA/assistive-technology assessment, independent security review/penetration test, browser/device/performance validation, UAT and production release authorization.

No decisions above are inferred from the presence of a form or permission code. The test suite uses synthetic fixtures and isolated disposable databases only.
