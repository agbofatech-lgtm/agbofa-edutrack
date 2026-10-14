# ADR 0007 — Phase 04 academic source and correction boundaries

**Status:** Proposed for Owner review (Phase 04 engineering implementation). No live-data or production approval.

## Context

The accepted institutional configuration provides approved year/class/offering/assignment references and opaque placements, but no learner source identity or academic result lifecycle. The explicit Phase 04 directive calls for candidates, BA-0, weekly assessments and Basic 9 mocks without inventing school policies or merging historical evidence. The complete Master Requirements v1.5 and 64-prompt roadmap were not available in this session.

## Decision

- `academic` owns Candidate and Guardian personal records and typed `CandidatePlacement` links to Phase 03 `Enrolment`; `institutional` continues to own its immutable configuration and effective-dated placement rows. Shared numeric IDs, client-side role claims and freeform JSON evidence are rejected in favor of typed FKs and scoped UUIDs.
- A candidate identity fingerprint is an HMAC of normalized name and optional birth date. It is a *possible-duplicate* guard, not proof of identity; reconciliation links duplicates without moving evidence. Identity changes, guardians and links preserve reasoned before/after evidence.
- Marks are an explicit sum of `scored` (including zero), `absent`, `missing` and `not_assessed`. A raw positive maximum comes from the authorized operator's subject blueprint; no grading, weighting, threshold, coverage inference or official WAEC data is embedded. BA-0 never claims coverage completeness without a separately approved policy.
- Submission/review/approval/publication are distinct transactional transitions. Approved records retain a source digest and cannot be edited; independently authorized correction creates a new draft successor with a source pointer. Audit metadata holds IDs/digests/counts; private before/after values remain in access-controlled domain tables.
- Exact institution/action RBAC and maker-checker are checked on the server. Monthly mock preparation, Headmaster approval and Basic 9 eligibility additionally require Owner-mapped role and level codes; empty mappings fail closed. A Local Manager is not an operational mock approver. No grants or policies are seeded.

## Consequences

This design supports source history and later separately approved analytical modules while avoiding grade/finance assumptions. Real-user role provisioning, field-level consent, DB-level immutability, HMAC secret rotation, migration/backfill, large-roster performance and offline private-data policy remain separate reviewed work. A digest is provenance evidence, not protection against a privileged database owner. This decision does not authorize shared/production migration, deployment, finance or Phase 05.
