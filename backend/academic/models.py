"""Institution-scoped academic source records; no school-specific policy is seeded.

Approved snapshots and evidence are protected from ordinary ORM mutation. Database
owners, direct SQL and custom managers outside these guards remain a separate
production governance concern. No personal data belongs in identity audit metadata.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone

from institutional.models import (
    AcademicYear,
    Enrolment,
    Institution,
    SchoolClass,
    Stream,
    SubjectOffering,
    TeachingAssignment,
)


class NoBulkMutationQuerySet(models.QuerySet):
    def update(self, **kwargs: object) -> int:
        raise ValidationError("Academic records cannot be bulk-updated.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("Academic records cannot be bulk-deleted.")

    def bulk_create(self, objs: Any, *args: Any, **kwargs: Any) -> Any:
        raise ValidationError(
            "Academic records cannot bypass model validation with bulk inserts."
        )

    def bulk_update(self, objs: Any, fields: Any, *args: Any, **kwargs: Any) -> Any:
        raise ValidationError("Academic records cannot be bulk-updated.")


class AppendOnlyEvidence(models.Model):
    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ValidationError("Historical evidence is append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Historical evidence cannot be deleted.")


class Candidate(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        DUPLICATE = "duplicate", "Reconciled duplicate"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    # Opaque fingerprint is an exact-match duplicate guard, not a public identifier.
    identity_fingerprint = models.CharField(max_length=64)
    given_name = models.CharField(max_length=100)
    family_name = models.CharField(max_length=100)
    birth_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    canonical_candidate = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT
    )
    version = models.PositiveIntegerField(default=1)
    import_batch = models.ForeignKey(
        "CandidateImport", null=True, blank=True, on_delete=models.PROTECT
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_candidate"
        ordering = ["family_name", "given_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "identity_fingerprint"],
                name="academic_candidate_identity_unique",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1), name="academic_candidate_version_positive"
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.canonical_candidate_id:
            canonical = self.canonical_candidate
            if canonical is None:
                raise ValidationError("Canonical candidate was not found.")
            if self.status != self.Status.DUPLICATE:
                raise ValidationError("Only reconciled duplicates have a canonical ID.")
            if self.canonical_candidate_id == self.pk:
                raise ValidationError("A candidate cannot reconcile to itself.")
            if canonical.institution_id != self.institution_id:
                raise ValidationError("Canonical candidates must share an institution.")
            if canonical.status == self.Status.DUPLICATE:
                raise ValidationError("Reconciliation chains are not supported.")
        elif self.status == self.Status.DUPLICATE:
            raise ValidationError("A duplicate requires a canonical candidate.")

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Candidate identities must be retained for review.")


class CandidatePlacement(models.Model):
    """Typed FK linking the Phase 03 opaque placement to its Phase 04 identity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    candidate = models.ForeignKey(
        Candidate, on_delete=models.PROTECT, related_name="placements"
    )
    enrolment = models.OneToOneField(Enrolment, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_candidate_placement"
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "enrolment"], name="academic_placement_unique"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.candidate_id and self.enrolment_id:
            if not (
                self.candidate.institution_id
                == self.enrolment.institution_id
                == self.institution_id
                and self.enrolment.learner_reference == self.candidate_id
            ):
                raise ValidationError(
                    "Placement must belong to this candidate and school."
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ValidationError("Placement links are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Placement history cannot be deleted.")


class CandidateChange(AppendOnlyEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(
        Candidate, on_delete=models.PROTECT, related_name="changes"
    )
    version = models.PositiveIntegerField()
    before = models.JSONField()
    after = models.JSONField()
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "academic_candidate_change"
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "version"], name="academic_candidate_change_unique"
            )
        ]


