"""BA-0 review, immutable snapshot and independently authorized revision lifecycle."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from academic.models import (
    Baseline,
    BaselineCorrection,
    BaselineEdit,
    BaselineObservation,
    Candidate,
)
from academic.permissions import (
    BASELINE_APPROVE,
    BASELINE_CORRECT,
    BASELINE_CORRECTION_AUTHORIZE,
    BASELINE_ENTER,
    BASELINE_SUBMIT,
)
from academic.validation import (
    Conflict,
    active_placement,
    offering_for,
    placement_context,
    require_permission,
    snapshot_digest,
    verify_version,
)
from identity.services.approvals import MakerCheckerContext, may_checker_approve
from identity.services.audit import record_audit_event
from institutional.models import AcademicYear, Institution


def _audit(action: str, request: Any, baseline: Baseline, **metadata: object) -> None:
    record_audit_event(
        action=action,
        request=request,
        actor=request.user,
        subject_type="academic.baseline",
        subject_id=str(baseline.pk),
        metadata={
            "institution_id": str(baseline.institution_id),
            "revision": baseline.revision,
            **metadata,
        },
    )


def _snapshot(baseline: Baseline) -> dict[str, Any]:
    return {
        "candidate": str(baseline.candidate_id),
        "year": str(baseline.academic_year_id),
        "effective_date": baseline.effective_date.isoformat(),
        "source_label": baseline.source_label,
        "source_date": baseline.source_date.isoformat(),
        "observations": sorted(
            (
                {
                    "offering": str(row.offering_id),
                    "state": row.state,
                    "score": str(row.score) if row.score is not None else None,
                    "maximum_score": str(row.maximum_score)
                    if row.maximum_score is not None
                    else None,
                }
                for row in baseline.observations.all()
            ),
            key=lambda value: value["offering"],
        ),
    }


def _validate_rows(
    baseline: Baseline, rows: list[Mapping[str, Any]]
) -> list[tuple[Any, Mapping[str, Any]]]:
    candidate = baseline.candidate
    if candidate.status == Candidate.Status.DUPLICATE:
        raise Conflict("Reconciled candidates cannot receive a new baseline revision.")
    placement = (
        candidate.placements.filter(
            enrolment__academic_year=baseline.academic_year,
            enrolment__effective_from__lte=baseline.effective_date,
        )
        .filter(
            Q(enrolment__effective_until__isnull=True)
            | Q(enrolment__effective_until__gte=baseline.effective_date)
        )
        .select_related("enrolment")
        .first()
    )
    if placement is None:
        raise ValidationError(
            {"candidate": "The candidate needs a placement for this academic year."}
        )
    year, school_class, stream = placement_context(
        baseline.institution,
        baseline.academic_year_id,
        placement.enrolment.school_class_id,
        placement.enrolment.stream_id,
        baseline.effective_date,
    )
    active_placement(candidate, year, school_class, stream, baseline.effective_date)
    seen: set[Any] = set()
    subjects: set[Any] = set()
    validated = []
    for row in rows:
        offering = offering_for(
            row["offering"], year, school_class, stream, on_date=baseline.effective_date
        )
        if offering.pk in seen or offering.subject_id in subjects:
            raise ValidationError(
                {"observations": "An offering or subject appears more than once."}
            )
        seen.add(offering.pk)
        subjects.add(offering.subject_id)
        observation = BaselineObservation(
            baseline=baseline,
            offering=offering,
            state=row["state"],
            score=Decimal(str(row["score"])) if row.get("score") is not None else None,
            maximum_score=Decimal(str(row["maximum_score"]))
            if row.get("maximum_score") is not None
            else None,
        )
        observation.full_clean(validate_unique=False, validate_constraints=False)
        validated.append((offering, row))
    return validated


def _write_rows(baseline: Baseline, rows: list[tuple[Any, Mapping[str, Any]]]) -> None:
    for current in baseline.observations.all():
        current.delete()
    for offering, row in rows:
        BaselineObservation.objects.create(
            baseline=baseline,
            offering=offering,
            state=row["state"],
            score=row.get("score"),
            maximum_score=row.get("maximum_score"),
        )


@transaction.atomic
def create_baseline(
    *, institution: Institution, actor: Any, request: Any, data: Mapping[str, Any]
) -> Baseline:
    require_permission(actor, BASELINE_ENTER, institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    candidate = get_object_or_404(
        Candidate, pk=data["candidate"], institution=institution
    )
    year = get_object_or_404(
        AcademicYear, pk=data["academic_year"], release__institution=institution
    )
    if candidate.status != Candidate.Status.ACTIVE:
        raise Conflict("Only active candidates can start a baseline.")
    if Baseline.objects.filter(candidate=candidate, academic_year=year).exists():
        raise Conflict(
            "This candidate and year already have a baseline; request a correction instead."
        )
    baseline = Baseline.objects.create(
        institution=institution,
        candidate=candidate,
        academic_year=year,
        effective_date=data["effective_date"],
        source_label=data["source_label"],
        source_date=data["source_date"],
        created_by=actor,
        revision=1,
    )
    rows = _validate_rows(baseline, data["observations"])
    _write_rows(baseline, rows)
    _audit(
        "academic.baseline.created",
        request,
        baseline,
        missing=sum(row["state"] == "missing" for _, row in rows),
        absent=sum(row["state"] == "absent" for _, row in rows),
    )
    return baseline


@transaction.atomic
def patch_baseline(
    *,
    baseline: Baseline,
    institution: Institution,
    actor: Any,
    request: Any,
    data: Mapping[str, Any],
) -> Baseline:
    require_permission(actor, BASELINE_ENTER, institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        Baseline.objects.select_for_update(), pk=baseline.pk, institution=institution
    )
    verify_version(locked, data["expected_version"])
    if locked.status != Baseline.Status.DRAFT:
        raise Conflict("Submitted and approved baselines cannot be edited.")
    before = _snapshot(locked)
    for field in ("effective_date", "source_label", "source_date"):
        if field in data:
            setattr(locked, field, data[field])
    locked.full_clean()
    rows = _validate_rows(locked, data.get("observations", before["observations"]))
    if "observations" in data:
        _write_rows(locked, rows)
    after = _snapshot(locked)
    if before == after:
        raise ValidationError("Nothing changed.")
    locked.version += 1
    locked.save()
    BaselineEdit.objects.create(
        baseline=locked,
        version=locked.version,
        before=before,
        after=after,
        reason=data["reason"],
        actor=actor,
    )
    _audit(
        "academic.baseline.edited",
        request,
        locked,
        version=locked.version,
        before_digest=snapshot_digest(before),
        after_digest=snapshot_digest(after),
    )
    return cast(Baseline, locked)


class _SubmittedBaselinePolicy:
    def __init__(self, baseline: Baseline) -> None:
        self.baseline = baseline

    def may_check(self, context: MakerCheckerContext) -> bool:
        return (
            self.baseline.status == Baseline.Status.SUBMITTED
            and context.checker_id != str(self.baseline.submitted_by_id)
            and not BaselineEdit.objects.filter(
                baseline=self.baseline, actor_id=int(context.checker_id)
            ).exists()
        )


class _CorrectionPolicy:
    def __init__(self, source: Baseline) -> None:
        self.source = source

    def may_check(self, context: MakerCheckerContext) -> bool:
        return self.source.status == Baseline.Status.APPROVED


@transaction.atomic
def transition_baseline(
    *,
    baseline: Baseline,
    institution: Institution,
    actor: Any,
    request: Any,
    action: str,
    expected_version: int,
) -> Baseline:
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        Baseline.objects.select_for_update(), pk=baseline.pk, institution=institution
    )
    verify_version(locked, expected_version)
    if action == "submit":
        require_permission(actor, BASELINE_SUBMIT, institution)
        if locked.status != Baseline.Status.DRAFT:
            raise Conflict("Only draft baselines may be submitted.")
        _validate_rows(locked, _snapshot(locked)["observations"])
        locked.status = Baseline.Status.SUBMITTED
        locked.submitted_by = actor
        locked.submitted_at = timezone.now()
        locked.version += 1
        locked.save()
        _audit(
            "academic.baseline.submitted",
            request,
            locked,
            version=locked.version,
            missing=locked.observations.filter(state="missing").count(),
            absent=locked.observations.filter(state="absent").count(),
        )
    elif action == "approve":
        require_permission(actor, BASELINE_APPROVE, institution)
        if not may_checker_approve(
            MakerCheckerContext(
                maker_id=str(locked.created_by_id),
                checker_id=str(actor.pk),
                resource_type="academic.baseline",
                resource_id=str(locked.pk),
                permission_code=BASELINE_APPROVE,
                scope_type="institution",
                scope_key=str(institution.pk),
            ),
            checker=actor,
            policy=_SubmittedBaselinePolicy(locked),
        ):
            raise PermissionDenied(
                "Approval requires an independent reviewer and scoped authority."
            )
        before_digest = locked.previous.snapshot_digest if locked.previous_id else None
        locked.status = Baseline.Status.APPROVED
        locked.approved_by = actor
        locked.approved_at = timezone.now()
        locked.snapshot_digest = snapshot_digest(_snapshot(locked))
        locked.version += 1
        locked.save()
        _audit(
            "academic.baseline.approved",
            request,
            locked,
            version=locked.version,
            effective_date=locked.effective_date.isoformat(),
            previous_id=str(locked.previous_id) if locked.previous_id else None,
            before_digest=before_digest,
            after_digest=locked.snapshot_digest,
        )
    else:
        raise ValidationError("Unknown baseline transition.")
    return cast(Baseline, locked)


@transaction.atomic
def request_correction(
    *,
    baseline: Baseline,
    institution: Institution,
    actor: Any,
    request: Any,
    reason: str,
) -> BaselineCorrection:
    require_permission(actor, BASELINE_CORRECT, institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        Baseline.objects.select_for_update(), pk=baseline.pk, institution=institution
    )
    if (
        locked.status != Baseline.Status.APPROVED
        or Baseline.objects.filter(previous=locked).exists()
        or BaselineCorrection.objects.filter(
            baseline=locked, status=BaselineCorrection.Status.PENDING
        ).exists()
    ):
        raise Conflict(
            "Only the latest approved baseline without an open correction may be corrected."
        )
    correction = BaselineCorrection.objects.create(
        institution=institution,
        baseline=locked,
        reason=reason,
        requested_by=actor,
    )
    _audit(
        "academic.baseline.correction.requested",
        request,
        locked,
        correction_id=str(correction.pk),
        before_digest=locked.snapshot_digest,
    )
    return correction


@transaction.atomic
def decide_correction(
    *,
    correction: BaselineCorrection,
    institution: Institution,
    actor: Any,
    request: Any,
    decision: str,
) -> BaselineCorrection:
    require_permission(actor, BASELINE_CORRECTION_AUTHORIZE, institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        BaselineCorrection.objects.select_for_update(),
        pk=correction.pk,
        institution=institution,
    )
    if locked.status != BaselineCorrection.Status.PENDING:
        raise Conflict("This correction has already been decided.")
    source = Baseline.objects.select_for_update().get(pk=locked.baseline_id)
    if not may_checker_approve(
        MakerCheckerContext(
            maker_id=str(locked.requested_by_id),
            checker_id=str(actor.pk),
            resource_type="academic.baseline.correction",
            resource_id=str(locked.pk),
            permission_code=BASELINE_CORRECTION_AUTHORIZE,
            scope_type="institution",
            scope_key=str(institution.pk),
        ),
        checker=actor,
        policy=_CorrectionPolicy(source),
    ):
        raise PermissionDenied("An independent correction authorizer is required.")
    if Baseline.objects.filter(previous=source).exists():
        raise Conflict("An approved baseline already has a successor.")
    locked.authorized_by = actor
    locked.resolved_at = timezone.now()
    if decision == "authorize":
        successor = Baseline.objects.create(
            institution=institution,
            candidate=source.candidate,
            academic_year=source.academic_year,
            previous=source,
            revision=source.revision + 1,
            effective_date=source.effective_date,
            source_date=source.source_date,
            source_label=source.source_label,
            created_by=locked.requested_by,
        )
        for row in source.observations.all():
            BaselineObservation.objects.create(
                baseline=successor,
                offering=row.offering,
                state=row.state,
                score=row.score,
                maximum_score=row.maximum_score,
            )
        locked.status = BaselineCorrection.Status.AUTHORIZED
        locked.successor = successor
        after_id = str(successor.pk)
    elif decision == "reject":
        locked.status = BaselineCorrection.Status.REJECTED
        after_id = None
    else:
        raise ValidationError("Unknown correction decision.")
    locked.save()
    _audit(
        "academic.baseline.correction.decided",
        request,
        source,
        correction_id=str(locked.pk),
        decision=locked.status,
        before_id=str(source.pk),
        after_id=after_id,
        before_digest=source.snapshot_digest,
    )
    return cast(BaselineCorrection, locked)
