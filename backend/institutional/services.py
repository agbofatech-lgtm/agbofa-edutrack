"""Versioned institutional configuration and approval-boundary services."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from identity.models import User
from identity.services.approvals import MakerCheckerContext, may_checker_approve
from identity.services.audit import record_audit_event
from institutional.models import (
    AcademicTerm,
    AcademicYear,
    ConfigurationRelease,
    EducationalLevel,
    Institution,
    InstitutionSetting,
    SchoolClass,
    Stream,
    Subject,
    SubjectOffering,
    TeachingAssignment,
)
from institutional.permissions import CONFIGURATION_APPROVE


class _SubmittedReleasePolicy:
    """Approve only the exact submitted release passed by the trusted service."""

    def __init__(self, release: ConfigurationRelease) -> None:
        self.release_id = str(release.pk)

    def may_check(self, context: MakerCheckerContext) -> bool:
        return (
            context.resource_type == "institution.configuration.release"
            and context.resource_id == self.release_id
        )


def _clone_rows(
    source: ConfigurationRelease,
    target: ConfigurationRelease,
    model: type[Any],
    fields: Iterable[str],
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for original in model.objects.filter(release=source).order_by("pk"):
        values = {field: getattr(original, field) for field in fields}
        clone = model.objects.create(release=target, **values)
        mapping[original.pk] = clone
    return mapping


def _clone_release_contents(
    source: ConfigurationRelease,
    target: ConfigurationRelease,
) -> None:
    for setting in InstitutionSetting.objects.filter(release=source).order_by("pk"):
        InstitutionSetting.objects.create(
            release=target,
            key=setting.key,
            label=setting.label,
            description=setting.description,
            value_type=setting.value_type,
            value=setting.value,
        )

    years = _clone_rows(
        source,
        target,
        AcademicYear,
        ("code", "name", "start_date", "end_date"),
    )
    terms: dict[Any, Any] = {}
    for original_term in AcademicTerm.objects.filter(release=source).order_by("pk"):
        term_clone = AcademicTerm.objects.create(
            release=target,
            academic_year=years[original_term.academic_year_id],
            code=original_term.code,
            name=original_term.name,
            sequence=original_term.sequence,
            start_date=original_term.start_date,
            end_date=original_term.end_date,
        )
        terms[original_term.pk] = term_clone

    levels = _clone_rows(source, target, EducationalLevel, ("code", "name", "position"))
    classes: dict[Any, Any] = {}
    for original_class in SchoolClass.objects.filter(release=source).order_by("pk"):
        class_clone = SchoolClass.objects.create(
            release=target,
            level=levels[original_class.level_id],
            code=original_class.code,
            name=original_class.name,
            position=original_class.position,
        )
        classes[original_class.pk] = class_clone

    streams: dict[Any, Any] = {}
    for original_stream in Stream.objects.filter(release=source).order_by("pk"):
        stream_clone = Stream.objects.create(
            release=target,
            school_class=classes[original_stream.school_class_id],
            code=original_stream.code,
            name=original_stream.name,
        )
        streams[original_stream.pk] = stream_clone

    subjects = _clone_rows(source, target, Subject, ("code", "name", "description"))
    offerings: dict[Any, Any] = {}
    for original_offering in SubjectOffering.objects.filter(release=source).order_by(
        "pk"
    ):
        offering_clone = SubjectOffering.objects.create(
            release=target,
            academic_year=years[original_offering.academic_year_id],
            term=terms.get(original_offering.term_id),
            school_class=classes[original_offering.school_class_id],
            stream=streams.get(original_offering.stream_id),
            subject=subjects[original_offering.subject_id],
        )
        offerings[original_offering.pk] = offering_clone

    for original_assignment in TeachingAssignment.objects.filter(
        release=source
    ).order_by("pk"):
        TeachingAssignment.objects.create(
            release=target,
            offering=offerings[original_assignment.offering_id],
            staff_membership=original_assignment.staff_membership,
            effective_from=original_assignment.effective_from,
            effective_until=original_assignment.effective_until,
        )

    # Staff affiliations and enrolments are historical institutional records, not
    # settings snapshots. They remain attached to their original effective records.


@transaction.atomic
def create_draft_release(
    *,
    institution: Institution,
    actor: User,
    effective_from: date,
    source_release: ConfigurationRelease | None = None,
    request: Any,
) -> ConfigurationRelease:
    """Create an empty first draft or clone an approved release into a new revision."""

    Institution.objects.select_for_update().get(pk=institution.pk)
    if source_release is not None:
        if (
            source_release.institution_id != institution.pk
            or source_release.status != ConfigurationRelease.Status.APPROVED
        ):
            raise ValidationError(
                "A new revision may only clone an approved release from this institution."
            )

    revision = (
        ConfigurationRelease.objects.filter(institution=institution)
        .order_by("-revision")
        .values_list("revision", flat=True)
        .first()
        or 0
    ) + 1
    release = ConfigurationRelease.objects.create(
        institution=institution,
        revision=revision,
        previous_release=source_release,
        status=ConfigurationRelease.Status.DRAFT,
        effective_from=effective_from,
        created_by=actor,
    )
    if source_release is not None:
        _clone_release_contents(source_release, release)
    record_audit_event(
        action="institution.configuration.release.created",
        request=request,
        actor=actor,
        subject_type="institution.configuration_release",
        subject_id=str(release.pk),
        metadata={
            "institution_id": str(institution.pk),
            "revision": revision,
            "cloned": source_release is not None,
        },
    )
    return release


def _release_records(release: ConfigurationRelease) -> Iterable[Any]:
    yield from InstitutionSetting.objects.filter(release=release)
    yield from AcademicYear.objects.filter(release=release)
    yield from AcademicTerm.objects.filter(release=release)
    yield from EducationalLevel.objects.filter(release=release)
    yield from SchoolClass.objects.filter(release=release)
    yield from Stream.objects.filter(release=release)
    yield from Subject.objects.filter(release=release)
    yield from SubjectOffering.objects.filter(release=release)
    yield from TeachingAssignment.objects.filter(release=release)


@transaction.atomic
def submit_release(
    *, release: ConfigurationRelease, actor: User, request: Any
) -> ConfigurationRelease:
    """Validate a draft snapshot before making it available for independent review."""

    locked = ConfigurationRelease.objects.select_for_update().get(pk=release.pk)
    if locked.status != ConfigurationRelease.Status.DRAFT:
        raise ValidationError("Only a draft release can be submitted for review.")
    # Validate every row before freezing the snapshot. Empty drafts may be submitted;
    # no institutional calendar or structure is made mandatory by this foundation.
    for row in _release_records(locked):
        row.full_clean()
    locked.status = ConfigurationRelease.Status.SUBMITTED
    locked.submitted_at = timezone.now()
    locked.save(update_fields=["status", "submitted_at"])
    record_audit_event(
        action="institution.configuration.release.submitted",
        request=request,
        actor=actor,
        subject_type="institution.configuration_release",
        subject_id=str(locked.pk),
        metadata={
            "institution_id": str(locked.institution_id),
            "revision": locked.revision,
        },
    )
    return locked


@transaction.atomic
def approve_release(
    *, release: ConfigurationRelease, actor: User, request: Any
) -> ConfigurationRelease:
    """Record an independent, institution-scoped approval; no policy is inferred."""

    locked = ConfigurationRelease.objects.select_for_update().get(pk=release.pk)
    if locked.status != ConfigurationRelease.Status.SUBMITTED:
        raise ValidationError("Only a submitted release can be approved.")
    if not may_checker_approve(
        MakerCheckerContext(
            maker_id=str(locked.created_by_id),
            checker_id=str(actor.pk),
            resource_type="institution.configuration.release",
            resource_id=str(locked.pk),
            permission_code=CONFIGURATION_APPROVE,
            scope_type="institution",
            scope_key=str(locked.institution_id),
        ),
        checker=actor,
        policy=_SubmittedReleasePolicy(locked),
    ):
        raise PermissionDenied(
            "Approval requires a distinct actor with an approved scoped permission."
        )
    locked.status = ConfigurationRelease.Status.APPROVED
    locked.approved_by = actor
    locked.approved_at = timezone.now()
    locked.full_clean()
    locked.save(update_fields=["status", "approved_by", "approved_at"])
    record_audit_event(
        action="institution.configuration.release.approved",
        request=request,
        actor=actor,
        subject_type="institution.configuration_release",
        subject_id=str(locked.pk),
        metadata={
            "institution_id": str(locked.institution_id),
            "revision": locked.revision,
            "effective_from": locked.effective_from.isoformat(),
        },
    )
    return locked


def get_effective_release(
    institution: Institution, *, on_date: date
) -> ConfigurationRelease | None:
    """Resolve the latest approved snapshot for an explicit institution-local date."""

    return (
        ConfigurationRelease.objects.filter(
            institution=institution,
            status=ConfigurationRelease.Status.APPROVED,
            effective_from__lte=on_date,
        )
        .order_by("-effective_from", "-revision")
        .first()
    )


def is_release_content_mutable(release: ConfigurationRelease) -> bool:
    return release.status == ConfigurationRelease.Status.DRAFT
