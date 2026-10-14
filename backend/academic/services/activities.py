"""Weekly and mock source workflows with distinct review, approval and publication."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from academic.models import (
    AcademicActivity,
    AcademicMark,
    ActivityCorrection,
    ActivityEdit,
    ActivityParticipant,
    ActivitySubject,
    Candidate,
    MarkChange,
    ParticipationChange,
    validate_score,
)
from academic.permissions import ACTIVITY_PERMISSIONS
from academic.validation import (
    Conflict,
    active_placement,
    mock_role_authorized,
    offering_for,
    placement_context,
    require_permission,
    snapshot_digest,
    verify_version,
)
from identity.services.approvals import MakerCheckerContext, may_checker_approve
from identity.services.audit import record_audit_event
from identity.services.mfa import mfa_is_enabled
from institutional.models import Institution, SchoolClass, TeachingAssignment


def _audit(
    action: str, request: Any, activity: AcademicActivity, **metadata: object
) -> None:
    record_audit_event(
        action=f"academic.{activity.kind}.{action}",
        request=request,
        actor=request.user,
        subject_type="academic.activity",
        subject_id=str(activity.pk),
        metadata={
            "institution_id": str(activity.institution_id),
            "revision": activity.revision,
            **metadata,
        },
    )


def _require_role(actor: Any, institution: Institution, *, approver: bool) -> None:
    if not mock_role_authorized(actor, institution, approver=approver):
        raise PermissionDenied(
            "A configured, exact-institution mock authority is required."
        )
    if approver and (not actor.is_staff or not mfa_is_enabled(actor)):
        raise PermissionDenied(
            "Mock approval requires an MFA-enabled privileged account."
        )


def _require_mock_level(school_class: SchoolClass) -> None:
    """Use only an Owner-mapped Basic 9 level; names and positions are not policy."""

    approved_code = settings.ACADEMIC_BECE_LEVEL_CODE
    if not approved_code or school_class.level.code != approved_code:
        raise PermissionDenied(
            "A configured Basic 9 level mapping is required for BECE mock operations."
        )


def _context(
    institution: Institution, data: Mapping[str, Any]
) -> tuple[Any, Any, Any, TeachingAssignment | None]:
    year, school_class, stream = placement_context(
        institution,
        data["academic_year"],
        data["school_class"],
        data.get("stream"),
        data["scheduled_for"],
    )
    assignment = None
    if data.get("teacher_assignment"):
        assignment = get_object_or_404(
            TeachingAssignment,
            pk=data["teacher_assignment"],
            release_id=year.release_id,
            staff_membership__institution=institution,
        )
        if not (
            assignment.effective_from <= data["scheduled_for"]
            and (
                assignment.effective_until is None
                or data["scheduled_for"] <= assignment.effective_until
            )
            and assignment.staff_membership.effective_from <= data["scheduled_for"]
            and (
                assignment.staff_membership.effective_until is None
                or data["scheduled_for"] <= assignment.staff_membership.effective_until
            )
        ):
            raise ValidationError(
                {
                    "teacher_assignment": "Teacher affiliation must be active on the assessment date."
                }
            )
    return year, school_class, stream, assignment


def _blueprint(
    activity: AcademicActivity, rows: list[Mapping[str, Any]]
) -> list[tuple[Any, Any]]:
    seen_subjects: set[Any] = set()
    result = []
    for row in rows:
        offering = offering_for(
            row["offering"],
            activity.academic_year,
            activity.school_class,
            activity.stream,
            on_date=activity.scheduled_for,
        )
        if offering.subject_id in seen_subjects:
            raise ValidationError(
                {"subjects": "A subject may appear only once in a blueprint."}
            )
        seen_subjects.add(offering.subject_id)
        result.append((offering, row["maximum_score"]))
    if activity.kind == AcademicActivity.Kind.WEEKLY and (
        len(result) != 1
        or activity.teacher_assignment is None
        or activity.teacher_assignment.offering_id != result[0][0].pk
    ):
        raise ValidationError(
            {
                "subjects": "A weekly assessment must use its assigned teacher's one offering."
            }
        )
    return result


def _snapshot(activity: AcademicActivity) -> dict[str, Any]:
    subjects = list(activity.subjects.all())
    participants = list(activity.participants.all())
    marks = list(activity.marks.all())
    return {
        "kind": activity.kind,
        "year": str(activity.academic_year_id),
        "class": str(activity.school_class_id),
        "stream": str(activity.stream_id) if activity.stream_id else None,
        "teacher_assignment": str(activity.teacher_assignment_id)
        if activity.teacher_assignment_id
        else None,
        "scheduled_for": activity.scheduled_for.isoformat(),
        "title": activity.title,
        "assessment_type": activity.assessment_type,
        "subjects": sorted(
            (
                {"offering": str(s.offering_id), "maximum_score": str(s.maximum_score)}
                for s in subjects
            ),
            key=lambda item: item["offering"],
        ),
        "participants": sorted(
            (
                {
                    "candidate": str(p.candidate_id),
                    "eligible": p.eligible,
                    "participation": p.participation,
                }
                for p in participants
            ),
            key=lambda item: item["candidate"],
        ),
        "marks": sorted(
            (
                {
                    "candidate": str(m.participant.candidate_id),
                    "offering": str(m.subject.offering_id),
                    "state": m.state,
                    "score": str(m.score) if m.score is not None else None,
                }
                for m in marks
            ),
            key=lambda item: (item["candidate"], item["offering"]),
        ),
    }


def _check_quality(activity: AcademicActivity) -> tuple[int, int, int, int]:
    participants = list(activity.participants.all())
    marks = list(activity.marks.select_related("participant"))
    eligible = sum(p.eligible for p in participants)
    expected = sum(
        p.eligible and p.participation == ActivityParticipant.Participation.EXPECTED
        for p in participants
    )
    missing = sum(m.state == "missing" for m in marks)
    not_assessed = sum(m.state == "not_assessed" for m in marks)
    if not eligible or len(marks) != eligible * activity.subjects.count():
        raise Conflict(
            "An assessment needs an eligible roster and a mark state for each subject."
        )
    if any(
        m.participant.participation == "absent" and m.state == "scored" for m in marks
    ):
        raise Conflict("An absent participant cannot have a recorded score.")
    return eligible, expected, missing, not_assessed


@transaction.atomic
def create_activity(
    *,
    institution: Institution,
    actor: Any,
    request: Any,
    kind: str,
    data: Mapping[str, Any],
) -> AcademicActivity:
    require_permission(actor, ACTIVITY_PERMISSIONS[kind]["schedule"], institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    if kind == AcademicActivity.Kind.MOCK:
        _require_role(actor, institution, approver=False)
    year, school_class, stream, assignment = _context(institution, data)
    if kind == AcademicActivity.Kind.MOCK:
        _require_mock_level(school_class)
    activity = AcademicActivity.objects.create(
        institution=institution,
        kind=kind,
        academic_year=year,
        school_class=school_class,
        stream=stream,
        teacher_assignment=assignment,
        scheduled_for=data["scheduled_for"],
        title=data["title"],
        assessment_type=data.get("assessment_type", ""),
        created_by=actor,
    )
    blueprint = _blueprint(activity, data["subjects"])
    for offering, maximum in blueprint:
        ActivitySubject.objects.create(
            activity=activity, offering=offering, maximum_score=maximum
        )
    _audit(
        "scheduled",
        request,
        activity,
        subjects=len(blueprint),
        scheduled_for=activity.scheduled_for.isoformat(),
    )
    return activity


@transaction.atomic
def patch_activity(
    *,
    activity: AcademicActivity,
    institution: Institution,
    actor: Any,
    request: Any,
    data: Mapping[str, Any],
) -> AcademicActivity:
    require_permission(
        actor, ACTIVITY_PERMISSIONS[activity.kind]["schedule"], institution
    )
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        AcademicActivity.objects.select_for_update(),
        pk=activity.pk,
        institution=institution,
    )
    verify_version(locked, data["expected_version"])
    if locked.kind == AcademicActivity.Kind.MOCK:
        _require_role(actor, institution, approver=False)
        _require_mock_level(locked.school_class)
    if locked.status != AcademicActivity.Status.DRAFT or locked.participants.exists():
        raise Conflict("Schedule changes require a draft with no candidate entries.")
    before = _snapshot(locked)
    for field in ("scheduled_for", "title", "assessment_type"):
        if field in data:
            setattr(locked, field, data[field])
    locked.full_clean()
    _context(
        institution,
        {
            "academic_year": locked.academic_year_id,
            "school_class": locked.school_class_id,
            "stream": locked.stream_id,
            "scheduled_for": locked.scheduled_for,
            "teacher_assignment": locked.teacher_assignment_id,
        },
    )
    for subject in locked.subjects.all():
        offering_for(
            subject.offering_id,
            locked.academic_year,
            locked.school_class,
            locked.stream,
            on_date=locked.scheduled_for,
        )
    after = _snapshot(locked)
    if before == after:
        raise ValidationError("Nothing changed.")
    locked.version += 1
    locked.save()
    ActivityEdit.objects.create(
        activity=locked,
        version=locked.version,
        before=before,
        after=after,
        reason=data["reason"],
        actor=actor,
    )
    _audit(
        "schedule.edited",
        request,
        locked,
        version=locked.version,
        before_digest=snapshot_digest(before),
        after_digest=snapshot_digest(after),
    )
    return cast(AcademicActivity, locked)


@transaction.atomic
def upsert_participants(
    *,
    activity: AcademicActivity,
    institution: Institution,
    actor: Any,
    request: Any,
    entries: list[Mapping[str, Any]],
    expected_activity_version: int,
) -> AcademicActivity:
    require_permission(
        actor, ACTIVITY_PERMISSIONS[activity.kind]["schedule"], institution
    )
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        AcademicActivity.objects.select_for_update(),
        pk=activity.pk,
        institution=institution,
    )
    verify_version(locked, expected_activity_version)
    if locked.kind == AcademicActivity.Kind.MOCK:
        _require_role(actor, institution, approver=False)
        _require_mock_level(locked.school_class)
    if locked.status != AcademicActivity.Status.DRAFT:
        raise Conflict("Only draft rosters may be edited.")
    if len({entry["candidate"] for entry in entries}) != len(entries):
        raise ValidationError({"entries": "A candidate appears more than once."})
    actions = []
    for entry in entries:
        candidate = get_object_or_404(
            Candidate, pk=entry["candidate"], institution=institution
        )
        active_placement(
            candidate,
            locked.academic_year,
            locked.school_class,
            locked.stream,
            locked.scheduled_for,
        )
        if entry["eligible"] and candidate.status != Candidate.Status.ACTIVE:
            raise ValidationError(
                {"eligible": "Only active identities can be marked eligible."}
            )
        if not entry["eligible"] and entry["participation"] != "not_assessed":
            raise ValidationError(
                {"participation": "Ineligible candidates must be not assessed."}
            )
        current = (
            ActivityParticipant.objects.select_for_update()
            .filter(activity=locked, candidate=candidate)
            .first()
        )
        if current:
            if "expected_version" not in entry or "reason" not in entry:
                raise ValidationError(
                    {"entries": "Updating a participant requires a version and reason."}
                )
            verify_version(current, entry["expected_version"])
            if current.eligible and not entry["eligible"]:
                raise Conflict(
                    "A roster entry with mark history cannot become ineligible."
                )
        elif "expected_version" in entry:
            raise Conflict(
                "This candidate is not yet in the roster; refresh before editing."
            )
        actions.append((candidate, current, entry))
    for candidate, current, entry in actions:
        if current is None:
            participant = ActivityParticipant.objects.create(
                activity=locked,
                candidate=candidate,
                eligible=entry["eligible"],
                participation=entry["participation"],
            )
            if participant.eligible:
                for subject in locked.subjects.all():
                    AcademicMark.objects.create(
                        activity=locked, subject=subject, participant=participant
                    )
        else:
            before = {
                "eligible": current.eligible,
                "participation": current.participation,
            }
            current.eligible = entry["eligible"]
            current.participation = entry["participation"]
            after = {
                "eligible": current.eligible,
                "participation": current.participation,
            }
            if before == after:
                raise ValidationError("Nothing changed for an existing participant.")
            current.version += 1
            current.save()
            if not before["eligible"] and current.eligible:
                for subject in locked.subjects.all():
                    AcademicMark.objects.create(
                        activity=locked, subject=subject, participant=current
                    )
            ParticipationChange.objects.create(
                participant=current,
                version=current.version,
                before=before,
                after=after,
                reason=entry["reason"],
                actor=actor,
            )
    locked.version += 1
    locked.save()
    _audit(
        "roster.edited",
        request,
        locked,
        entries=len(entries),
        version=locked.version,
        eligible=sum(bool(entry["eligible"]) for entry in entries),
    )
    return cast(AcademicActivity, locked)


def _may_enter(
    actor: Any,
    activity: AcademicActivity,
    subject: ActivitySubject,
    institution: Institution,
) -> bool:
    if activity.kind == AcademicActivity.Kind.WEEKLY:
        assignment = activity.teacher_assignment
        return bool(assignment and assignment.staff_membership.user_id == actor.pk)
    if mock_role_authorized(actor, institution, approver=False):
        return True
    return (
        TeachingAssignment.objects.filter(
            offering=subject.offering,
            staff_membership__user=actor,
            staff_membership__institution=institution,
            effective_from__lte=activity.scheduled_for,
            staff_membership__effective_from__lte=activity.scheduled_for,
        )
        .filter(
            Q(effective_until__isnull=True)
            | Q(effective_until__gte=activity.scheduled_for)
        )
        .filter(
            Q(staff_membership__effective_until__isnull=True)
            | Q(staff_membership__effective_until__gte=activity.scheduled_for)
        )
        .exists()
    )


@transaction.atomic
def enter_marks(
    *,
    activity: AcademicActivity,
    institution: Institution,
    actor: Any,
    request: Any,
    entries: list[Mapping[str, Any]],
    expected_activity_version: int,
) -> AcademicActivity:
    require_permission(actor, ACTIVITY_PERMISSIONS[activity.kind]["enter"], institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        AcademicActivity.objects.select_for_update(),
        pk=activity.pk,
        institution=institution,
    )
    verify_version(locked, expected_activity_version)
    if locked.kind == AcademicActivity.Kind.MOCK:
        _require_mock_level(locked.school_class)
    if locked.status != AcademicActivity.Status.DRAFT:
        raise Conflict(
            "Only draft marks may be edited; request a correction for approved results."
        )
    if len({(row["participant"], row["subject"]) for row in entries}) != len(entries):
        raise ValidationError(
            {"marks": "A candidate-subject cell appears more than once."}
        )
    actions = []
    for row in entries:
        mark = get_object_or_404(
            AcademicMark.objects.select_for_update().select_related(
                "subject__offering", "participant"
            ),
            activity=locked,
            subject_id=row["subject"],
            participant_id=row["participant"],
        )
        verify_version(mark, row["expected_version"])
        if not _may_enter(actor, locked, mark.subject, institution):
            raise PermissionDenied(
                "Mark entry requires the active subject teacher or configured mock preparer."
            )
        state, score = row["state"], row.get("score")
        validate_score(state, score, mark.subject.maximum_score)
        if mark.participant.participation == "absent" and state == "scored":
            raise ValidationError(
                {"marks": "An absent participant cannot receive a score."}
            )
        if mark.state == state and mark.score == score:
            raise ValidationError({"marks": "Nothing changed in an entered cell."})
        actions.append((mark, state, score))
    for mark, state, score in actions:
        before_state, before_score = mark.state, mark.score
        mark.state, mark.score, mark.recorded_by = state, score, actor
        mark.version += 1
        mark.save()
        MarkChange.objects.create(
            mark=mark,
            version=mark.version,
            before_state=before_state,
            before_score=before_score,
            after_state=state,
            after_score=score,
            actor=actor,
        )
        _audit(
            "mark.edited",
            request,
            locked,
            mark_id=str(mark.pk),
            version=mark.version,
            before_state=before_state,
            after_state=state,
        )
    locked.version += 1
    locked.save()
    return cast(AcademicActivity, locked)


class _ModeratedPolicy:
    def __init__(self, activity: AcademicActivity) -> None:
        self.activity = activity

    def may_check(self, context: MakerCheckerContext) -> bool:
        return (
            self.activity.status == AcademicActivity.Status.MODERATED
            and context.checker_id
            not in {
                str(self.activity.submitted_by_id),
                str(self.activity.moderated_by_id),
            }
            and not MarkChange.objects.filter(
                mark__activity=self.activity, actor_id=int(context.checker_id)
            ).exists()
            and not AcademicMark.objects.filter(
                activity=self.activity, recorded_by_id=int(context.checker_id)
            ).exists()
            and not ParticipationChange.objects.filter(
                participant__activity=self.activity, actor_id=int(context.checker_id)
            ).exists()
        )


class _CorrectionPolicy:
    def __init__(self, activity: AcademicActivity) -> None:
        self.activity = activity

    def may_check(self, context: MakerCheckerContext) -> bool:
        return self.activity.status in (
            AcademicActivity.Status.APPROVED,
            AcademicActivity.Status.PUBLISHED,
        )


@transaction.atomic
def transition_activity(
    *,
    activity: AcademicActivity,
    institution: Institution,
    actor: Any,
    request: Any,
    action: str,
    expected_version: int,
    reason: str = "",
) -> AcademicActivity:
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        AcademicActivity.objects.select_for_update(),
        pk=activity.pk,
        institution=institution,
    )
    verify_version(locked, expected_version)
    if locked.kind == AcademicActivity.Kind.MOCK:
        _require_mock_level(locked.school_class)
    perms = ACTIVITY_PERMISSIONS[locked.kind]
    before = {"status": locked.status, "version": locked.version}
    if action == "submit":
        require_permission(actor, perms["schedule"], institution)
        if locked.kind == AcademicActivity.Kind.MOCK:
            _require_role(actor, institution, approver=False)
        if locked.status != AcademicActivity.Status.DRAFT:
            raise Conflict("Only draft events can be submitted.")
        eligible, expected, missing, unassessed = _check_quality(locked)
        locked.status = AcademicActivity.Status.SUBMITTED
        locked.submitted_by, locked.submitted_at = actor, timezone.now()
    elif action in ("moderate", "return"):
        require_permission(actor, perms["review"], institution)
        allowed = (
            (AcademicActivity.Status.SUBMITTED, AcademicActivity.Status.MODERATED)
            if action == "return"
            else (AcademicActivity.Status.SUBMITTED,)
        )
        if locked.status not in allowed:
            raise Conflict("Only submitted or moderated results may be reviewed.")
        if (
            actor.pk in (locked.created_by_id, locked.submitted_by_id)
            or MarkChange.objects.filter(mark__activity=locked, actor=actor).exists()
            or AcademicMark.objects.filter(activity=locked, recorded_by=actor).exists()
            or ParticipationChange.objects.filter(
                participant__activity=locked, actor=actor
            ).exists()
        ):
            raise PermissionDenied(
                "Data entry and independent review must be separate."
            )
        if action == "moderate":
            if locked.status != AcademicActivity.Status.SUBMITTED:
                raise Conflict("This event has already been moderated.")
            locked.status = AcademicActivity.Status.MODERATED
            locked.moderated_by, locked.moderated_at = actor, timezone.now()
        else:
            if not reason:
                raise ValidationError({"reason": "A return requires a reason."})
            locked.status = AcademicActivity.Status.DRAFT
            locked.moderated_by, locked.moderated_at = None, None
        eligible, expected, missing, unassessed = _check_quality(locked)
    elif action == "approve":
        require_permission(actor, perms["approve"], institution)
        if locked.kind == AcademicActivity.Kind.MOCK:
            _require_role(actor, institution, approver=True)
        if not may_checker_approve(
            MakerCheckerContext(
                maker_id=str(locked.created_by_id),
                checker_id=str(actor.pk),
                resource_type=f"academic.{locked.kind}",
                resource_id=str(locked.pk),
                permission_code=perms["approve"],
                scope_type="institution",
                scope_key=str(institution.pk),
            ),
            checker=actor,
            policy=_ModeratedPolicy(locked),
        ):
            raise PermissionDenied(
                "Approval requires an independent reviewer and approved authority."
            )
        eligible, expected, missing, unassessed = _check_quality(locked)
        locked.status = AcademicActivity.Status.APPROVED
        locked.approved_by, locked.approved_at = actor, timezone.now()
        locked.snapshot_digest = snapshot_digest(_snapshot(locked))
    elif action == "publish":
        require_permission(actor, perms["publish"], institution)
        if locked.kind == AcademicActivity.Kind.MOCK:
            _require_role(actor, institution, approver=True)
        if locked.status != AcademicActivity.Status.APPROVED:
            raise Conflict("Only approved results may be published.")
        eligible, expected, missing, unassessed = _check_quality(locked)
        if expected or missing or unassessed:
            raise Conflict(
                "Incomplete results cannot be published; resolve missing and not-assessed states first."
            )
        locked.status = AcademicActivity.Status.PUBLISHED
        locked.published_by, locked.published_at = actor, timezone.now()
    else:
        raise ValidationError("Unknown event transition.")
    locked.version += 1
    locked.save()
    if action == "return":
        ActivityEdit.objects.create(
            activity=locked,
            version=locked.version,
            before=before,
            after={"status": locked.status, "version": locked.version},
            reason=reason,
            actor=actor,
        )
    _audit(
        action if action != "return" else "returned",
        request,
        locked,
        version=locked.version,
        eligible=eligible,
        expected=expected,
        missing=missing,
        not_assessed=unassessed,
        before_digest=locked.previous.snapshot_digest
        if action == "approve" and locked.previous_id
        else None,
        after_digest=locked.snapshot_digest if action == "approve" else None,
    )
    return cast(AcademicActivity, locked)


@transaction.atomic
def request_correction(
    *,
    activity: AcademicActivity,
    institution: Institution,
    actor: Any,
    request: Any,
    reason: str,
) -> ActivityCorrection:
    require_permission(
        actor, ACTIVITY_PERMISSIONS[activity.kind]["correct"], institution
    )
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        AcademicActivity.objects.select_for_update(),
        pk=activity.pk,
        institution=institution,
    )
    if locked.kind == AcademicActivity.Kind.MOCK:
        _require_role(actor, institution, approver=False)
        _require_mock_level(locked.school_class)
    if (
        locked.status
        not in (AcademicActivity.Status.APPROVED, AcademicActivity.Status.PUBLISHED)
        or AcademicActivity.objects.filter(previous=locked).exists()
        or ActivityCorrection.objects.filter(
            activity=locked, status=ActivityCorrection.Status.PENDING
        ).exists()
    ):
        raise Conflict(
            "Only the latest approved result without an open correction can be revised."
        )
    correction = ActivityCorrection.objects.create(
        institution=institution,
        activity=locked,
        reason=reason,
        requested_by=actor,
    )
    _audit(
        "correction.requested",
        request,
        locked,
        correction_id=str(correction.pk),
        before_digest=locked.snapshot_digest,
    )
    return correction


@transaction.atomic
def decide_correction(
    *,
    correction: ActivityCorrection,
    institution: Institution,
    actor: Any,
    request: Any,
    decision: str,
) -> ActivityCorrection:
    source = get_object_or_404(
        AcademicActivity, pk=correction.activity_id, institution=institution
    )
    require_permission(
        actor, ACTIVITY_PERMISSIONS[source.kind]["authorize"], institution
    )
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        ActivityCorrection.objects.select_for_update(),
        pk=correction.pk,
        institution=institution,
    )
    if locked.status != ActivityCorrection.Status.PENDING:
        raise Conflict("This correction has already been decided.")
    source = AcademicActivity.objects.select_for_update().get(pk=locked.activity_id)
    if source.kind == AcademicActivity.Kind.MOCK:
        _require_role(actor, institution, approver=True)
        _require_mock_level(source.school_class)
    if not may_checker_approve(
        MakerCheckerContext(
            maker_id=str(locked.requested_by_id),
            checker_id=str(actor.pk),
            resource_type=f"academic.{source.kind}.correction",
            resource_id=str(locked.pk),
            permission_code=ACTIVITY_PERMISSIONS[source.kind]["authorize"],
            scope_type="institution",
            scope_key=str(institution.pk),
        ),
        checker=actor,
        policy=_CorrectionPolicy(source),
    ):
        raise PermissionDenied("An independent correction authorizer is required.")
    if AcademicActivity.objects.filter(previous=source).exists():
        raise Conflict("An approved result already has a successor.")
    locked.authorized_by, locked.resolved_at = actor, timezone.now()
    if decision == "authorize":
        successor = AcademicActivity.objects.create(
            institution=institution,
            kind=source.kind,
            academic_year=source.academic_year,
            school_class=source.school_class,
            stream=source.stream,
            teacher_assignment=source.teacher_assignment,
            scheduled_for=source.scheduled_for,
            title=source.title,
            assessment_type=source.assessment_type,
            revision=source.revision + 1,
            previous=source,
            created_by=locked.requested_by,
        )
        subjects = {}
        for subject in source.subjects.all():
            subjects[subject.pk] = ActivitySubject.objects.create(
                activity=successor,
                offering=subject.offering,
                maximum_score=subject.maximum_score,
            )
        participants = {}
        for participant in source.participants.all():
            participants[participant.pk] = ActivityParticipant.objects.create(
                activity=successor,
                candidate=participant.candidate,
                eligible=participant.eligible,
                participation=participant.participation,
            )
        for mark in source.marks.all():
            AcademicMark.objects.create(
                activity=successor,
                subject=subjects[mark.subject_id],
                participant=participants[mark.participant_id],
                state=mark.state,
                score=mark.score,
                recorded_by=mark.recorded_by,
            )
        locked.status, locked.successor = (
            ActivityCorrection.Status.AUTHORIZED,
            successor,
        )
        after_id = str(successor.pk)
    elif decision == "reject":
        locked.status = ActivityCorrection.Status.REJECTED
        after_id = None
    else:
        raise ValidationError("Unknown correction decision.")
    locked.save()
    _audit(
        "correction.decided",
        request,
        source,
        correction_id=str(locked.pk),
        decision=locked.status,
        before_id=str(source.pk),
        after_id=after_id,
        before_digest=source.snapshot_digest,
    )
    return cast(ActivityCorrection, locked)
