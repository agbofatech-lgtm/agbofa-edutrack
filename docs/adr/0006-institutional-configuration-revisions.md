# ADR-0006: Institution-scoped, versioned configuration snapshots

- **Status:** Accepted for the Prompt 03 implementation, pending Owner acceptance of the implementation report
- **Date:** 2026-10-13
- **Scope:** Configuration foundations only; not a school-policy decision or production-migration approval

## Context

Prompt 03 requires institution-aware academic configuration, explicit effective dates, revision history, dependency validation, independent approval, audit evidence and dynamic accessible forms. Calendars, roles, school policies, rates, entitlements and operational approval rules remain unresolved and must not be inferred. Prompt 02 remains accepted only as an engineering foundation.

## Decision

1. Use an `Institution` UUID as the exact tenant boundary. An institution can be registered only through a distinct global creation permission; registration does not imply a subsequent read or management grant.
2. Store configuration as immutable-identity `ConfigurationRelease` revisions. An optional source approved release can be cloned. Versioned contents can be added, edited or deleted only while the release is draft; submit and approve are distinct, author self-approval is denied, and approved contents cannot be rewritten.
3. Serialize release-scoped writes against approval by locking the current release and institution rows and rechecking the current database status before saving. The approval service locks the release while validating all snapshot rows and changing state.
4. Resolve effective configuration only when a caller provides an explicit institution-local date. Do not infer the institution's timezone, locale, academic calendar or date convention. Those are future Owner decisions.
5. Keep the technical schema catalogue policy-neutral. User-entered values are validated by schema metadata and model constraints, but no real school values or policy defaults are seeded. Typed settings are not a secret store and credential-like keys/nested fields are rejected.
6. Keep staff affiliation separate from identity roles/grants. Store only minimal institution affiliation and effective dates; never let affiliation confer authorization.
7. Represent enrolment only as an opaque UUID reference plus placement fields. Do not create a learner profile or store learner/guardian attributes in this foundation.
8. Use server-authored form schemas and same-origin API contracts. The frontend can adjust visibility and assist users but never grants permission or bypasses server-side scope checks.
9. Record allow-listed audit events for release lifecycle, versioned record changes, staff affiliation and enrolment actions without request bodies, secrets or the opaque learner reference.
10. Commit an initial `institutional` migration for reproducible test/schema evolution, but do not execute it against shared or production infrastructure. CI may apply it only to its disposable PostgreSQL 16 test service.

## Consequences

- Future authorized AIM modules can reference stable institution/release/year/class/subject UUIDs, staff affiliations and the opaque learner reference without coupling to an operational workflow.
- Full migration governance, production schema review, rollback/forward-fix, backup/restore, audit retention and database-level immutability remain Owner/security gates.
- School calendars, permissions, assignment policies, finance rates, mock approvals and payment processing remain absent. Governance roles and policies are not hardcoded.
- Prompt 03 implementation and its CI evidence do not constitute Owner acceptance, a policy approval, deployment authorization or permission to begin later prompts.
