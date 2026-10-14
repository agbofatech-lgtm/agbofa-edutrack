# Module boundaries — Phases 01–04

| Package | Owns now | Does **not** own |
|---|---|---|
| `core` | Versioned API prefix, liveness/readiness, request IDs, structured logging, HTTP security defaults | Domain data, school policy or grading |
| `identity` | Session/CSRF and privileged MFA; users, data-defined roles/permissions/scopes; audit allow-list; disabled-by-default recovery; maker-checker primitive | School role assignments, Guardian login, live recovery delivery, grant administration, academic or finance source records |
| `institutional` | Institution tenant and approved versioned releases; years/terms/levels/classes/streams; subject offerings; staff affiliations/teaching assignments; opaque enrolment effective dates | Candidate names/guardian records, grades, roles, mock workflows, finance rules |
| `academic` | Typed Candidate-to-Enrolment link, candidate/guardian source data, controlled import, BA-0 observations, weekly assessments, Basic 9 monthly mock source records, review/correction/audit lifecycles | Editing an approved institutional release; official WAEC data, school scoring rules, attendance/interventions, guardian messaging, predictions, allowances/payments |
| `frontend` | Accessible institution-scoped forms and authenticated academic workspace; same-origin no-store client; public-shell-only PWA | Authorization truth, invented school records/rules, cached API/private offline drafts, analytics or finance calculations |

`academic` reads approved `institutional` FKs and placement periods but does not mutate institutional configuration; subsequent placement creation writes a Phase 03 `Enrolment` inside a scoped academic service transaction. Closing an open enrolment remains separately authorized by the Phase 03 endpoint. Staff affiliation is not RBAC. Session permission identifiers and `context.permissions` inform UI visibility but never authorize a server operation. The complete Master Requirements v1.5 and 64-prompt roadmap were unavailable during Phase 04; see [the engineering report](../prompt-04-candidate-academic-operations.md).

## Future, not implemented

| Future domain | Possible integration boundary; not a delivered Phase 04 feature |
|---|---|
| Academic follow-on | Attendance, timetable, classroom progression policies, grading, exam registration, interventions and official outcomes |
| Reporting / intelligence | Reviewed analytics with source/period/numerator/denominator, missingness and published snapshots |
| Finance | Owner-approved fee policy, invoice/receipt/ledger/payment evidence, allowances, expenditure and reconciliation |
| Integration | Approved data import/export standards, notifications, WAEC or payment providers |

1. Business domains depend on identity and approved institutional contracts; identity does not import academic models.
2. Each domain owns its writes; shared PostgreSQL does not permit arbitrary data joins or cross-institution access. Explicit service transactions own the narrowly defined CandidatePlacement/Enrolment link.
3. Cross-domain analytics must identify source, period, missingness, policy version and denominator before any interpretation. No Phase 04 raw mark is an official prediction.
4. External services are adapters behind separately authorized policy and security gates, not simulated active integrations.
5. Technical configuration is not school policy. Headmaster—not Local Manager—is the operational BECE mock approver; JHS Contact Person preparation, any mock allowance/finance arrangement, and payment remain **separate** governance responsibilities. Nothing here calculates or disburses an allowance.
