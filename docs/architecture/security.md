# Security foundation and residual threat model

## Security objectives

Protect learner/guardian and staff information, preserve academic/financial evidence, enforce record-level scope on the server, prevent unsafe privilege changes, and make status/errors honest. Phases 01–04 establish tested engineering, configuration and academic source foundations only; this is not a security certification or production authorization.

## Trust boundaries

1. Browser UI is untrusted. Hidden navigation or a role claim in JavaScript cannot grant access.
2. Nginx/Vite is a same-origin reverse proxy. API authorization, input validation and record scoping remain in Django.
3. Django session cookies are HttpOnly, SameSite=Lax and Secure outside debug mode. CSRF tokens are obtained from a same-origin endpoint and sent in `X-CSRFToken` for writes.
4. PostgreSQL is the authoritative persistent store. Test-only SQLite is isolated to test settings.
5. Redis is a private cache/broker integration point. No business task, session cache, payment callback or user data cache is enabled in this foundation.
6. Environment secrets are never committed. Production fails closed when the secret key or database URL is missing; production settings also require hosts and Redis URL.

## Authentication and authorization controls

- Django's custom user model is chosen before domain data/migrations exist.
- Login uses Django password hashing/authentication, identical generic credential failures for known/unknown users, CSRF-protected POST, session-key rotation, and logout invalidation. Session expiry is sent by the server, shown in the shell, and handled by browser timers plus refresh/focus checks.
- Django `is_staff` and `is_superuser` accounts are required to enroll and complete RFC 6238 TOTP before obtaining an authenticated session. TOTP seeds are encrypted at rest with AES-256-GCM under a separate `MFA_ENCRYPTION_KEY`; codes are time-window checked and each counter can be used once. The key is required at use time and fails closed if missing or invalid.
- Recovery uses high-entropy, single-use tokens stored only as SHA-256 digests and password reset invalidates existing Django sessions. Delivery is disabled by default; no email/SMS provider, verified recovery contact, or delivery credentials are included. A configured adapter must be explicitly Owner-approved.
- Login, MFA, and recovery requests are rate-throttled using configurable DRF scopes. Defaults are provisional and IP-based; reverse-proxy client identity and shared-cache behavior require validation before exposure.
- No default username/password, public sign-up, token in localStorage, or superuser bypass exists in `HasRBACPermission`.
- `AccessRole`, `AccessPermission`, `RolePermission`, and effective-dated `ScopeGrant` remain the server-side authorization foundation. Active role labels and permission codes returned in the session are derived from the database; they are UI hints, not authority. No school roles, permissions, or scope hierarchy are seeded.
- Scope helpers deny when there is no active exact grant; global access requires an explicit canonical global grant. Institutional API views derive the scope only from the route institution UUID and filter release/resource objects by institution and revision. Phase 04 candidate/profile, BA-0 and weekly/mock endpoints are separately scoped and source-only. Attendance, analytic reporting, interventions and finance endpoints are not registered.
- Institution creation is separately gated by a global permission; registration does not grant a scoped read. Configuration resources are editable only in drafts. Versioned writes lock the release and institution rows while checking current release state, serializing ordinary API writes with approval. The service requires an explicit institution-local date for effective-release resolution; it does not infer timezone/locale.
- Staff affiliations and enrolments have separate permission codes and exact institution scope. Affiliation does not grant roles. Enrolment contains an opaque UUID and placement references only, not learner profile fields. Resource updates are restricted to the intended date-close action for memberships/enrolments, with before/after end-date audit metadata.
- Login, logout, MFA setup/verification, recovery request/completion, configuration release, versioned record, staff-membership and enrolment audit actions are allow-listed. The service rejects sensitive audit metadata keys, and the model blocks ordinary ORM update/delete paths; raw SQL, bulk creation, administrators, DB compromise and retention are not controlled by this layer.
- A policy-neutral maker-checker interface requires a distinct actor, an exact scoped permission and an explicit policy callback; release approval uses that interface and rejects the author. It does not define school roles or approval authorities. Role/grant provisioning endpoints and automated grant-change auditing remain absent; an Owner-approved management service must audit grant changes atomically before provisioning is exposed.

## Input, errors and observability

The login serializer bounds input lengths; API defaults to JSON; readiness returns generic status without exposing connection details; request IDs are generated server-side and are not copied from attacker-controlled headers. Structured logs include time, severity, logger, message and request ID, not request bodies, passwords, cookies or tokens. Institutional serializers constrain related-object querysets to the route institution/revision; Phase 04 academic serializers also bound rows and refuse unknown fields. Models/services validate dates, approved configuration dependencies, score states, exact institution scope, optimistic versions, review-state transitions and append-only evidence. Future domain writes still need their own policy, ownership and state-transition validation.

## Secrets and dependency controls

