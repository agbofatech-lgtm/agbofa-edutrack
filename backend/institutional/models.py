from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

_SENSITIVE_SETTING_KEY_MARKERS = (
    "password",
    "secret",
    "token",
    "credential",
    "apikey",
    "privatekey",
    "accesskey",
)


def _is_sensitive_setting_key(value: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(value).casefold())
    return any(marker in normalized for marker in _SENSITIVE_SETTING_KEY_MARKERS)


def _contains_sensitive_setting_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if _is_sensitive_setting_key(key) or _contains_sensitive_setting_key(
                nested
            ):
                return True
    elif isinstance(value, list | tuple):
        return any(_contains_sensitive_setting_key(item) for item in value)
    return False


class Institution(models.Model):
    """Tenant boundary for institution-specific configuration; no school is seeded."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "institutional_institution"
        ordering = ["code"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class ConfigurationRelease(models.Model):
    """Immutable approved snapshot boundary for institution configuration."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted for review"
        APPROVED = "approved", "Approved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        related_name="configuration_releases",
    )
    revision = models.PositiveIntegerField()
    previous_release = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="successor_releases",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    effective_from = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_institution_configuration_releases",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_institution_configuration_releases",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "institutional_configuration_release"
        ordering = ["institution_id", "-revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "revision"],
                name="inst_release_revision_uniq",
            ),
            models.UniqueConstraint(
                fields=["institution", "effective_from"],
                condition=Q(status="approved"),
                name="inst_release_effective_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["institution", "status", "effective_from"],
                name="inst_release_lookup_idx",
            )
        ]

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.previous_release_id and self.institution_id:
            previous = self.previous_release
            if previous is not None and previous.institution_id != self.institution_id:
                errors["previous_release"] = (
                    "A revision must inherit from the same institution."
                )
            elif previous is not None and previous.revision >= self.revision:
                errors["previous_release"] = (
                    "A revision must follow its source revision."
                )
        if self.status == self.Status.DRAFT:
            if self.submitted_at or self.approved_by_id or self.approved_at:
                errors["status"] = "Draft releases cannot contain review evidence."
        elif self.status == self.Status.SUBMITTED:
            if self.submitted_at is None:
                errors["submitted_at"] = "A submitted release requires a timestamp."
            if self.approved_by_id or self.approved_at:
                errors["status"] = (
                    "A submitted release cannot contain approval evidence."
                )
        elif self.status == self.Status.APPROVED:
            if self.submitted_at is None:
                errors["submitted_at"] = "An approved release must have been submitted."
            if self.approved_by_id is None or self.approved_at is None:
                errors["approved_by"] = "Approval requires an actor and timestamp."
            if self.approved_by_id == self.created_by_id:
                errors["approved_by"] = "The author cannot approve their own release."
        if self.status == self.Status.APPROVED and self.institution_id:
            duplicate_effective_date = ConfigurationRelease.objects.filter(
                institution_id=self.institution_id,
                status=self.Status.APPROVED,
                effective_from=self.effective_from,
            ).exclude(pk=self.pk)
            if duplicate_effective_date.exists():
                errors["effective_from"] = (
                    "Only one approved release may begin on a given date."
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            prior_status = self.Status(previous.status)
            immutable_fields = (
                "institution_id",
                "revision",
                "previous_release_id",
                "effective_from",
                "created_by_id",
            )
            if any(
                getattr(previous, field) != getattr(self, field)
                for field in immutable_fields
            ):
                raise ValidationError(
                    "Release identity and effective date are immutable."
                )
            allowed_transitions = {
                self.Status.DRAFT: {self.Status.DRAFT, self.Status.SUBMITTED},
                self.Status.SUBMITTED: {self.Status.SUBMITTED, self.Status.APPROVED},
                self.Status.APPROVED: {self.Status.APPROVED},
            }
            if self.status not in allowed_transitions[prior_status]:
                raise ValidationError("Configuration releases cannot be reopened.")
            if prior_status == self.Status.APPROVED:
                raise ValidationError("Approved releases are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)

    def is_effective_on(self, as_of_date: date) -> bool:
        """Evaluate against an explicit institution-local date; never infer a calendar."""

        return self.status == self.Status.APPROVED and self.effective_from <= as_of_date

    def __str__(self) -> str:
        return f"{self.institution.code} revision {self.revision} ({self.status})"


class ReleaseScopedModel(models.Model):
    """Base for catalog data that belongs to one immutable config revision."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    release = models.ForeignKey(
        ConfigurationRelease,
        on_delete=models.PROTECT,
        related_name="%(class)s_records",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def clean(self) -> None:
        super().clean()
        original = None
        if not self._state.adding:
            manager = self._meta.default_manager
            original = manager.filter(pk=self.pk).first() if manager else None
            if original is None:
                raise ValidationError(
                    {"release": "This configuration record no longer exists."}
                )
            if original.release_id != self.release_id:
                raise ValidationError(
                    {"release": "A configuration record cannot change revisions."}
                )

        release_status = None
        if self.release_id:
            release_status = (
                ConfigurationRelease.objects.filter(pk=self.release_id)
                .values_list("status", flat=True)
                .first()
            )
        if self.release_id and release_status != ConfigurationRelease.Status.DRAFT:
            if self._state.adding:
                raise ValidationError(
                    {"release": "Configuration records can only be added to a draft."}
                )
            changed_fields = (
                field.attname
                for field in self._meta.concrete_fields
                if field.name != "updated_at"
                and original is not None
                and getattr(original, field.attname) != getattr(self, field.attname)
            )
            if next(changed_fields, None) is not None:
                raise ValidationError(
                    {"release": "Start a new draft revision to change this record."}
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        with transaction.atomic():
            if self.release_id:
                release = (
                    ConfigurationRelease.objects.select_for_update()
                    .filter(pk=self.release_id)
                    .first()
                )
                if release is not None:
                    Institution.objects.select_for_update().filter(
                        pk=release.institution_id
                    ).first()
            self.full_clean()
            super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        with transaction.atomic():
            manager = self._meta.default_manager
            if manager is None:
                raise ValidationError("Configuration record manager is unavailable.")
            release_id = (
                manager.filter(pk=self.pk).values_list("release_id", flat=True).first()
            )
            if release_id is None:
                return super().delete(*args, **kwargs)
            release = (
                ConfigurationRelease.objects.select_for_update()
                .filter(pk=release_id)
                .first()
            )
            if release is not None:
                Institution.objects.select_for_update().filter(
                    pk=release.institution_id
                ).first()
            persisted = manager.select_for_update().filter(pk=self.pk).first()
            if persisted is None:
                return super().delete(*args, **kwargs)
            if persisted.release_id != release_id:
                raise ValidationError("A configuration record cannot change revisions.")
            if release is None or release.status != ConfigurationRelease.Status.DRAFT:
                raise ValidationError(
                    "Approved or submitted configuration history cannot be deleted."
                )
            return super().delete(*args, **kwargs)


class InstitutionSetting(ReleaseScopedModel):
    class ValueType(models.TextChoices):
        TEXT = "text", "Text"
        INTEGER = "integer", "Integer"
        DECIMAL = "decimal", "Decimal"
        BOOLEAN = "boolean", "Boolean"
        DATE = "date", "Date"
        JSON = "json", "Structured JSON"

    key = models.CharField(max_length=120)
    label = models.CharField(max_length=160, blank=True)
    description = models.CharField(max_length=400, blank=True)
    value_type = models.CharField(max_length=16, choices=ValueType.choices)
    value = models.JSONField()

    class Meta:
        db_table = "institutional_setting"
        ordering = ["key"]
        constraints = [
            models.UniqueConstraint(
                fields=["release", "key"], name="inst_setting_key_uniq"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,119}", self.key or ""):
            raise ValidationError(
                {"key": "Use a lowercase configuration key with dots or hyphens."}
            )
        if _is_sensitive_setting_key(self.key):
            raise ValidationError(
                {"key": "Store credentials in an approved secret store, not settings."}
            )
        value = self.value
        valid = True
        if _contains_sensitive_setting_key(value):
            raise ValidationError(
                {"value": "Credential fields must remain in an approved secret store."}
            )
        if self.value_type == self.ValueType.TEXT:
            valid = isinstance(value, str)
        elif self.value_type == self.ValueType.INTEGER:
            valid = isinstance(value, int) and not isinstance(value, bool)
        elif self.value_type == self.ValueType.DECIMAL:
            if isinstance(value, bool) or not isinstance(value, int | float | str):
                valid = False
            else:
                try:
                    valid = Decimal(str(value)).is_finite()
                except InvalidOperation:
                    valid = False
        elif self.value_type == self.ValueType.BOOLEAN:
            valid = isinstance(value, bool)
        elif self.value_type == self.ValueType.DATE:
            try:
                from datetime import date

                valid = (
                    isinstance(value, str)
                    and date.fromisoformat(value).isoformat() == value
                )
            except ValueError:
                valid = False
        if not valid:
            raise ValidationError(
                {"value": f"The value does not match the {self.value_type} type."}
            )


class AcademicYear(ReleaseScopedModel):
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        db_table = "institutional_academic_year"
        ordering = ["start_date", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["release", "code"], name="inst_year_code_uniq"
            ),
            models.CheckConstraint(
                condition=Q(end_date__gte=models.F("start_date")),
                name="inst_year_date_order",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date must not precede start date."})


class AcademicTerm(ReleaseScopedModel):
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="terms"
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    sequence = models.PositiveSmallIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        db_table = "institutional_academic_term"
        ordering = ["academic_year__start_date", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "code"], name="inst_term_code_uniq"
            ),
            models.UniqueConstraint(
                fields=["academic_year", "sequence"], name="inst_term_seq_uniq"
            ),
            models.CheckConstraint(
                condition=Q(end_date__gte=models.F("start_date")),
                name="inst_term_date_order",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors["end_date"] = "End date must not precede start date."
        if self.academic_year_id and self.release_id:
            if self.academic_year.release_id != self.release_id:
                errors["academic_year"] = (
                    "Term and academic year must share a revision."
                )
            if (
                self.start_date
                and self.end_date
                and (
                    self.start_date < self.academic_year.start_date
                    or self.end_date > self.academic_year.end_date
                )
            ):
                errors["start_date"] = "Term dates must fall within the academic year."
        if errors:
            raise ValidationError(errors)


class EducationalLevel(ReleaseScopedModel):
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    position = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "institutional_educational_level"
        ordering = ["position", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["release", "code"], name="inst_level_code_uniq"
            ),
            models.UniqueConstraint(
                fields=["release", "position"], name="inst_level_pos_uniq"
            ),
        ]


class SchoolClass(ReleaseScopedModel):
    level = models.ForeignKey(
        EducationalLevel, on_delete=models.PROTECT, related_name="classes"
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    position = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "institutional_class"
        ordering = ["level__position", "position", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["release", "code"], name="inst_class_code_uniq"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.level_id and self.release_id:
            if self.level.release_id != self.release_id:
                raise ValidationError(
                    {"level": "Class and level must share a revision."}
                )


class Stream(ReleaseScopedModel):
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.PROTECT, related_name="streams"
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)

    class Meta:
        db_table = "institutional_stream"
        ordering = ["school_class__position", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["school_class", "code"], name="inst_stream_code_uniq"
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.school_class_id and self.release_id:
            if self.school_class.release_id != self.release_id:
                raise ValidationError(
                    {"school_class": "Stream and class must share a revision."}
                )


class Subject(ReleaseScopedModel):
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=400, blank=True)

    class Meta:
        db_table = "institutional_subject"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["release", "code"], name="inst_subject_code_uniq"
            )
        ]


class SubjectOffering(ReleaseScopedModel):
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="subject_offerings"
    )
    term = models.ForeignKey(
        AcademicTerm,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="subject_offerings",
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.PROTECT, related_name="subject_offerings"
    )
    stream = models.ForeignKey(
        Stream,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="subject_offerings",
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="class_offerings"
    )

    class Meta:
        db_table = "institutional_subject_offering"
        ordering = ["academic_year__start_date", "school_class__code", "subject__code"]

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        related: list[ReleaseScopedModel | None] = []
        if self.academic_year_id:
            related.append(self.academic_year)
        if self.school_class_id:
            related.append(self.school_class)
        if self.subject_id:
            related.append(self.subject)
        if self.term_id:
            related.append(self.term)
        if self.stream_id:
            related.append(self.stream)
        if self.release_id and any(
            item.release_id != self.release_id for item in related if item is not None
        ):
            errors["release"] = "Offering dependencies must share one revision."
        term = self.term if self.term_id else None
        if term is not None and self.academic_year_id:
            if term.academic_year_id != self.academic_year_id:
                errors["term"] = "The selected term must belong to the academic year."
        stream = self.stream if self.stream_id else None
        if stream is not None and self.school_class_id:
            if stream.school_class_id != self.school_class_id:
                errors["stream"] = "The stream must belong to the selected class."
        if errors:
            raise ValidationError(errors)


class InstitutionStaffMembership(models.Model):
    """Institution affiliation, deliberately separate from RBAC job-role grants."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(
        Institution, on_delete=models.PROTECT, related_name="staff_memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="institutional_memberships",
    )
    staff_reference = models.CharField(max_length=64, blank=True)
    effective_from = models.DateField()
    effective_until = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_institutional_memberships",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "institutional_staff_membership"
        ordering = ["institution_id", "staff_reference", "effective_from"]
        constraints = [
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gte=models.F("effective_from")),
                name="inst_staff_period_order",
            ),
            models.UniqueConstraint(
                fields=["institution", "user", "effective_from"],
                name="inst_staff_start_uniq",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.effective_until
            and self.effective_from
            and self.effective_until < self.effective_from
        ):
            raise ValidationError(
                {"effective_until": "Membership end must not precede its start."}
            )
        if self.institution_id and self.user_id and self.effective_from:
            overlaps = InstitutionStaffMembership.objects.filter(
                institution_id=self.institution_id,
                user_id=self.user_id,
            ).exclude(pk=self.pk)
            if self.effective_until:
                overlaps = overlaps.filter(effective_from__lte=self.effective_until)
            overlaps = overlaps.filter(
                Q(effective_until__isnull=True)
                | Q(effective_until__gte=self.effective_from)
            )
            if overlaps.exists():
                raise ValidationError(
                    {"effective_from": "Staff membership periods may not overlap."}
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        with transaction.atomic():
            if self.institution_id:
                Institution.objects.select_for_update().filter(
                    pk=self.institution_id
                ).first()
            self.full_clean()
            super().save(*args, **kwargs)


class TeachingAssignment(ReleaseScopedModel):
    offering = models.ForeignKey(
        SubjectOffering, on_delete=models.PROTECT, related_name="teaching_assignments"
    )
    staff_membership = models.ForeignKey(
        InstitutionStaffMembership,
        on_delete=models.PROTECT,
        related_name="teaching_assignments",
    )
    effective_from = models.DateField()
    effective_until = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "institutional_teaching_assignment"
        ordering = ["effective_from", "staff_membership_id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gte=models.F("effective_from")),
                name="inst_teacher_period_order",
            )
        ]

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if self.offering_id and self.release_id:
            if self.offering.release_id != self.release_id:
                errors["offering"] = "Assignment and offering must share a revision."
        if self.staff_membership_id and self.release_id:
            institution_id = self.release.institution_id
            if self.staff_membership.institution_id != institution_id:
                errors["staff_membership"] = (
                    "Staff membership must belong to the release institution."
                )
            if (
                self.effective_from
                and self.effective_from < self.staff_membership.effective_from
            ):
                errors["effective_from"] = (
                    "Assignment must begin during the staff membership."
                )
            if self.staff_membership.effective_until and (
                self.effective_from > self.staff_membership.effective_until
                or self.effective_until is None
                or self.effective_until > self.staff_membership.effective_until
            ):
                errors["effective_until"] = (
                    "Assignment must end within the staff membership."
                )
        if (
            self.effective_until
            and self.effective_from
            and self.effective_until < self.effective_from
        ):
            errors["effective_until"] = "Assignment end must not precede its start."
        if self.offering_id and self.effective_from:
            year = self.offering.academic_year
            if (
                self.effective_from < year.start_date
                or self.effective_from > year.end_date
            ):
                errors["effective_from"] = (
                    "Assignment must fall within its academic year."
                )
            if self.effective_until and self.effective_until > year.end_date:
                errors["effective_until"] = (
                    "Assignment must end within its academic year."
                )
        if errors:
            raise ValidationError(errors)


