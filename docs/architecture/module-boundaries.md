# Module boundaries

## Foundation modules implemented in Prompt 01

| Package | Owns | Explicitly does not own |
|---|---|---|
| `core` | API-version prefix, liveness/readiness endpoints, request ID, structured logging, cross-cutting HTTP defaults | Domain data, policy decisions, business calculations |
| `identity` | User model, data-defined role/permission and scope grants, append-only audit-event API guard, encrypted TOTP and disabled-by-default recovery service seams, policy-neutral maker-checker contract | Institutional role assignments, school policy approvals, live recovery delivery, login provisioning, business approval workflows or business-record tables |
| `frontend` | Accessible role-aware foundation shell, session/CSRF sign-in, TOTP challenge/setup, recovery request/token form, generic loading/error/success states, same-origin no-store HTTP client | Authorization truth, school data, report/finance calculations, cached API data or an external recovery channel |

The Prompt 02 shell displays active role labels supplied by the identity service and exposes only foundation pages. There is no approved school permission matrix or business route catalog, so no school-operation navigation is seeded. UI visibility is not server authorization.

## Planned modular-monolith boundaries (not implemented)

| Domain | Future ownership and integration boundary |
|---|---|
| Identity / governance | Accounts, permission catalog, scoped grants, delegation, controlled configuration, feature lifecycle, audit evidence |
| Academic structure | School identity, academic years/terms, levels/classes/streams/subjects and effective-dated assignments |
| Assessment | Schemes, versions, assessment instances, marks, absence-vs-zero, moderation and approvals |
| Attendance / teaching evidence | Scheduled sessions, learner attendance, teacher check-in, independently verified lesson delivery |
| Recovery / intervention | Topic gaps, case lifecycle, named ownership, session evidence, reassessment and escalation |
| Reporting / intelligence | Versioned templates, immutable snapshots, freshness/missingness contracts, approval, publication and analytics |
| Finance | Approved fee policy, invoice/receipt/ledger, payment evidence, allowances, expenditure and reconciliation |
| Integration | Carefully isolated import/export, notifications and later approved external providers |

### Dependency rules

1. Business domains depend on identity and shared API contracts; identity must not import business domain models.
2. A domain owns writes to its records. Cross-domain operations use explicit application services and transactions, not hidden model signals.
3. Shared PostgreSQL is a persistence boundary, not permission to join arbitrary domain tables from any view.
4. Cross-domain analytics must name source, period, numerator/denominator, missingness and policy version; no source-specific assumptions are copied into the UI.
5. Payment providers, WAEC, guardian messaging, LMS and other future services are explicit adapters behind feature gates; no simulated integration is shown as live.
6. Technical configuration and institutional policy are separate authority layers. Senior System Administrator is not automatically authorized to approve academic or finance policy.
7. Academic and finance modules remain disabled until their separate design/policy/activation gates are satisfied.
