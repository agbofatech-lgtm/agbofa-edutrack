# Security foundation and residual threat model

## Security objectives

Protect learner/guardian and staff information, preserve academic/financial evidence, enforce record-level scope on the server, prevent unsafe privilege changes, and make status/errors honest. This Prompt 01 work establishes seams only; it is not a security certification or a production authorization.

## Trust boundaries

1. Browser UI is untrusted. Hidden navigation or a role claim in JavaScript cannot grant access.
2. Nginx/Vite is a same-origin reverse proxy. API authorization, input validation and record scoping remain in Django.
3. Django session cookies are HttpOnly, SameSite=Lax and Secure outside debug mode. CSRF tokens are obtained from a same-origin endpoint and sent in `X-CSRFToken` for writes.
4. PostgreSQL is the authoritative persistent store. Test-only SQLite is isolated to test settings.
5. Redis is a private cache/broker integration point. No business task, session cache, payment callback or user data cache is enabled in this foundation.
6. Environment secrets are never committed. Production fails closed when the secret key or database URL is missing; production settings also require hosts and Redis URL.

## Authentication and authorization controls

- Django's custom user model is chosen before domain data/migrations exist.
- Login uses Django password hashing/authentication, generic invalid-credential responses, CSRF-protected POST, session rotation, and logout invalidation.
- No default username/password, public sign-up, token in localStorage, or superuser bypass exists in `HasRBACPermission`.
- `AccessRole`, `AccessPermission`, `RolePermission`, and effective-dated `ScopeGrant` are the server-side authorization foundation. Role labels are data, not a hard-coded school roster.
- Scope helper denies when there is no active exact grant; global access requires an explicit canonical global grant. Future views must resolve scope from trusted service/view code and apply the corresponding scoped queryset before returning records.
- Minimal login/logout audit events are append-only through ordinary ORM save/update/delete paths; actor deletion is protected. Role, permission and scope-grant provisioning endpoints do not exist, and their changes are not automatically audited. Do not expose grant administration until an Owner-authorized management service records each change and its actor in the same transaction. A database role/trigger/retention strategy is still needed to protect audit evidence against direct SQL and privileged database actors.

## Input, errors and observability

The login serializer bounds input lengths; API defaults to JSON; readiness returns generic status without exposing connection details; request IDs are generated server-side and are not copied from attacker-controlled headers. Structured logs include time, severity, logger, message and request ID, not request bodies, passwords, cookies or tokens. Future domain writes must validate ownership, policy version and state transition server-side.

## Secrets and dependency controls

`.env`, `.env.*` (except `.env.example`), private keys, local databases, dependency directories and build outputs are ignored. The template contains empty secret fields. CI includes GitHub dependency review, `detect-secrets` source scanning, `npm audit`, and `pip-audit`. Production secrets and provider credentials must be entered only into an Owner-controlled secret store with rotation/access review.

## Threats, controls and open work

| Threat | Foundation mitigation | Residual work before exposure |
|---|---|---|
| Credential theft / session fixation | Django password hashing and login session rotation; HttpOnly session cookie | MFA for privileged accounts, password/reset policy, login throttling/lockout, session revocation and incident process |
| CSRF / cross-site requests | CSRF middleware, token endpoint, same-origin deployment, Lax cookies | Validate final domains and trusted origins; browser-level security test |
| Horizontal/vertical privilege escalation | RBAC query service and fail-closed scope contract | Approved matrix, comprehensive object-level negative tests for every future endpoint, periodic access review |
| Tampering with audit records | Append-only ORM manager/model, protected actor references | Database privileges/triggers, retention, immutable backup/log sink, privileged DBA threat model |
| Secret leakage | Environment-only settings, ignore rules, blank template fields, secret scan | External secret-store ownership, rotation, deployment permission review |
| Dependency compromise/vulnerability | Lockfile, version constraints, audit checks and PR dependency review | Pin/monitor Python transitive graph, SBOM, update cadence and production image scan |
| Data loss / malicious changes | PostgreSQL architecture only | Backup schedule, restore drills, point-in-time recovery, retention, monitoring; none is provisioned |
| Unsafe offline sync | Precaches static shell only; API data is network-only | Device-loss/conflict policy, cryptographic threat model and Owner approval before drafts |
| Unverified operational state | UI uses honest foundation text; no fabricated metrics | UAT with school data stewards after lawful/approved data onboarding |

## Explicit security limitations

No MFA, account provisioning flow, login rate limiting, email/SMS delivery, production TLS, database RLS, database immutability trigger, guardian consent, data retention policy, backup/restore, penetration test or independent threat assessment is completed. Do not deploy or import real data until these risks have Owner-approved treatment.
