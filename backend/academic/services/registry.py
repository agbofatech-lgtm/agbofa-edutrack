"""Candidate and guardian changes are transactional and retain local evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from academic.models import (
    ActivityParticipant,
    Baseline,
    Candidate,
    CandidateChange,
    CandidateImport,
    CandidatePlacement,
    Guardian,
    GuardianChange,
    GuardianLink,
    GuardianLinkChange,
)
from academic.permissions import (
    CANDIDATE_IMPORT,
    CANDIDATE_READ,
    CANDIDATE_RECONCILE,
    CANDIDATE_WRITE,
    GUARDIAN_WRITE,
)
from academic.serializers import CandidateInput
from academic.validation import (
    Conflict,
    candidate_fingerprint,
    payload_digest,
    placement_context,
    require_permission,
    verify_version,
)
from identity.services.audit import record_audit_event
from institutional.models import Enrolment, Institution


def _audit(
    action: str,
    request: Any,
    subject: Any,
    institution: Institution,
    **metadata: object,
) -> None:
    record_audit_event(
        action=action,
        request=request,
        actor=request.user,
        subject_type=f"academic.{subject._meta.model_name}",
        subject_id=str(subject.pk),
        metadata={"institution_id": str(institution.pk), **metadata},
    )


def _candidate_snapshot(candidate: Candidate) -> dict[str, Any]:
    return {
        "given_name": candidate.given_name,
        "family_name": candidate.family_name,
        "birth_date": candidate.birth_date.isoformat()
        if candidate.birth_date
        else None,
        "status": candidate.status,
        "canonical_candidate": str(candidate.canonical_candidate_id)
        if candidate.canonical_candidate_id
        else None,
    }


def _guardian_snapshot(guardian: Guardian) -> dict[str, str]:
    return {"name": guardian.name, "phone": guardian.phone, "email": guardian.email}


def _link_snapshot(link: GuardianLink) -> dict[str, Any]:
    return {
        "relationship": link.relationship,
        "contact_authorized": link.contact_authorized,
        "is_active": link.is_active,
    }


def _placement(
    *,
    candidate: Candidate,
    actor: Any,
    institution: Institution,
    data: Mapping[str, Any],
) -> CandidatePlacement:
    year, school_class, stream = placement_context(
        institution,
        data["academic_year"],
        data["school_class"],
        data.get("stream"),
        data["effective_from"],
    )
    if (
        CandidatePlacement.objects.filter(
            candidate=candidate,
            enrolment__academic_year=year,
        )
        .filter(
            Q(enrolment__effective_until__isnull=True)
            | Q(enrolment__effective_until__gte=data["effective_from"])
        )
        .exists()
    ):
        raise Conflict(
            "Placement dates in this year must not overlap; close any open placement first."
        )
    enrolment = Enrolment.objects.create(
        institution=institution,
        learner_reference=candidate.pk,
        academic_year=year,
        school_class=school_class,
        stream=stream,
        effective_from=data["effective_from"],
        created_by=actor,
    )
    return CandidatePlacement.objects.create(
        institution=institution, candidate=candidate, enrolment=enrolment
    )


@transaction.atomic
def create_candidate(
    *,
    institution: Institution,
    actor: Any,
    request: Any,
    data: Mapping[str, Any],
    import_batch: CandidateImport | None = None,
) -> Candidate:
    require_permission(
        actor,
        CANDIDATE_IMPORT if import_batch is not None else CANDIDATE_WRITE,
        institution,
    )
    Institution.objects.select_for_update().get(pk=institution.pk)
    fingerprint = candidate_fingerprint(
        data["given_name"], data["family_name"], data.get("birth_date")
    )
    if Candidate.objects.filter(
        institution=institution, identity_fingerprint=fingerprint
    ).exists():
        raise Conflict(
            "This identity matches an existing candidate. Review and reconcile before creating another."
        )
    candidate = Candidate.objects.create(
        institution=institution,
        given_name=data["given_name"],
        family_name=data["family_name"],
        birth_date=data.get("birth_date"),
        identity_fingerprint=fingerprint,
        created_by=actor,
        import_batch=import_batch,
    )
    placement = _placement(
        candidate=candidate, actor=actor, institution=institution, data=data
    )
    _audit(
        "academic.candidate.created",
        request,
        candidate,
        institution,
        placement_id=str(placement.pk),
        imported=import_batch is not None,
    )
    return candidate


@transaction.atomic
def add_placement(
    *,
    candidate: Candidate,
    institution: Institution,
    actor: Any,
    request: Any,
    data: Mapping[str, Any],
) -> CandidatePlacement:
    require_permission(actor, CANDIDATE_WRITE, institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    candidate = get_object_or_404(
        Candidate.objects.select_for_update(), pk=candidate.pk, institution=institution
    )
    if candidate.status != Candidate.Status.ACTIVE:
        raise Conflict("Only active candidates can receive a new placement.")
    placement = _placement(
        candidate=candidate, actor=actor, institution=institution, data=data
    )
    _audit(
        "academic.candidate.placement.created",
        request,
        candidate,
        institution,
        placement_id=str(placement.pk),
    )
    return placement


@transaction.atomic
def patch_candidate(
    *,
    candidate: Candidate,
    institution: Institution,
    actor: Any,
    request: Any,
    data: Mapping[str, Any],
) -> Candidate:
    require_permission(actor, CANDIDATE_WRITE, institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        Candidate.objects.select_for_update(), pk=candidate.pk, institution=institution
    )
    verify_version(locked, data["expected_version"])
    if locked.status == Candidate.Status.DUPLICATE:
        raise Conflict("Reconciled identities are historical and cannot be edited.")
    before = _candidate_snapshot(locked)
    for field in ("given_name", "family_name", "birth_date", "status"):
        if field in data:
            setattr(locked, field, data[field])
    fingerprint = candidate_fingerprint(
        locked.given_name, locked.family_name, locked.birth_date
    )
    if (
        Candidate.objects.filter(
            institution=institution, identity_fingerprint=fingerprint
        )
        .exclude(pk=locked.pk)
        .exists()
    ):
        raise Conflict(
            "This identity matches another candidate. Review and reconcile instead."
        )
    locked.identity_fingerprint = fingerprint
    after = _candidate_snapshot(locked)
    if before == after:
        raise ValidationError("Nothing changed.")
    locked.version += 1
    locked.save()
    CandidateChange.objects.create(
        candidate=locked,
        version=locked.version,
        before=before,
        after=after,
        actor=actor,
        reason=data["reason"],
    )
    _audit(
        "academic.candidate.corrected",
        request,
        locked,
        institution,
        version=locked.version,
        fields=sorted(key for key in before if before[key] != after[key]),
    )
    return cast(Candidate, locked)


@transaction.atomic
def reconcile_candidate(
    *,
    candidate: Candidate,
    institution: Institution,
    actor: Any,
    request: Any,
    data: Mapping[str, Any],
) -> Candidate:
    require_permission(actor, CANDIDATE_RECONCILE, institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        Candidate.objects.select_for_update(), pk=candidate.pk, institution=institution
    )
    verify_version(locked, data["expected_version"])
    if locked.status == Candidate.Status.DUPLICATE:
        raise Conflict(
            "Candidate already reconciled. Historical records cannot be retargeted."
        )
    if (
        Baseline.objects.filter(candidate=locked).exists()
        or ActivityParticipant.objects.filter(candidate=locked).exists()
    ):
        raise Conflict(
            "Reconciliation with academic evidence requires a separately approved historical data policy."
        )
    canonical = get_object_or_404(
        Candidate,
        pk=data["canonical_candidate"],
        institution=institution,
        status=Candidate.Status.ACTIVE,
    )
    if canonical.pk == locked.pk:
        raise ValidationError({"canonical_candidate": "Choose a different candidate."})
    before = _candidate_snapshot(locked)
    locked.status = Candidate.Status.DUPLICATE
    locked.canonical_candidate = canonical
    locked.version += 1
    locked.save()
    CandidateChange.objects.create(
        candidate=locked,
        version=locked.version,
        before=before,
        after=_candidate_snapshot(locked),
        actor=actor,
        reason=data["reason"],
    )
    _audit(
        "academic.candidate.reconciled",
        request,
        locked,
        institution,
        version=locked.version,
        canonical_candidate_id=str(canonical.pk),
    )
    return cast(Candidate, locked)


def _preview_rows(
    rows: list[Any], institution: Institution
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validated: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for number, row in enumerate(rows, 1):
        serializer = CandidateInput(data=row)
        if not serializer.is_valid():
            errors.append({"row": number, "errors": serializer.errors})
            continue
        data = serializer.validated_data
        fingerprint = candidate_fingerprint(
            data["given_name"], data["family_name"], data.get("birth_date")
        )
        if (
            fingerprint in seen
            or Candidate.objects.filter(
                institution=institution, identity_fingerprint=fingerprint
            ).exists()
        ):
            errors.append(
                {
                    "row": number,
                    "errors": {
                        "identity": [
                            "Possible duplicate; review existing candidates before importing."
                        ]
                    },
                }
            )
            continue
        seen.add(fingerprint)
        try:
            placement_context(
                institution,
                data["academic_year"],
                data["school_class"],
                data.get("stream"),
                data["effective_from"],
            )
        except ValidationError as error:
            errors.append({"row": number, "errors": error.detail})
            continue
        validated.append(data)
    return validated, errors


@transaction.atomic
def preview_import(
    *, institution: Institution, actor: Any, request: Any, data: Mapping[str, Any]
) -> tuple[CandidateImport, list[dict[str, Any]]]:
    Institution.objects.select_for_update().get(pk=institution.pk)
    rows = data["rows"]
    digest = payload_digest(rows)
    batch = (
        CandidateImport.objects.select_for_update()
        .filter(institution=institution, idempotency_key=data["idempotency_key"])
        .first()
    )
    if batch is not None:
        if batch.actor_id != actor.pk:
            raise PermissionDenied("Import keys belong to their original operator.")
        if batch.payload_digest != digest or batch.row_count != len(rows):
            raise Conflict(
                "This import key has already been used for a different submission."
            )
        _, errors = _preview_rows(rows, institution)
        return batch, errors
    _, errors = _preview_rows(rows, institution)
    batch = CandidateImport.objects.create(
        institution=institution,
        actor=actor,
        idempotency_key=data["idempotency_key"],
        payload_digest=digest,
        row_count=len(rows),
        error_count=len(errors),
    )
    _audit(
        "academic.candidate.import.previewed",
        request,
        batch,
        institution,
        rows=len(rows),
        errors=len(errors),
    )
    return batch, errors


@transaction.atomic
def apply_import(
    *,
    institution: Institution,
    actor: Any,
    request: Any,
    batch: CandidateImport,
    data: Mapping[str, Any],
) -> tuple[list[Candidate], bool]:
    require_permission(actor, CANDIDATE_IMPORT, institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        CandidateImport.objects.select_for_update(),
        pk=batch.pk,
        institution=institution,
    )
    if locked.actor_id != actor.pk:
        raise PermissionDenied("Only the previewing operator can apply this import.")
    if (
        locked.idempotency_key != data["idempotency_key"]
        or locked.payload_digest != payload_digest(data["rows"])
        or locked.row_count != len(data["rows"])
    ):
        raise Conflict("Import submission does not match its validated preview.")
    if locked.status == CandidateImport.Status.APPLIED:
        return list(
            Candidate.objects.filter(import_batch=locked).order_by("created_at", "pk")
        ), False
    if locked.error_count:
        raise Conflict("Resolve the preview errors and start a new import key.")
    valid_rows, errors = _preview_rows(data["rows"], institution)
    if errors:
        raise Conflict(
            {"detail": "Import is stale; no candidates were created.", "errors": errors}
        )
    created = [
        create_candidate(
            institution=institution,
            actor=actor,
            request=request,
            data=row,
            import_batch=locked,
        )
        for row in valid_rows
    ]
    locked.status = CandidateImport.Status.APPLIED
    locked.applied_at = timezone.now()
    locked.save(update_fields=["status", "applied_at"])
    _audit(
        "academic.candidate.import.applied",
        request,
        locked,
        institution,
        rows=len(created),
    )
    return created, True


@transaction.atomic
def create_guardian(
    *, institution: Institution, actor: Any, request: Any, data: Mapping[str, Any]
) -> Guardian:
    require_permission(actor, GUARDIAN_WRITE, institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    guardian = Guardian.objects.create(
        institution=institution, created_by=actor, **data
    )
    _audit("academic.guardian.created", request, guardian, institution)
    return guardian


@transaction.atomic
def patch_guardian(
    *,
    guardian: Guardian,
    institution: Institution,
    actor: Any,
    request: Any,
    data: Mapping[str, Any],
) -> Guardian:
    require_permission(actor, GUARDIAN_WRITE, institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        Guardian.objects.select_for_update(), pk=guardian.pk, institution=institution
    )
    verify_version(locked, data["expected_version"])
    before = _guardian_snapshot(locked)
    for field in ("name", "phone", "email"):
        if field in data:
            setattr(locked, field, data[field])
    after = _guardian_snapshot(locked)
    if before == after:
        raise ValidationError("Nothing changed.")
    locked.version += 1
    locked.save()
    GuardianChange.objects.create(
        guardian=locked,
        version=locked.version,
        before=before,
        after=after,
        actor=actor,
        reason=data["reason"],
    )
    _audit(
        "academic.guardian.corrected",
        request,
        locked,
        institution,
        version=locked.version,
        fields=sorted(key for key in before if before[key] != after[key]),
    )
    return cast(Guardian, locked)


@transaction.atomic
def create_link(
    *,
    candidate: Candidate,
    institution: Institution,
    actor: Any,
    request: Any,
    data: Mapping[str, Any],
) -> GuardianLink:
    require_permission(actor, GUARDIAN_WRITE, institution)
    require_permission(actor, CANDIDATE_READ, institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    candidate = get_object_or_404(Candidate, pk=candidate.pk, institution=institution)
    guardian = get_object_or_404(Guardian, pk=data["guardian"], institution=institution)
    if GuardianLink.objects.filter(candidate=candidate, guardian=guardian).exists():
        raise Conflict(
            "This relationship already exists; update its recorded history instead."
        )
    link = GuardianLink.objects.create(
        institution=institution,
        candidate=candidate,
        guardian=guardian,
        relationship=data["relationship"],
        contact_authorized=data["contact_authorized"],
        created_by=actor,
    )
    _audit(
        "academic.guardian.link.created",
        request,
        link,
        institution,
        candidate_id=str(candidate.pk),
        guardian_id=str(guardian.pk),
    )
    return link


@transaction.atomic
def patch_link(
    *,
    link: GuardianLink,
    institution: Institution,
    actor: Any,
    request: Any,
    data: Mapping[str, Any],
) -> GuardianLink:
    require_permission(actor, GUARDIAN_WRITE, institution)
    require_permission(actor, CANDIDATE_READ, institution)
    Institution.objects.select_for_update().get(pk=institution.pk)
    locked = get_object_or_404(
        GuardianLink.objects.select_for_update(), pk=link.pk, institution=institution
    )
    verify_version(locked, data["expected_version"])
    before = _link_snapshot(locked)
    for field in ("relationship", "contact_authorized", "is_active"):
        if field in data:
            setattr(locked, field, data[field])
    after = _link_snapshot(locked)
    if before == after:
        raise ValidationError("Nothing changed.")
    locked.version += 1
    locked.save()
    GuardianLinkChange.objects.create(
        link=locked,
        version=locked.version,
        before=before,
        after=after,
        actor=actor,
        reason=data["reason"],
    )
    _audit(
        "academic.guardian.link.corrected",
        request,
        locked,
        institution,
        version=locked.version,
        fields=sorted(key for key in before if before[key] != after[key]),
        candidate_id=str(locked.candidate_id),
    )
    return cast(GuardianLink, locked)