class Guardian(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(max_length=254, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_guardian"
        ordering = ["name", "id"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Guardian identities cannot be deleted.")


class GuardianChange(AppendOnlyEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    guardian = models.ForeignKey(
        Guardian, on_delete=models.PROTECT, related_name="changes"
    )
    version = models.PositiveIntegerField()
    before = models.JSONField()
    after = models.JSONField()
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "academic_guardian_change"
        constraints = [
            models.UniqueConstraint(
                fields=["guardian", "version"], name="academic_guardian_change_unique"
            )
        ]


class GuardianLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    candidate = models.ForeignKey(
        Candidate, on_delete=models.PROTECT, related_name="guardian_links"
    )
    guardian = models.ForeignKey(
        Guardian, on_delete=models.PROTECT, related_name="candidate_links"
    )
    relationship = models.CharField(max_length=80)
    contact_authorized = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_guardian_link"
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "guardian"], name="academic_guardian_link_unique"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.candidate_id
            and self.guardian_id
            and not (
                self.candidate.institution_id
                == self.guardian.institution_id
                == self.institution_id
            )
        ):
            raise ValidationError("A guardian and candidate must share an institution.")

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Guardian links may be closed but not deleted.")


class GuardianLinkChange(AppendOnlyEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    link = models.ForeignKey(
        GuardianLink, on_delete=models.PROTECT, related_name="changes"
    )
    version = models.PositiveIntegerField()
    before = models.JSONField()
    after = models.JSONField()
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "academic_guardian_link_change"
        constraints = [
            models.UniqueConstraint(
                fields=["link", "version"], name="academic_guardian_link_change_unique"
            )
        ]


class CandidateImport(models.Model):
    class Status(models.TextChoices):
        PREVIEWED = "previewed", "Previewed"
        APPLIED = "applied", "Applied"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    idempotency_key = models.UUIDField()
    payload_digest = models.CharField(max_length=64)
    row_count = models.PositiveSmallIntegerField()
    error_count = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PREVIEWED
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    applied_at = models.DateTimeField(null=True, blank=True)

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_candidate_import"
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "idempotency_key"],
                name="academic_import_key_unique",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            if (
                previous.status != self.Status.PREVIEWED
                or any(
                    getattr(self, field) != getattr(previous, field)
                    for field in (
                        "institution_id",
                        "actor_id",
                        "idempotency_key",
                        "payload_digest",
                        "row_count",
                        "error_count",
                    )
                )
                or self.status != self.Status.APPLIED
            ):
                raise ValidationError("Import evidence cannot be changed.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Import evidence cannot be deleted.")


class Baseline(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    candidate = models.ForeignKey(
        Candidate, on_delete=models.PROTECT, related_name="baselines"
    )
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    previous = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    effective_date = models.DateField()
    source_label = models.CharField(max_length=160)
    source_date = models.DateField()
    version = models.PositiveIntegerField(default=1)
    snapshot_digest = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_baselines",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="submitted_baselines",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_baselines",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_baseline"
        ordering = ["candidate_id", "academic_year_id", "-revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "academic_year", "revision"],
                name="academic_baseline_revision_unique",
            ),
            models.UniqueConstraint(
                fields=["previous"],
                condition=Q(previous__isnull=False),
                name="academic_baseline_successor_unique",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1), name="academic_baseline_version_positive"
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.candidate_id and self.candidate.institution_id != self.institution_id:
            raise ValidationError("Candidate belongs to another institution.")
        if self.academic_year_id:
            if self.academic_year.release.institution_id != self.institution_id:
                raise ValidationError("Academic year belongs to another institution.")
            if (
                not self.academic_year.start_date
                <= self.effective_date
                <= self.academic_year.end_date
            ):
                raise ValidationError(
                    "Baseline date must fall within its academic year."
                )
        if self.previous_id:
            previous = self.previous
            if previous is None or (
                previous.status != self.Status.APPROVED
                or previous.candidate_id != self.candidate_id
                or previous.academic_year_id != self.academic_year_id
                or previous.revision + 1 != self.revision
            ):
                raise ValidationError(
                    "A correction must follow an approved baseline for this candidate and year."
                )
        if (self.revision == 1) != (self.previous_id is None):
            raise ValidationError("Initial baselines start at revision one.")
        if self.status == self.Status.APPROVED and not (
            self.submitted_at
            and self.submitted_by_id
            and self.approved_at
            and self.approved_by_id
            and self.snapshot_digest
        ):
            raise ValidationError("Approval evidence is required.")

    def save(self, *args: Any, **kwargs: Any) -> None:
        with transaction.atomic():
            if not self._state.adding:
                previous = type(self).objects.select_for_update().get(pk=self.pk)
                if previous.status == self.Status.APPROVED:
                    raise ValidationError("Approved baselines are immutable.")
                transitions = {
                    self.Status.DRAFT: {self.Status.DRAFT, self.Status.SUBMITTED},
                    self.Status.SUBMITTED: {self.Status.APPROVED},
                }
                if self.status not in transitions[previous.status]:
                    raise ValidationError("Baseline review states cannot be bypassed.")
                if previous.status == self.Status.SUBMITTED:
                    allowed = {
                        "status",
                        "approved_by_id",
                        "approved_at",
                        "snapshot_digest",
                        "version",
                    }
                    if any(
                        getattr(self, field.attname) != getattr(previous, field.attname)
                        for field in self._meta.concrete_fields
                        if field.attname not in allowed
                    ):
                        raise ValidationError(
                            "Submitted baseline contents cannot be edited."
                        )
            self.full_clean()
            super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Baselines cannot be deleted.")


class BaselineObservation(models.Model):
    class State(models.TextChoices):
        SCORED = "scored", "Scored"
        ABSENT = "absent", "Absent"
        MISSING = "missing", "Missing"
        NOT_ASSESSED = "not_assessed", "Not assessed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    baseline = models.ForeignKey(
        Baseline, on_delete=models.PROTECT, related_name="observations"
    )
    offering = models.ForeignKey(SubjectOffering, on_delete=models.PROTECT)
    state = models.CharField(max_length=16, choices=State.choices)
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    maximum_score = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True
    )

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_baseline_observation"
        constraints = [
            models.UniqueConstraint(
                fields=["baseline", "offering"],
                name="academic_baseline_offering_unique",
            ),
            models.CheckConstraint(
                condition=Q(maximum_score__isnull=True) | Q(maximum_score__gt=0),
                name="academic_baseline_max_positive",
            ),
            models.CheckConstraint(
                condition=Q(score__isnull=True) | Q(score__gte=0),
                name="academic_baseline_score_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(score__isnull=True) | Q(maximum_score__gte=F("score")),
                name="academic_baseline_score_within_max",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.baseline_id and self.baseline.status != Baseline.Status.DRAFT:
            raise ValidationError("Only draft baseline observations may be changed.")
        if (
            self.offering_id
            and self.baseline_id
            and (
                self.offering.academic_year_id != self.baseline.academic_year_id
                or self.offering.release.institution_id != self.baseline.institution_id
            )
        ):
            raise ValidationError(
                "Observation offering must share the baseline year and school."
            )
        validate_score(self.state, self.score, self.maximum_score)

    def save(self, *args: Any, **kwargs: Any) -> None:
        with transaction.atomic():
            self.baseline = Baseline.objects.select_for_update().get(
                pk=self.baseline_id
            )
            if self.baseline.status != Baseline.Status.DRAFT:
                raise ValidationError(
                    "Reviewed baseline observations cannot be changed."
                )
            self.full_clean()
            super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        with transaction.atomic():
            current = Baseline.objects.select_for_update().get(pk=self.baseline_id)
            if current.status != Baseline.Status.DRAFT:
                raise ValidationError(
                    "Reviewed baseline observations cannot be deleted."
                )
            return super().delete(*args, **kwargs)


class BaselineEdit(AppendOnlyEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    baseline = models.ForeignKey(
        Baseline, on_delete=models.PROTECT, related_name="edits"
    )
    version = models.PositiveIntegerField()
    before = models.JSONField()
    after = models.JSONField()
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "academic_baseline_edit"
        constraints = [
            models.UniqueConstraint(
                fields=["baseline", "version"], name="academic_baseline_edit_unique"
            )
        ]


class BaselineCorrection(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        AUTHORIZED = "authorized", "Authorized"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    baseline = models.ForeignKey(
        Baseline, on_delete=models.PROTECT, related_name="corrections"
    )
    reason = models.CharField(max_length=500)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_baseline_corrections",
    )
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="authorized_baseline_corrections",
    )
    successor = models.OneToOneField(
        Baseline,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="correction_source",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_baseline_correction"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if (
            not self._state.adding
            and type(self).objects.get(pk=self.pk).status != self.Status.PENDING
        ):
            raise ValidationError("Resolved correction evidence is immutable.")
        if self.baseline_id and self.baseline.institution_id != self.institution_id:
            raise ValidationError("Correction belongs to another institution.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Correction evidence cannot be deleted.")


def validate_score(state: str, score: Any, maximum_score: Any) -> None:
    """Zero is a score, while absent/missing/not-assessed must have no score."""
    if state == BaselineObservation.State.SCORED:
        if (
            score is None
            or maximum_score is None
            or maximum_score <= 0
            or not 0 <= score <= maximum_score
        ):
            raise ValidationError(
                "A scored record needs a score between zero and its positive maximum."
            )
    elif state in (
        BaselineObservation.State.ABSENT,
        BaselineObservation.State.MISSING,
        BaselineObservation.State.NOT_ASSESSED,
    ):
        if score is not None:
            raise ValidationError("Non-scored records must not contain a score.")
        if maximum_score is not None and maximum_score <= 0:
            raise ValidationError("Maximum score must be positive when supplied.")
    else:
        raise ValidationError("Unknown mark state.")


class AcademicActivity(models.Model):
    class Kind(models.TextChoices):
        WEEKLY = "weekly", "Weekly assessment"
        MOCK = "mock", "Monthly full mock"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        MODERATED = "moderated", "Moderated"
        APPROVED = "approved", "Approved"
        PUBLISHED = "published", "Published"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.PROTECT)
    stream = models.ForeignKey(Stream, null=True, blank=True, on_delete=models.PROTECT)
    teacher_assignment = models.ForeignKey(
        TeachingAssignment, null=True, blank=True, on_delete=models.PROTECT
    )
    scheduled_for = models.DateField()
    title = models.CharField(max_length=160)
    assessment_type = models.CharField(max_length=80, blank=True)
    revision = models.PositiveIntegerField(default=1)
    previous = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    version = models.PositiveIntegerField(default=1)
    snapshot_digest = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_academic_activities",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="submitted_academic_activities",
    )
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="moderated_academic_activities",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_academic_activities",
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="published_academic_activities",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    moderated_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_activity"
        ordering = ["-scheduled_for", "-revision", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["previous"],
                condition=Q(previous__isnull=False),
                name="academic_activity_successor_unique",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1), name="academic_activity_version_positive"
            ),
        ]

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.academic_year_id and (
            self.academic_year.release.institution_id != self.institution_id
            or not self.academic_year.start_date
            <= self.scheduled_for
            <= self.academic_year.end_date
        ):
            errors["academic_year"] = (
                "The event must fall within this school's academic year."
            )
        if (
            self.school_class_id
            and self.academic_year_id
            and self.school_class.release_id != self.academic_year.release_id
        ):
            errors["school_class"] = "Class and year must share a release."
        if self.stream_id and (
            self.stream is None or self.stream.school_class_id != self.school_class_id
        ):
            errors["stream"] = "Stream must belong to the selected class."
        if self.kind == self.Kind.WEEKLY:
            assignment = self.teacher_assignment
            if assignment is None:
                errors["teacher_assignment"] = (
                    "Weekly assessments require a teaching assignment."
                )
            elif (
                assignment.offering.academic_year_id != self.academic_year_id
                or assignment.offering.school_class_id != self.school_class_id
                or assignment.release_id != self.academic_year.release_id
            ):
                errors["teacher_assignment"] = (
                    "Teaching assignment does not cover this class and year."
                )
            elif self.scheduled_for < assignment.effective_from or (
                assignment.effective_until
                and self.scheduled_for > assignment.effective_until
            ):
                errors["scheduled_for"] = (
                    "Teaching assignment is not active on this date."
                )
            if not self.assessment_type:
                errors["assessment_type"] = (
                    "Weekly assessments require a configured type label."
                )
        elif self.kind == self.Kind.MOCK and self.teacher_assignment_id:
            errors["teacher_assignment"] = (
                "Mocks have a subject blueprint, not a single teacher."
            )
        if self.previous_id:
            previous = self.previous
            if previous is None or (
                previous.status not in (self.Status.APPROVED, self.Status.PUBLISHED)
                or previous.institution_id != self.institution_id
                or previous.kind != self.kind
                or previous.revision + 1 != self.revision
            ):
                errors["previous"] = (
                    "A correction must follow an approved event from this school."
                )
        if (self.revision == 1) != (self.previous_id is None):
            errors["revision"] = "Initial events start at revision one."
        if self.status in (self.Status.APPROVED, self.Status.PUBLISHED) and not (
            self.approved_at and self.approved_by_id and self.snapshot_digest
        ):
            errors["status"] = "Approval snapshot evidence is required."
        if self.status == self.Status.PUBLISHED and not (
            self.published_by_id and self.published_at
        ):
            errors["status"] = "Publication evidence is required."
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        with transaction.atomic():
            if not self._state.adding:
                previous = type(self).objects.select_for_update().get(pk=self.pk)
                transitions = {
                    self.Status.DRAFT: {self.Status.DRAFT, self.Status.SUBMITTED},
                    self.Status.SUBMITTED: {self.Status.MODERATED, self.Status.DRAFT},
                    self.Status.MODERATED: {self.Status.APPROVED, self.Status.DRAFT},
                    self.Status.APPROVED: {self.Status.PUBLISHED},
                    self.Status.PUBLISHED: set(),
                }
                if self.status not in transitions[previous.status]:
                    raise ValidationError(
                        "Reviewed results cannot be reopened or bypassed."
                    )
                if previous.status != self.Status.DRAFT:
                    allowed = {
                        "status",
                        "version",
                        "moderated_by_id",
                        "moderated_at",
                        "approved_by_id",
                        "approved_at",
                        "snapshot_digest",
                        "published_by_id",
                        "published_at",
                    }
                    if any(
                        getattr(self, field.attname) != getattr(previous, field.attname)
                        for field in self._meta.concrete_fields
                        if field.attname not in allowed
                    ):
                        raise ValidationError(
                            "Reviewed snapshot contents cannot be edited."
                        )
                if previous.status == self.Status.APPROVED:
                    allowed = {"status", "published_by_id", "published_at", "version"}
                    if any(
                        getattr(self, field.attname) != getattr(previous, field.attname)
                        for field in self._meta.concrete_fields
                        if field.attname not in allowed
                    ):
                        raise ValidationError(
                            "Approved result snapshots cannot be edited."
                        )
            self.full_clean()
            super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Academic events cannot be deleted.")


