# Conceptual PostgreSQL data architecture — proposed, not migrated

This document maps the Master Requirements v1.5 concepts into a future relational design. It is not an approved field-level schema, a migration plan, or evidence of existing school records. The concrete model definitions are limited to technical identity/RBAC, append-only audit, encrypted TOTP credential, and hashed one-time recovery-token primitives. No migration is committed and no learner or finance tables exist; CI creates unmigrated tables only in a disposable test database.

## Proposed entity groups

```mermaid
erDiagram
    USER ||--o{ SCOPE_GRANT : receives
    USER ||--o{ AUDIT_EVENT : performs
    ROLE ||--o{ SCOPE_GRANT : grants
    ROLE ||--o{ ROLE_PERMISSION : includes
    PERMISSION ||--o{ ROLE_PERMISSION : names
    SCHOOL ||--o{ ACADEMIC_YEAR : configures
    ACADEMIC_YEAR ||--o{ TERM : contains
    LEVEL ||--o{ CLASS : organizes
    CLASS ||--o{ ENROLMENT : hosts
    LEARNER ||--o{ ENROLMENT : participates
    LEARNER ||--o{ ASSESSMENT_RESULT : earns
    ASSESSMENT ||--o{ ASSESSMENT_RESULT : records
    LEARNER ||--o{ INTERVENTION_CASE : receives
    REPORT_TEMPLATE_VERSION ||--o{ REPORT_SNAPSHOT : renders
    LEARNER ||--o{ REPORT_SNAPSHOT : represented_by
    LEARNER ||--o{ INVOICE : billed_by
    INVOICE ||--o{ INVOICE_LINE : itemizes
    PAYMENT ||--o{ PAYMENT_ALLOCATION : allocates
    INVOICE ||--o{ PAYMENT_ALLOCATION : receives
    PAYMENT ||--o{ RECEIPT : evidences
    JOURNAL_ENTRY ||--o{ JOURNAL_LINE : posts
    ACCOUNT ||--o{ JOURNAL_LINE : classifies
```

### Identity / governance

`User`, `Role`, `Permission`, `RolePermission`, `ScopeGrant`, `ApprovalDelegation`, `AuditEvent`, `ConfigDefinition`, `ConfigVersion`, `ChangeRequest`, `ImpactReview`, `Approval`, `FeatureFlag`.

The code defines `User`, `AccessRole`, `AccessPermission`, `RolePermission`, `ScopeGrant`, `AuditEvent`, `MfaCredential`, and `AccountRecoveryToken`. MFA ciphertext and recovery token digests are technical security fields; no raw recovery token is stored. No sample roles/permissions are seeded. A school-approved role-permission matrix and record-scope vocabulary are prerequisites to assigning real grants. Field-level schema/migration review remains required before any shared or production use.

### School / academic foundation

`School`, `AcademicYear`, `Term`, `Level`, `Class`, `Stream`, `Subject`, `StaffProfile`, `TeacherAssignment`, `Learner`, `GuardianLink`, `Enrolment`. Staff profiles and school accounts are related but distinct identities. These must support the whole-school Nursery–Basic 9 record hierarchy from the outset even if operational activation initially targets Basic 7–9. Use stable internal identifiers; never encode school-specific names or classes as application code.

### Academic / recovery / reporting

`AssessmentSchemeVersion`, `Assessment`, `Mark`, `Moderation`, `MockExamination`, `MockCandidate`, `MockItem`, `Lesson`, `TimetableSlot`, `AttendanceRecord`, `InterventionPlan`, `TopicGap`, `Alert`, `ReportTemplateVersion`, `ReportSnapshot`, `PublicationEvent`, `Signatory`.

Academic policy, assessment comparability, missingness, grades/ranking, template components and effective periods must be reviewed before fields and constraints are frozen.

### Finance (core scope, independently gated activation)

`FeePolicyVersion`, `FeeSchedule`, `Invoice`, `InvoiceLine`, `Payment`, `Allocation`, `Credit`, `Receipt`, `ConcessionAward`, `ExpenseRequest`, `Account`, `JournalEntry`, `JournalLine`, `Reconciliation`, `ClosePeriod`, `MockAllowancePolicyVersion`, `MockAllowanceEntitlement`, and `DisbursementEvidence`.

Mock allowance entitlements must preserve the established rate version, beneficiary, approved mock, eligibility evidence, Headmaster approval (including own-beneficiary transparency), Accounts processing, and actual payment state; approval alone must not auto-disburse.

Amounts should use fixed-precision `NUMERIC`, not floating point. Issued invoices, receipts and posted journals must preserve a policy/template snapshot and immutable source references. Corrections should be reversals/credit notes, never deletion. Provider callback/idempotency and maker-checker rules need an approved financial design before implementation.

## PostgreSQL design controls for the next schema gate

- Primary keys: UUIDs for externally addressable domain records; internal sequence keys may be selected for high-volume internal joins after review.
- Dates/times: `timestamptz`, UTC storage, explicit academic local-date policy; distinguish effective periods from record-created time.
- Integrity: foreign keys, unique idempotency keys, check constraints, exclusion/overlap constraints where justified, and indexes aligned to scope-filtered queries.
- History: policy/template versions, audit events, publication snapshots and ledger entries are append-only; updates should create revisions or reversing events.
- Record scoping: design each domain's ownership key and permitted scope hierarchy with row-access service contracts. Never rely on opaque frontend filters or a global role label.
- Privacy: minimize copied identity/guardian attributes, define consent/retention/export/deletion rules, and avoid broad analytics replicas before review.
- Operations: migrations must be reviewed, tested against representative anonymized fixtures, backed up, reversible or forward-fixable, and approved before production execution.

## Explicit non-deliverables

No learner, guardian, class, subject, assessment, attendance, intervention, report, invoice, payment, receipt, account, ledger, expenditure, reconciliation or provider schema/migration is included here. No production database was contacted.
