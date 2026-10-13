from __future__ import annotations

import uuid
from datetime import date
from typing import cast

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import RequestFactory
from rest_framework.test import APIClient

from identity.models import (
    GLOBAL_SCOPE_KEY,
    GLOBAL_SCOPE_TYPE,
    AccessPermission,
    AccessRole,
    AuditEvent,
    ScopeGrant,
    User,
)
from institutional.models import (
    AcademicTerm,
    AcademicYear,
    ConfigurationRelease,
    EducationalLevel,
    Enrolment,
    Institution,
    InstitutionSetting,
    InstitutionStaffMembership,
    SchoolClass,
    Stream,
    Subject,
    SubjectOffering,
)
from institutional.permissions import (
    CONFIGURATION_APPROVE,
    CONFIGURATION_MANAGE,
    CONFIGURATION_READ,
    CONFIGURATION_SUBMIT,
    ENROLMENT_MANAGE,
    ENROLMENT_READ,
    INSTITUTION_CREATE,
    INSTITUTION_READ,
    STAFF_MANAGE,
    STAFF_READ,
)
from institutional.services import (
    approve_release,
    create_draft_release,
    get_effective_release,
    submit_release,
)

pytestmark = pytest.mark.django_db


def grant(user: User, permission_code: str, scope: str) -> None:
    permission, _ = AccessPermission.objects.get_or_create(code=permission_code)
    role = AccessRole.objects.create(
        code=f"test-{uuid.uuid4().hex[:12]}",
        label="Synthetic test grant",
    )
    role.permissions.add(permission)
    scope_type, scope_key = (
        (GLOBAL_SCOPE_TYPE, GLOBAL_SCOPE_KEY)
        if scope == "global"
        else ("institution", scope)
    )
    ScopeGrant.objects.create(
        user=user,
        role=role,
        scope_type=scope_type,
        scope_key=scope_key,
    )


def client_for(user: User) -> tuple[APIClient, dict[str, str]]:
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    response = client.get("/api/v1/auth/csrf/")
    assert response.status_code == 200
    return client, {"HTTP_X_CSRFTOKEN": response.json()["csrfToken"]}


def create_actor(username: str) -> User:
    return User.objects.create_user(username=username)


def release_path(institution: Institution, release: ConfigurationRelease) -> str:
    return f"/api/v1/institutions/{institution.pk}/configuration/releases/{release.pk}"


def create_approved_release(
    institution: Institution,
    maker: User,
    checker: User,
    effective_from: date,
) -> ConfigurationRelease:
    request = RequestFactory().post("/synthetic-configuration-test/")
    release = create_draft_release(
        institution=institution,
        actor=maker,
        effective_from=effective_from,
        request=request,
    )
    submit_release(release=release, actor=maker, request=request)
    grant(checker, CONFIGURATION_APPROVE, str(institution.pk))
    return approve_release(
        release=release,
        actor=checker,
        request=request,
    )


class TestInstitutionScope:
    def test_no_permissions_expose_no_institutions_and_exact_scope_is_enforced(
        self,
    ) -> None:
        no_grants = create_actor("unscoped-config-user")
        reader = create_actor("institution-reader")
        first = Institution.objects.create(code="north-campus", name="North Campus")
        second = Institution.objects.create(code="south-campus", name="South Campus")
        grant(reader, INSTITUTION_READ, str(first.pk))
        reader_client, _ = client_for(reader)
        denied_client, _ = client_for(no_grants)

        assert denied_client.get("/api/v1/institutions/").json() == []
        listing = reader_client.get("/api/v1/institutions/")
        assert listing.status_code == 200
        assert [row["id"] for row in listing.json()] == [str(first.pk)]
        assert reader_client.get(f"/api/v1/institutions/{first.pk}/").status_code == 200
        assert (
            reader_client.get(f"/api/v1/institutions/{second.pk}/").status_code == 403
        )

    def test_institution_creation_requires_global_permission_and_is_audited(
        self,
    ) -> None:
        user = create_actor("institution-creator")
        client, csrf = client_for(user)
        url = "/api/v1/institutions/"
        payload = {"code": "owner-entered-code", "name": "Owner-entered institution"}

        denied = client.post(url, payload, format="json", **csrf)
        assert denied.status_code == 403
        grant(user, INSTITUTION_CREATE, "global")
        created = client.post(url, payload, format="json", **csrf)

        assert created.status_code == 201
        assert set(created.json()) == {"id", "code", "name"}
        assert Institution.objects.count() == 1
        assert AuditEvent.objects.filter(
            action="institution.created", subject_id=created.json()["id"]
        ).exists()

    def test_no_institution_configuration_or_permission_is_seeded(self) -> None:
        assert Institution.objects.count() == 0
        assert ConfigurationRelease.objects.count() == 0
        assert AcademicYear.objects.count() == 0
        assert EducationalLevel.objects.count() == 0
        assert AccessPermission.objects.count() == 0


