# Module boundaries

## Foundation modules implemented across Prompts 01–03

| Package | Owns | Explicitly does not own |
|---|---|---|
| `core` | API-version prefix, liveness/readiness endpoints, request ID, structured logging, cross-cutting HTTP defaults | Domain data, policy decisions, business calculations |
| `identity` | User model, data-defined role/permission and scope grants, append-only audit-event guards, encrypted TOTP and disabled-by-default recovery seams, policy-neutral maker-checker contract | School-specific role assignments, operational approval workflows, live recovery delivery, grant administration or future business records |
| `institutional` | Institution tenant boundary; versioned settings/releases; academic years/terms, levels/classes/streams, subject catalogue/offerings, effective-dated staff affiliations and teaching assignments, opaque enrolment placements; scoped APIs and audit evidence | User provisioning, role/permission grants, school calendars/policies, fees/rates, mock workflows, learner profiles or AIM module operations |
| `frontend` | Accessible role-aware foundation shell, session/CSRF sign-in, TOTP challenge/setup, recovery request/token form, same-origin no-store HTTP client, schema-driven institutional forms | Authorization truth, invented school data/rules, report/finance calculations, cached API data or an external recovery channel |

The Prompt 03 configuration workbench consumes server-authored schemas and server-side exact-scope API contracts. `user.permissions` only controls navigation/form visibility; it is never an authorization boundary. Staff affiliation is explicitly separate from RBAC.

## Planned modular-monolith boundaries — not implemented

AIM-01 through AIM-06 and later operational modules remain out of scope. Their approved names, semantics, field-level schemas, policy and activation gates must come from their own Owner-authorized work; this architecture does not infer them.

| Future domain | Possible ownership/integration boundary; not a delivered feature |
|---|---|
| Academic operations | Learner registry, approved attendance/timetable operations, assessment instances/results and moderation; may reference institution, release, year, class, subject offering and opaque learner UUID after separate review |
| Recovery / intervention | Topic gaps, case lifecycle, named ownership, session evidence, reassessment and escalation |
| Reporting / intelligence | Versioned templates, immutable snapshots, freshness/missingness contracts, approval, publication and analytics |
| Finance | Approved fee policy, invoice/receipt/ledger, payment evidence, allowances, expenditure and reconciliation |
| Integration | Carefully isolated import/export, notifications and later approved external providers |

No row above exists as an implemented AIM endpoint or workflow. The institutional placement record does not constitute a learner registry.

### Dependency rules

1. Business domains depend on identity and shared API contracts; identity must not import institutional or operational models.
2. `institutional` owns its configuration writes. Future domains consume stable IDs through explicit application services and must not mutate another module's records.
3. Shared PostgreSQL is a persistence boundary, not permission to join arbitrary domain tables from any view.
4. Cross-domain analytics must name source, period, numerator/denominator, missingness and policy version; no source-specific assumptions are copied into the UI.
5. Payment providers, WAEC, guardian messaging, LMS and other future services are explicit adapters behind separately approved feature gates; no simulated integration is shown as live.
6. Technical configuration and institutional policy are separate authority layers. Senior System Administrator is not automatically authorized to approve academic or finance policy.
7. Existing governance boundaries are recorded, not operationalized here: Headmaster approval for BECE mocks/related allowances; Local Manager and Secretary establishment of arrangements/rates (Local Manager is not the operational mock approver); Finance Director configuration of authorized rates; JHS Contact Person preparation; Finance processing of authorized payments. No rates, entitlements or workflow are encoded.
8. AIM and finance modules remain disabled until their separate design, policy, data, security and activation gates are satisfied.
