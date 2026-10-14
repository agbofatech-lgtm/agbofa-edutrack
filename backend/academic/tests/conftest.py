from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest
from django.test import RequestFactory
from rest_framework.test import APIClient

from identity.models import (
    AccessPermission,
    AccessRole,
    MfaCredential,
    ScopeGrant,
    User,
)
from institutional.models import (
    AcademicYear,
    EducationalLevel,
    Institution,
    InstitutionStaffMembership,
    SchoolClass,
    Stream,
    Subject,
    SubjectOffering,
    TeachingAssignment,
)
from institutional.permissions import CONFIGURATION_APPROVE
from institutional.services import approve_release, create_draft_release, submit_release


def actor(username: str, *, staff: bool = False) -> User:
    return User.objects.create_user(username=username, is_staff=staff)


def grant(
    user: User,
    institution: Institution,
    *permissions: str,
    role_code: str | None = None,
) -> AccessRole:
    role = AccessRole.objects.create(
        code=role_code or f"synthetic-{uuid.uuid4().hex[:12]}",
        label="Synthetic test role",
    )
    for code in permissions:
        permission, _ = AccessPermission.objects.get_or_create(code=code)
        role.permissions.add(permission)
    ScopeGrant.objects.create(
        user=user, role=role, scope_type="institution", scope_key=str(institution.pk)
    )
    return role


def client_for(user: User) -> tuple[APIClient, dict[str, str]]:
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    csrf = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
    return client, {"HTTP_X_CSRFTOKEN": csrf}


@pytest.fixture
def world(db: Any) -> dict[str, Any]:
    """Disposable invented institution, school structure and staff; never seeded."""
    institution = Institution.objects.create(
        code="synthetic-school", name="Synthetic school"
    )
    other = Institution.objects.create(code="unrelated-school", name="Unrelated school")
    maker = actor("synthetic-config-maker")
    checker = actor("synthetic-config-checker")
    grant(checker, institution, CONFIGURATION_APPROVE)
    request = RequestFactory().post("/synthetic-setup/")
    release = create_draft_release(
        institution=institution,
        actor=maker,
        effective_from=date(2026, 1, 1),
        request=request,
    )
    year = AcademicYear.objects.create(
        release=release,
        code="synthetic-2026",
        name="Synthetic year",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    level = EducationalLevel.objects.create(
        release=release,
        code="synthetic-level",
        name="Synthetic upper level",
        position=9,
    )
    school_class = SchoolClass.objects.create(
        release=release,
        level=level,
        code="synthetic-class",
        name="Synthetic class",
        position=1,
    )
    stream = Stream.objects.create(
        release=release,
        school_class=school_class,
        code="one",
        name="One",
    )
    subject = Subject.objects.create(
        release=release, code="syn-a", name="Synthetic subject A"
    )
    second_subject = Subject.objects.create(
        release=release, code="syn-b", name="Synthetic subject B"
    )
    offering = SubjectOffering.objects.create(
        release=release,
        academic_year=year,
        school_class=school_class,
        subject=subject,
    )
    second_offering = SubjectOffering.objects.create(
        release=release,
        academic_year=year,
        school_class=school_class,
        subject=second_subject,
    )
    teacher = actor("synthetic-teacher")
    membership = InstitutionStaffMembership.objects.create(
        institution=institution,
        user=teacher,
        effective_from=date(2026, 1, 1),
        created_by=maker,
    )
    assignment = TeachingAssignment.objects.create(
        release=release,
        staff_membership=membership,
        offering=offering,
        effective_from=date(2026, 1, 1),
    )
    submit_release(release=release, actor=maker, request=request)
    approve_release(release=release, actor=checker, request=request)
    return {
        "institution": institution,
        "other": other,
        "year": year,
        "release": release,
        "class": school_class,
        "stream": stream,
        "offering": offering,
        "second_offering": second_offering,
        "assignment": assignment,
        "teacher": teacher,
    }


def path(world: dict[str, Any], suffix: str) -> str:
    return f"/api/v1/institutions/{world['institution'].pk}/academic/{suffix}"


def candidate_data(world: dict[str, Any], name: str = "Learner") -> dict[str, Any]:
    return {
        "given_name": name,
        "family_name": "Synthetic",
        "birth_date": "2011-02-03",
        "academic_year": str(world["year"].pk),
        "school_class": str(world["class"].pk),
        "stream": str(world["stream"].pk),
        "effective_from": "2026-01-10",
    }


def make_candidate(world: dict[str, Any], user: User, name: str = "Learner") -> str:
    from academic.permissions import CANDIDATE_WRITE

    grant(user, world["institution"], CANDIDATE_WRITE)
    client, csrf = client_for(user)
    response = client.post(
        path(world, "candidates/"), candidate_data(world, name), format="json", **csrf
    )
    assert response.status_code == 201, response.json()
    return str(response.json()["id"])


def enable_mfa(user: User) -> None:
    MfaCredential.objects.create(
        user=user, secret_ciphertext=b"synthetic-only", is_enabled=True
    )
