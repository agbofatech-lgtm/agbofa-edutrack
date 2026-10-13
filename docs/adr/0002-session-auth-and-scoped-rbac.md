# ADR-0002: Same-origin session authentication and server-side scoped RBAC

- **Status:** Accepted for the foundation; production use not approved
- **Date:** 2026-10-13

## Decision

Use Django's custom user model and password hashing, session authentication, HttpOnly session cookies, a CSRF-token endpoint, and CSRF-protected login/logout. Keep API requests same-origin through Vite/Nginx proxies. Do not expose public account creation or create default credentials.

Represent authorization with data-defined `AccessRole`, `AccessPermission`, `RolePermission` and effective-dated `ScopeGrant`. The `HasRBACPermission` service must fail closed without a permission contract and exact/global server-side grant. Global scope uses one explicit canonical grant. Superuser status is not treated as permission by this service. Audit events are append-only through the ordinary ORM and actor deletion is protected.

## Rationale

This is appropriate for a browser PWA served with its API on one origin, permits standard CSRF defense, avoids persistent client bearer tokens and supports scoped roles without hardcoding school job titles.

## Consequences and required follow-up

- Authentication does not imply business authorization; future endpoints must use both permission codes and record filters.
- The role/permission catalogue and scope hierarchy must be approved before any production account is assigned. No management endpoint exists; a future Owner-authorized service must audit grant and permission changes atomically before provisioning is exposed.
- Privileged MFA, lifecycle/provisioning, password recovery, throttling, device/session revocation, access reviews, DB-level audit immutability and database migrations remain open.
- ORM append-only guards are not a defense against direct SQL, database administrators, or a compromised application DB credential.