class ActivitySubject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(
        AcademicActivity, on_delete=models.PROTECT, related_name="subjects"
    )
    offering = models.ForeignKey(SubjectOffering, on_delete=models.PROTECT)
    maximum_score = models.DecimalField(max_digits=7, decimal_places=2)

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_activity_subject"
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "offering"],
                name="academic_activity_offering_unique",
            ),
            models.CheckConstraint(
                condition=Q(maximum_score__gt=0), name="academic_activity_max_positive"
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.activity_id and self.activity.status != AcademicActivity.Status.DRAFT:
            raise ValidationError("Approved blueprints cannot be modified.")
        if (
            self.offering_id
            and self.activity_id
            and (
                self.offering.academic_year_id != self.activity.academic_year_id
                or self.offering.school_class_id != self.activity.school_class_id
                or self.offering.release.institution_id != self.activity.institution_id
                or (
                    self.offering.stream_id is not None
                    and self.offering.stream_id != self.activity.stream_id
                )
            )
        ):
            raise ValidationError(
                "Subject offering is outside the activity's year, class or stream."
            )

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ValidationError(
                "Blueprint subjects must be versioned, not overwritten."
            )
        with transaction.atomic():
            self.activity = AcademicActivity.objects.select_for_update().get(
                pk=self.activity_id
            )
            if self.activity.status != AcademicActivity.Status.DRAFT:
                raise ValidationError("Reviewed event contents cannot be changed.")
            self.full_clean()
            super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Blueprint history cannot be deleted.")


class ActivityParticipant(models.Model):
    class Participation(models.TextChoices):
        EXPECTED = "expected", "Expected"
        ATTENDED = "attended", "Attended"
        ABSENT = "absent", "Absent"
        NOT_ASSESSED = "not_assessed", "Not assessed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(
        AcademicActivity, on_delete=models.PROTECT, related_name="participants"
    )
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT)
    eligible = models.BooleanField(default=True)
    participation = models.CharField(
        max_length=16, choices=Participation.choices, default=Participation.EXPECTED
    )
    version = models.PositiveIntegerField(default=1)

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_activity_participant"
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "candidate"], name="academic_participant_unique"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.activity_id and self.activity.status != AcademicActivity.Status.DRAFT:
            raise ValidationError("Participants in reviewed results cannot be changed.")
        if (
            self.candidate_id
            and self.activity_id
            and self.candidate.institution_id != self.activity.institution_id
        ):
            raise ValidationError("Candidate belongs to another institution.")
        if not self.eligible and self.participation != self.Participation.NOT_ASSESSED:
            raise ValidationError(
                "Ineligible candidates cannot be recorded as participants."
            )

    def save(self, *args: Any, **kwargs: Any) -> None:
        with transaction.atomic():
            self.activity = AcademicActivity.objects.select_for_update().get(
                pk=self.activity_id
            )
            if self.activity.status != AcademicActivity.Status.DRAFT:
                raise ValidationError("Reviewed event contents cannot be changed.")
            self.full_clean()
            super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Participation history cannot be deleted.")