class Enrolment(models.Model):
    """Minimal placement record referencing a future learner registry by opaque UUID."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(
        Institution, on_delete=models.PROTECT, related_name="enrolments"
    )
    learner_reference = models.UUIDField(
        help_text="Opaque future learner-registry identifier; contains no learner PII."
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="enrolments"
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.PROTECT, related_name="enrolments"
    )
    stream = models.ForeignKey(
        Stream,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="enrolments",
    )
    effective_from = models.DateField()
    effective_until = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_institutional_enrolments",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "institutional_enrolment"
        ordering = ["academic_year__start_date", "effective_from"]
        indexes = [
            models.Index(
                fields=["institution", "learner_reference"],
                name="inst_enrolment_ref_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gte=models.F("effective_from")),
                name="inst_enrolment_period_order",
            )
        ]

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        year = self.academic_year if self.academic_year_id else None
        if year is not None:
            if year.release.institution_id != self.institution_id:
                errors["academic_year"] = (
                    "Academic year belongs to another institution."
                )
            if self.effective_from and (
                self.effective_from < year.start_date
                or self.effective_from > year.end_date
            ):
                errors["effective_from"] = (
                    "Enrolment must fall within its academic year."
                )
            if self.effective_until and self.effective_until > year.end_date:
                errors["effective_until"] = (
                    "Enrolment must end within its academic year."
                )
            release_status = (
                ConfigurationRelease.objects.filter(pk=year.release_id)
                .values_list("status", flat=True)
                .first()
            )
            if release_status != ConfigurationRelease.Status.APPROVED:
                errors["academic_year"] = (
                    "Enrolments require an approved configuration."
                )
        school_class = self.school_class if self.school_class_id else None
        if school_class is not None and year is not None:
            if school_class.release_id != year.release_id:
                errors["school_class"] = (
                    "Class and academic year must share a revision."
                )
        stream = self.stream if self.stream_id else None
        if stream is not None and self.school_class_id:
            if stream.school_class_id != self.school_class_id:
                errors["stream"] = "Stream must belong to the selected class."
        if (
            self.effective_until
            and self.effective_from
            and self.effective_until < self.effective_from
        ):
            errors["effective_until"] = "Enrolment end must not precede its start."
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
