# ADR-0003: Keep business schema and migrations out of Prompt 01

- **Status:** Accepted for Prompt 01
- **Date:** 2026-10-13

## Context

The supplied requirements document is a draft, has an Owner Gate for policy and schema approval, and lists missing institutional decisions. Prompt 01 asks for a documented initial PostgreSQL schema design, not all operational tables or workflows.

## Decision

Document the conceptual identity, school, academic, recovery, reporting, finance and governance entities, PostgreSQL integrity patterns and future boundaries. Create only initial technical identity/RBAC model definitions needed to demonstrate server-side authorization and authentication. Do not commit migrations, seed roles/policies, create learner/finance models, connect to a production database, or run production migrations.

## Consequences

- Future migration authors can alter model contracts after a field-level schema review.
- Test runner creates the unmigrated identity tables only in disposable test databases. A local dev schema, if needed, must be created explicitly in a local non-production database after review.
- Before any shared or production deployment, agree on a migration, backup, rollback/forward-fix and restore plan and produce a reviewed migration set.