class AcademicMark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(
        AcademicActivity, on_delete=models.PROTECT, related_name="marks"
    )
    subject = models.ForeignKey(ActivitySubject, on_delete=models.PROTECT)
    participant = models.ForeignKey(
        ActivityParticipant, on_delete=models.PROTECT, related_name="marks"
    )
    state = models.CharField(
        max_length=16,
        choices=BaselineObservation.State.choices,
        default=BaselineObservation.State.MISSING,
    )
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    updated_at = models.DateTimeField(auto_now=True)

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_mark"
        constraints = [
            models.UniqueConstraint(
                fields=["subject", "participant"], name="academic_mark_cell_unique"
            ),
            models.CheckConstraint(
                condition=Q(score__isnull=True) | Q(score__gte=0),
                name="academic_mark_score_nonnegative",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.activity_id and self.activity.status != AcademicActivity.Status.DRAFT:
            raise ValidationError("Reviewed or approved marks cannot be changed.")
        if (
            self.subject_id
            and self.participant_id
            and not (
                self.subject.activity_id
                == self.participant.activity_id
                == self.activity_id
            )
        ):
            raise ValidationError(
                "Mark, subject and candidate must belong to the same activity."
            )
        if self.participant_id and not self.participant.eligible:
            raise ValidationError("Ineligible candidates cannot receive marks.")
        if self.subject_id:
            validate_score(self.state, self.score, self.subject.maximum_score)

    def save(self, *args: Any, **kwargs: Any) -> None:
        with transaction.atomic():
            self.activity = AcademicActivity.objects.select_for_update().get(
                pk=self.activity_id
            )
            if self.activity.status != AcademicActivity.Status.DRAFT:
                raise ValidationError("Reviewed event contents cannot be changed.")
            self.full_clean()
            super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Mark history cannot be deleted.")


class MarkChange(AppendOnlyEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mark = models.ForeignKey(
        AcademicMark, on_delete=models.PROTECT, related_name="changes"
    )
    version = models.PositiveIntegerField()
    before_state = models.CharField(
        max_length=16, choices=BaselineObservation.State.choices
    )
    before_score = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True
    )
    after_state = models.CharField(
        max_length=16, choices=BaselineObservation.State.choices
    )
    after_score = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "academic_mark_change"
        constraints = [
            models.UniqueConstraint(
                fields=["mark", "version"], name="academic_mark_change_unique"
            )
        ]


class ParticipationChange(AppendOnlyEvidence):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.ForeignKey(
        ActivityParticipant, on_delete=models.PROTECT, related_name="changes"
    )
    version = models.PositiveIntegerField()
    before = models.JSONField()
    after = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "academic_participation_change"
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "version"],
                name="academic_participation_change_unique",
            )
        ]


class ActivityCorrection(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        AUTHORIZED = "authorized", "Authorized"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    activity = models.ForeignKey(
        AcademicActivity, on_delete=models.PROTECT, related_name="corrections"
    )
    reason = models.CharField(max_length=500)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_activity_corrections",
    )
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="authorized_activity_corrections",
    )
    successor = models.OneToOneField(
        AcademicActivity,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="correction_source",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    objects = NoBulkMutationQuerySet.as_manager()

    class Meta:
        db_table = "academic_activity_correction"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if (
            not self._state.adding
            and type(self).objects.get(pk=self.pk).status
            != BaselineCorrection.Status.PENDING
        ):
            raise ValidationError("Resolved correction evidence is immutable.")
        if self.activity_id and self.activity.institution_id != self.institution_id:
            raise ValidationError("Correction belongs to another institution.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Correction evidence cannot be deleted.")


class ActivityEdit(AppendOnlyEvidence):
    """Draft schedule/review state history; scores stay in MarkChange records."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(
        AcademicActivity, on_delete=models.PROTECT, related_name="edits"
    )
    version = models.PositiveIntegerField()
    before = models.JSONField()
    after = models.JSONField()
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "academic_activity_edit"
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "version"], name="academic_activity_edit_unique"
            )
        ]