`.env`, `.env.*` (except `.env.example`), private keys, local databases, dependency directories and build outputs are ignored. The template contains empty secret fields. CI includes GitHub dependency review, `detect-secrets` source scanning, `npm audit`, and `pip-audit`. Production secrets and provider credentials must be entered only into an Owner-controlled secret store with rotation/access review.

## Threats, controls and open work

| Threat | Foundation mitigation | Residual work before exposure |
|---|---|---|
| Credential theft / session fixation | Django password hashing, generic failures, session rotation/expiry, throttles, HttpOnly cookie, TOTP for Django platform admins | Owner approval of which school identities are privileged, session/throttle policy, factor reset, independent review and incident process |
| CSRF / cross-site requests | CSRF middleware, token endpoint, protected state-changing authentication endpoints, same-origin deployment, Lax cookies | Validate final domains and trusted origins; browser-level security test |
| Recovery-token theft / account enumeration | Generic responses; high-entropy single-use tokens stored as digests; disabled-by-default delivery seam; no recovery contact disclosed | Approve identity proofing, delivery channel, token lifetime, retention, recovery support and privileged-factor reset; configure no provider until approved |
| TOTP seed/code compromise | AES-GCM encrypted seed with separate key, short pre-auth session, replay prevention, CSRF and throttling | Owner key custody/rotation, TOTP enrollment policy, lost-device process and deployment key provisioning |
| Horizontal/vertical privilege escalation | RBAC query service and fail-closed scope contract | Approved matrix, comprehensive object-level negative tests for every future endpoint, periodic access review |
| Tampering with audit records | Action-allow-listed service, sensitive metadata rejection, append-only ORM manager/model, protected actor references | Database privileges/triggers, retention, immutable backup/log sink, privileged DBA threat model, and grant-change audit process |
| Secret leakage | Environment-only settings, ignore rules, blank template fields, secret scan | External secret-store ownership, rotation, deployment permission review |
| Dependency compromise/vulnerability | Lockfile, version constraints, audit checks and PR dependency review | Pin/monitor Python transitive graph, SBOM, update cadence and production image scan |
| Data loss / malicious changes | PostgreSQL architecture only | Backup schedule, restore drills, point-in-time recovery, retention, monitoring; none is provisioned |
| Unsafe offline sync | Static-shell precache only, no Workbox runtime routes, API navigation denied from fallback, no-store fetch/response directives, no private browser storage | Device-loss/conflict policy, cryptographic threat model and Owner approval before any draft/offline workflow |
| Unverified operational state | UI uses honest foundation text; no fabricated metrics | UAT with school data stewards after lawful/approved data onboarding |

## Explicit security limitations

No school-specific privileged-role matrix, account provisioning flow, verified recovery channel, MFA factor reset, production TLS validation, database RLS/audit-immutability trigger, grant-management API, audit retention policy, guardian consent, backup/restore, independent penetration test, full WCAG 2.2 AA audit or threat-model workshop is completed. The institutional and academic initial migrations are present for testable schema evolution only; neither has been run against shared/production data or received a production migration review. The current 8-hour/browser-close session policy, TOTP defaults, MFA setup lifetime and rate limits are technical defaults pending Owner approval. Do not deploy or import real data until the open decisions and schema/migration plan have an approved treatment.

## Phase 04 academic threat additions

- Candidate/guardian names and contact are restricted by institution and action codes. Guardian link/profile contact is masked when inactive or unauthorized; the separate guardian directory is an administrative permission and **not** a contact-consent mechanism. Candidate 360° and candidate-filtered activities strip peer participants, marks and quality; restricted/unimplemented sections are labeled. Academic responses explicitly carry no-store/private cache directives. Static PWA precache never stores API paths.
- Bulk CSV preview is actor/key/payload bound, validates identities and placement dependencies, and commits all-or-nothing under an institution lock. Stale versions produce 409 for draft, mark and roster changes. Server-side maker-checker rejects self-approval or a mark editor checking the same record. Approved source snapshots are immutable under ordinary ORM operations and correction creates a distinct successor. Audit metadata excludes PII, raw marks, source labels and correction reasons.
- Mock role codes and Basic 9 level mapping are **empty by default**. Only exact institution JHS Contact Person and Headmaster grants can activate the separately scoped actions, and Headmaster approval/publication requires privileged MFA. No Local Manager fallback exists. A global level-code mapping may not fit institutions with different approved codes; no mapping should be activated without explicit multi-tenant governance.
- Residual risks include raw SQL/DB-owner alteration, unapproved role provisioning, guardian consent/retention, HMAC key rotation and identity collision review, large-roster response/performance and concurrency testing, DB migration/backfill, backup/restore and independent penetration/WCAG audit. Passing synthetic tests is **not** a legal basis for importing real pupil records.
