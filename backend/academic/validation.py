"""Shared validation and scoped workflow primitives for Phase 04."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import unicodedata
from datetime import date
from typing import Any, cast

from django.conf import settings
from django.core.exceptions import (
    PermissionDenied,
)
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from academic.models import Candidate, CandidatePlacement
from identity.models import ScopeGrant
from identity.services.rbac import user_has_permission
from institutional.models import (
    AcademicYear,
    ConfigurationRelease,
    Institution,
    SchoolClass,
    Stream,
    SubjectOffering,
)


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This record has changed. Reload it before trying again."
    default_code = "conflict"


def as_api_error(error: DjangoValidationError) -> ValidationError:
    if hasattr(error, "message_dict"):
        return ValidationError(error.message_dict)
    return ValidationError(error.messages)


def verify_version(record: Any, expected_version: int) -> None:
    if record.version != expected_version:
        raise Conflict("This record has changed. Reload it before trying again.")


def require_permission(actor: Any, code: str, institution: Institution) -> None:
    if not user_has_permission(
        actor, code, scope_type="institution", scope_key=str(institution.pk)
    ):
        raise PermissionDenied(
            "This action requires an explicit institution-scoped permission."
        )


def mock_role_authorized(
    actor: Any, institution: Institution, *, approver: bool
) -> bool:
    """Fail closed without an Owner-approved role code and an exact tenant grant.

    A permission grant alone cannot stand in for the Headmaster or JHS Contact
    Person mapping. There is no default, fallback, or inferred delegated approver.
    """

    role_code = (
        settings.ACADEMIC_MOCK_APPROVER_ROLE_CODE
        if approver
        else settings.ACADEMIC_MOCK_PREPARER_ROLE_CODE
    )
    if not role_code or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", role_code):
        return False
    now = timezone.now()
    grants = ScopeGrant.objects.filter(
        user=actor,
        is_active=True,
        role__is_active=True,
        role__code=role_code,
        scope_type="institution",
        scope_key=str(institution.pk),
        valid_from__lte=now,
    ).filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now))
    return grants.exists()


def canonical_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).strip()


def candidate_fingerprint(given: str, family: str, birth_date: date | None) -> str:
    # An HMAC, not a bare dictionary-attackable digest. Re-keying requires a
    # controlled re-indexing plan; no identity key is sent to the client/audit.
    raw = "\x1f".join(
        (
            canonical_name(given).casefold(),
            canonical_name(family).casefold(),
            birth_date.isoformat() if birth_date else "unknown",
        )
    )
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def payload_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hmac.new(settings.SECRET_KEY.encode(), encoded, hashlib.sha256).hexdigest()


def snapshot_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def placement_context(
    institution: Institution,
    year_id: Any,
    school_class_id: Any,
    stream_id: Any,
    on_date: date,
) -> tuple[AcademicYear, SchoolClass, Stream | None]:
    year = AcademicYear.objects.filter(
        pk=year_id,
        release__institution=institution,
        release__status=ConfigurationRelease.Status.APPROVED,
    ).first()
    if year is None or not year.start_date <= on_date <= year.end_date:
        raise ValidationError(
            {
                "academic_year": "Select an approved year covering this date in this institution."
            }
        )
    school_class = SchoolClass.objects.filter(
        pk=school_class_id, release_id=year.release_id
    ).first()
    if school_class is None:
        raise ValidationError(
            {"school_class": "Select a class in the approved year revision."}
        )
    stream = None
    if stream_id is not None:
        stream = Stream.objects.filter(pk=stream_id, school_class=school_class).first()
        if stream is None:
            raise ValidationError({"stream": "Select a stream in this class."})
    return year, school_class, stream


def active_placement(
    candidate: Candidate,
    year: AcademicYear,
    school_class: SchoolClass,
    stream: Stream | None,
    on_date: date,
) -> CandidatePlacement:
    placements = CandidatePlacement.objects.filter(
        candidate=candidate,
        institution_id=candidate.institution_id,
        enrolment__academic_year=year,
        enrolment__school_class=school_class,
        enrolment__effective_from__lte=on_date,
    ).filter(
        Q(enrolment__effective_until__isnull=True)
        | Q(enrolment__effective_until__gte=on_date)
    )
    if stream is not None:
        placements = placements.filter(enrolment__stream=stream)
    elif school_class.streams.exists():
        # A stream-free activity must not silently include learners from all streams.
        placements = placements.filter(enrolment__stream__isnull=True)
    placement = placements.first()
    if placement is None:
        raise ValidationError(
            {"candidate": "Candidate has no matching active placement on this date."}
        )
    return cast(CandidatePlacement, placement)


def offering_for(
    offering_id: Any,
    year: AcademicYear,
    school_class: SchoolClass,
    stream: Stream | None,
    *,
    on_date: date,
) -> SubjectOffering:
    offering = (
        SubjectOffering.objects.filter(
            pk=offering_id,
            release_id=year.release_id,
            academic_year=year,
            school_class=school_class,
        )
        .select_related("term")
        .first()
    )
    if offering is None or (
        offering.stream_id and (stream is None or offering.stream_id != stream.pk)
    ):
        raise ValidationError(
            {"offering": "Subject offering does not cover this class and stream."}
        )
    term = offering.term
    if term is not None and not term.start_date <= on_date <= term.end_date:
        raise ValidationError(
            {"offering": "Subject offering is outside its configured term."}
        )
    return offering