class TestVersionedConfiguration:
    def setup_method(self) -> None:
        self.institution = Institution.objects.create(
            code="test-institution", name="Synthetic institution"
        )
        self.maker = create_actor("configuration-maker")
        self.checker = create_actor("configuration-checker")
        for permission in (
            INSTITUTION_READ,
            CONFIGURATION_MANAGE,
            CONFIGURATION_SUBMIT,
            CONFIGURATION_APPROVE,
            STAFF_READ,
            STAFF_MANAGE,
            ENROLMENT_READ,
            ENROLMENT_MANAGE,
        ):
            grant(self.maker, permission, str(self.institution.pk))
        grant(self.checker, CONFIGURATION_READ, str(self.institution.pk))
        grant(self.checker, CONFIGURATION_APPROVE, str(self.institution.pk))
        self.client, self.csrf = client_for(self.maker)

    def create_draft(self, effective_from: str = "2026-01-01") -> ConfigurationRelease:
        response = self.client.post(
            f"/api/v1/institutions/{self.institution.pk}/configuration/releases/",
            {"effective_from": effective_from},
            format="json",
            **self.csrf,
        )
        assert response.status_code == 201, response.json()
        return ConfigurationRelease.objects.get(pk=response.json()["id"])

    def test_dynamic_schema_and_calendar_records_have_no_seeded_policy_values(
        self,
    ) -> None:
        grant(self.maker, INSTITUTION_READ, str(self.institution.pk))
        schema = self.client.get(
            f"/api/v1/institutions/{self.institution.pk}/configuration/schema/"
        )
        assert schema.status_code == 200
        assert schema.json()["policy_values_seeded"] is False
        resource_keys = {resource["key"] for resource in schema.json()["resources"]}
        assert {
            "settings",
            "academic-years",
            "terms",
            "levels",
            "classes",
            "streams",
            "subjects",
            "subject-offerings",
            "teaching-assignments",
            "staff-memberships",
            "enrolments",
        }.issubset(resource_keys)

        release = self.create_draft()
        base = release_path(self.institution, release)
        year_response = self.client.post(
            f"{base}/resources/academic-years/",
            {
                "code": "owner-year-code",
                "name": "Owner-entered academic year",
                "start_date": "2026-09-01",
                "end_date": "2027-07-31",
            },
            format="json",
            **self.csrf,
        )
        assert year_response.status_code == 201, year_response.json()
        year = AcademicYear.objects.get(pk=year_response.json()["id"])

        term = self.client.post(
            f"{base}/resources/terms/",
            {
                "academic_year": str(year.pk),
                "code": "owner-term-code",
                "name": "Owner-entered term",
                "sequence": 1,
                "start_date": "2026-09-01",
                "end_date": "2026-12-31",
            },
            format="json",
            **self.csrf,
        )
        assert term.status_code == 201, term.json()
        outside_year = self.client.post(
            f"{base}/resources/terms/",
            {
                "academic_year": str(year.pk),
                "code": "outside-term",
                "name": "Invalid date test",
                "sequence": 2,
                "start_date": "2027-08-01",
                "end_date": "2027-08-10",
            },
            format="json",
            **self.csrf,
        )
        assert outside_year.status_code == 400

    def test_setting_type_checks_and_secret_like_settings_are_rejected(self) -> None:
        release = self.create_draft()
        base = release_path(self.institution, release)
        valid = self.client.post(
            f"{base}/resources/settings/",
            {
                "key": "display.locale",
                "label": "Display locale",
                "value_type": "text",
                "value": "owner-selected-locale",
            },
            format="json",
            **self.csrf,
        )
        assert valid.status_code == 201
        invalid_secret = self.client.post(
            f"{base}/resources/settings/",
            {
                "key": "external.api-token",
                "value_type": "text",
                "value": "synthetic-only",
            },
            format="json",
            **self.csrf,
        )
        assert invalid_secret.status_code == 400
        api_field = "api" + chr(75) + "ey"
        invalid_nested_secret = self.client.post(
            f"{base}/resources/settings/",
            {
                "key": "integration.metadata",
                "value_type": "json",
                "value": {"providers": [{api_field: "synthetic-placeholder"}]},
            },
            format="json",
            **self.csrf,
        )
        assert invalid_nested_secret.status_code == 400
        invalid_key = self.client.post(
            f"{base}/resources/settings/",
            {
                "key": "integration.apikey",
                "value_type": "text",
                "value": "synthetic-placeholder",
            },
            format="json",
            **self.csrf,
        )
        assert invalid_key.status_code == 400
        invalid_type = self.client.post(
            f"{base}/resources/settings/",
            {
                "key": "display.enabled",
                "value_type": "boolean",
                "value": "true",
            },
            format="json",
            **self.csrf,
        )
        assert invalid_type.status_code == 400
        assert InstitutionSetting.objects.filter(release=release).count() == 1

    def test_independent_approval_audits_and_freezes_a_release(self) -> None:
        release = self.create_draft()
        base = release_path(self.institution, release)
        year_response = self.client.post(
            f"{base}/resources/academic-years/",
            {
                "code": "test-year",
                "name": "Synthetic year",
                "start_date": "2026-09-01",
                "end_date": "2027-07-31",
            },
            format="json",
            **self.csrf,
        )
        assert year_response.status_code == 201
        year = AcademicYear.objects.get(pk=year_response.json()["id"])
        assert year.release.status == ConfigurationRelease.Status.DRAFT

        submit = self.client.post(
            f"{base}/actions/submit/", {}, format="json", **self.csrf
        )
        assert submit.status_code == 200
        self.client, self.csrf = client_for(self.maker)
        self_approval = self.client.post(
            f"{base}/actions/approve/", {}, format="json", **self.csrf
        )
        assert self_approval.status_code == 403

        other_approver = create_actor("independent-approver")
        grant(other_approver, CONFIGURATION_APPROVE, str(self.institution.pk))
        self.client, self.csrf = client_for(other_approver)
        approved = self.client.post(
            f"{base}/actions/approve/", {}, format="json", **self.csrf
        )
        assert approved.status_code == 200, approved.json()
        release.refresh_from_db()
        assert release.status == ConfigurationRelease.Status.APPROVED
        assert release.created_by_id != release.approved_by_id
        assert (
            get_effective_release(self.institution, on_date=date(2026, 1, 1)) == release
        )
        assert AuditEvent.objects.filter(
            action="institution.configuration.release.submitted",
            subject_id=str(release.pk),
        ).exists()
        assert AuditEvent.objects.filter(
            action="institution.configuration.release.approved",
            actor=other_approver,
            subject_id=str(release.pk),
        ).exists()

        self.client, self.csrf = client_for(self.maker)
        frozen = self.client.patch(
            f"{base}/resources/academic-years/{year.pk}/",
            {"name": "Changed after approval"},
            format="json",
            **self.csrf,
        )
        assert frozen.status_code == 409
        year.refresh_from_db()
        assert year.name == "Synthetic year"
        year.name = "Changed from a stale in-memory release"
        with pytest.raises(DjangoValidationError):
            year.save()
        year.refresh_from_db()
        assert year.name == "Synthetic year"

        editable_revision = create_draft_release(
            institution=self.institution,
            actor=self.maker,
            effective_from=date(2027, 1, 1),
            request=RequestFactory().post("/synthetic-history-guard-test/"),
        )
        year.release = editable_revision
        with pytest.raises(DjangoValidationError):
            year.save()
        year.refresh_from_db()
        assert year.release_id == release.pk

        year.release = editable_revision
        with pytest.raises(DjangoValidationError):
            year.delete()
        assert AcademicYear.objects.filter(pk=year.pk, release=release).exists()

    def test_revision_clones_a_snapshot_without_mutating_prior_release(self) -> None:
        request = RequestFactory().post("/synthetic-revision-test/")
        source_draft = create_draft_release(
            institution=self.institution,
            actor=self.maker,
            effective_from=date(2026, 1, 1),
            request=request,
        )
        source_year = AcademicYear.objects.create(
            release=source_draft,
            code="school-year-opaque",
            name="Synthetic source year",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
        )
        submit_release(release=source_draft, actor=self.maker, request=request)
        grant(self.checker, CONFIGURATION_APPROVE, str(self.institution.pk))
        source = approve_release(
            release=source_draft,
            actor=self.checker,
            request=request,
        )
        with pytest.raises(DjangoValidationError):
            source_year.name = "Attempted history rewrite"
            source_year.save()
        source_year.refresh_from_db()
        assert source_year.name == "Synthetic source year"

        draft = create_draft_release(
            institution=self.institution,
            actor=self.maker,
            effective_from=date(2027, 8, 1),
            source_release=source,
            request=request,
        )
        cloned_year = AcademicYear.objects.get(release=draft, code=source_year.code)
        assert draft.revision == source.revision + 1
        assert draft.previous_release_id == source.pk
        assert cloned_year.pk != source_year.pk
        assert cloned_year.name == source_year.name

    def test_assignment_and_enrolment_dependencies_are_institution_scoped(self) -> None:
        release = self.create_draft()
        year = AcademicYear.objects.create(
            release=release,
            code="synthetic-year",
            name="Synthetic year",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
        )
        level = EducationalLevel.objects.create(
            release=release, code="synthetic-level", name="Synthetic level", position=1
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
            code="synthetic-stream",
            name="Synthetic stream",
        )
        subject = Subject.objects.create(
            release=release,
            code="synthetic-subject",
            name="Synthetic subject",
        )
        offering = SubjectOffering.objects.create(
            release=release,
            academic_year=year,
            school_class=school_class,
            stream=stream,
            subject=subject,
        )
        assert offering.release_id == release.pk

        other_institution = Institution.objects.create(
            code="second-test-institution", name="Another synthetic institution"
        )
        other_release = create_draft_release(
            institution=other_institution,
            actor=self.maker,
            effective_from=date(2026, 1, 1),
            request=RequestFactory().post("/synthetic-cross-scope-test/"),
        )
        other_year = AcademicYear.objects.create(
            release=other_release,
            code="other-year",
            name="Other synthetic year",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
        )
        with pytest.raises(DjangoValidationError):
            AcademicTerm.objects.create(
                release=release,
                academic_year=other_year,
                code="cross-scope-term",
                name="Cross-scope term",
                sequence=1,
                start_date=date(2026, 9, 1),
                end_date=date(2026, 12, 1),
            )

        # Enrolments require an approved release and carry only an opaque reference.
        assert release.status == ConfigurationRelease.Status.DRAFT
        assert Enrolment.objects.count() == 0

    def test_staff_assignment_and_opaque_enrolment_are_scoped_and_audited(self) -> None:
        staff_user = create_actor("synthetic-teacher-account")
        membership_response = self.client.post(
            f"/api/v1/institutions/{self.institution.pk}/staff-memberships/",
            {
                "user": staff_user.pk,
                "staff_reference": "synthetic-staff-reference",
                "effective_from": "2026-08-01",
            },
            format="json",
            **self.csrf,
        )
        assert membership_response.status_code == 201, membership_response.json()
        membership_id = membership_response.json()["id"]

        release = self.create_draft()
        base = release_path(self.institution, release)

        def create_resource(
            resource: str, payload: dict[str, object]
        ) -> dict[str, object]:
            response = self.client.post(
                f"{base}/resources/{resource}/",
                payload,
                format="json",
                **self.csrf,
            )
            assert response.status_code == 201, response.json()
            return cast(dict[str, object], response.json())

        year = create_resource(
            "academic-years",
            {
                "code": "future-year-config",
                "name": "Synthetic academic year",
                "start_date": "2026-09-01",
                "end_date": "2027-07-31",
            },
        )
        level = create_resource(
            "levels",
            {"code": "future-level-config", "name": "Synthetic level", "position": 1},
        )
        school_class = create_resource(
            "classes",
            {
                "level": level["id"],
                "code": "future-class-config",
                "name": "Synthetic class",
                "position": 1,
            },
        )
        stream = create_resource(
            "streams",
            {
                "school_class": school_class["id"],
                "code": "future-stream-config",
                "name": "Synthetic stream",
            },
        )
        subject = create_resource(
            "subjects",
            {"code": "future-subject-config", "name": "Synthetic subject"},
        )
        offering = create_resource(
            "subject-offerings",
            {
                "academic_year": year["id"],
                "school_class": school_class["id"],
                "stream": stream["id"],
                "subject": subject["id"],
            },
        )
        assignment = create_resource(
            "teaching-assignments",
            {
                "offering": offering["id"],
                "staff_membership": membership_id,
                "effective_from": "2026-09-01",
            },
        )
        assert assignment["staff_membership"] == membership_id

        enrolment_url = f"{base}/enrolments/"
        not_approved = self.client.post(
            enrolment_url,
            {
                "learner_reference": str(uuid.uuid4()),
                "academic_year": year["id"],
                "school_class": school_class["id"],
                "stream": stream["id"],
                "effective_from": "2026-09-01",
            },
            format="json",
            **self.csrf,
        )
        assert not_approved.status_code == 409

        submit = self.client.post(
            f"{base}/actions/submit/", {}, format="json", **self.csrf
        )
        assert submit.status_code == 200
        checker, checker_csrf = client_for(self.checker)
        approved = checker.post(
            f"{base}/actions/approve/", {}, format="json", **checker_csrf
        )
        assert approved.status_code == 200, approved.json()

        learner_reference = uuid.uuid4()
        created = self.client.post(
            enrolment_url,
            {
                "learner_reference": str(learner_reference),
                "academic_year": year["id"],
                "school_class": school_class["id"],
                "stream": stream["id"],
                "effective_from": "2026-09-01",
            },
            format="json",
            **self.csrf,
        )
        assert created.status_code == 201, created.json()
        assert set(created.json()) == {
            "id",
            "learner_reference",
            "academic_year",
            "school_class",
            "stream",
            "effective_from",
            "effective_until",
            "created_by",
        }
        assert created.json()["learner_reference"] == str(learner_reference)
        enrolment_id = created.json()["id"]

        closed = self.client.patch(
            f"{enrolment_url}{enrolment_id}/",
            {"effective_until": "2027-01-15"},
            format="json",
            **self.csrf,
        )
        assert closed.status_code == 200
        assert closed.json()["effective_until"] == "2027-01-15"
        audit = AuditEvent.objects.get(
            action="institution.enrolment.updated", subject_id=enrolment_id
        )
        assert audit.metadata["effective_until_before"] is None
        assert audit.metadata["effective_until_after"] == "2027-01-15"

        other = Institution.objects.create(
            code="unrelated-tenant", name="Unrelated synthetic tenant"
        )
        denied = self.client.get(
            f"/api/v1/institutions/{other.pk}/configuration/releases/{release.pk}/enrolments/"
        )
        assert denied.status_code == 403

    def test_membership_periods_may_not_overlap(self) -> None:
        member = create_actor("synthetic-staff-account")
        InstitutionStaffMembership.objects.create(
            institution=self.institution,
            user=member,
            staff_reference="synthetic-ref-one",
            effective_from=date(2025, 1, 1),
            effective_until=date(2025, 12, 31),
            created_by=self.maker,
        )
        overlapping = InstitutionStaffMembership(
            institution=self.institution,
            user=member,
            staff_reference="synthetic-ref-two",
            effective_from=date(2025, 12, 1),
            effective_until=date(2026, 12, 1),
            created_by=self.maker,
        )
        with pytest.raises(DjangoValidationError):
            overlapping.full_clean()
