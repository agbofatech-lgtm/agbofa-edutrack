from __future__ import annotations

from typing import Any

import pytest

from academic.permissions import CANDIDATE_READ, CANDIDATE_WRITE
from academic.tests.conftest import actor, candidate_data, client_for, grant, path
from identity.models import AuditEvent

pytestmark = pytest.mark.django_db


def test_candidate_create_requires_permission_and_csrf(world: dict[str, Any]) -> None:
    user = actor("synthetic-registry")
    client, csrf = client_for(user)
    url = path(world, "candidates/")
    assert (
        client.post(url, candidate_data(world), format="json", **csrf).status_code
        == 403
    )
    grant(user, world["institution"], CANDIDATE_WRITE, CANDIDATE_READ)
    assert client.post(url, candidate_data(world), format="json").status_code == 403
    result = client.post(url, candidate_data(world), format="json", **csrf)
    assert result.status_code == 201, result.json()
    pk = result.json()["id"]
    profile = client.get(path(world, f"candidates/{pk}/profile/"))
    assert profile.status_code == 200, profile.json()
    assert {"no-store", "private"}.issubset(
        set(profile.headers["Cache-Control"].replace(" ", "").split(","))
    )
    assert len(profile.json()["placements"]) == 1
    assert profile.json()["sections"]["attendance"]["state"] == "unavailable"
    assert (
        client.post(url, candidate_data(world), format="json", **csrf).status_code
        == 409
    )
    event = AuditEvent.objects.get(action="academic.candidate.created")
    assert "Learner" not in str(event.metadata)


def test_candidate_lifecycle_reconciliation_and_tenant_isolation(
    world: dict[str, Any],
) -> None:
    from academic.models import Candidate, CandidateChange
    from academic.permissions import CANDIDATE_RECONCILE

    user = actor("synthetic-steward")
    grant(
        user, world["institution"], CANDIDATE_READ, CANDIDATE_WRITE, CANDIDATE_RECONCILE
    )
    client, csrf = client_for(user)
    first = client.post(
        path(world, "candidates/"),
        candidate_data(world, "Avery"),
        format="json",
        **csrf,
    )
    second = client.post(
        path(world, "candidates/"),
        candidate_data(world, "Robin"),
        format="json",
        **csrf,
    )
    assert first.status_code == second.status_code == 201
    first_id, second_id = first.json()["id"], second.json()["id"]
    first_url = path(world, f"candidates/{first_id}/")
    assert (
        client.patch(
            first_url,
            {
                "status": "inactive",
                "reason": "Synthetic withdrawal",
                "expected_version": 1,
            },
            format="json",
            **csrf,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            first_url,
            {"status": "active", "reason": "Synthetic reversal", "expected_version": 1},
            format="json",
            **csrf,
        ).status_code
        == 409
    )
    change = CandidateChange.objects.get(candidate_id=first_id)
    assert change.before["status"] == "active" and change.after["status"] == "inactive"
    assert "Synthetic withdrawal" not in str(
        AuditEvent.objects.get(action="academic.candidate.corrected").metadata
    )
    reconcile = client.post(
        path(world, f"candidates/{first_id}/reconcile/"),
        {
            "expected_version": 2,
            "canonical_candidate": second_id,
            "reason": "Identity review concluded duplicate",
        },
        format="json",
        **csrf,
    )
    assert reconcile.status_code == 200, reconcile.json()
    assert reconcile.json()["status"] == "duplicate"
    assert (
        Candidate.objects.get(pk=first_id).canonical_candidate_id
        == Candidate.objects.get(pk=second_id).pk
    )
    assert (
        client.patch(
            first_url,
            {"status": "active", "reason": "Unsafe reversal", "expected_version": 3},
            format="json",
            **csrf,
        ).status_code
        == 409
    )
    other_url = (
        f"/api/v1/institutions/{world['other'].pk}/academic/candidates/{first_id}/"
    )
    assert client.get(other_url).status_code == 403
    denied = actor("synthetic-other-reader")
    grant(denied, world["other"], CANDIDATE_READ, CANDIDATE_WRITE)
    denied_client, denied_csrf = client_for(denied)
    assert denied_client.get(other_url).status_code == 404
    assert (
        denied_client.post(
            f"/api/v1/institutions/{world['other'].pk}/academic/candidates/",
            candidate_data(world, "Wrong"),
            format="json",
            **denied_csrf,
        ).status_code
        == 400
    )
    assert denied_client.get(path(world, f"candidates/{second_id}/")).status_code == 403


def test_guardian_link_contact_scope_versions_and_history(
    world: dict[str, Any],
) -> None:
    from academic.models import GuardianChange, GuardianLinkChange
    from academic.permissions import GUARDIAN_READ, GUARDIAN_WRITE

    steward = actor("synthetic-guardian-steward")
    reader = actor("synthetic-candidate-only")
    grant(
        steward,
        world["institution"],
        CANDIDATE_READ,
        CANDIDATE_WRITE,
        GUARDIAN_READ,
        GUARDIAN_WRITE,
    )
    grant(reader, world["institution"], CANDIDATE_READ)
    client, csrf = client_for(steward)
    candidate = client.post(
        path(world, "candidates/"),
        candidate_data(world, "Casey"),
        format="json",
        **csrf,
    ).json()["id"]
    guardian = client.post(
        path(world, "guardians/"),
        {
            "name": "Test Guardian",
            "phone": "+233 20 000 0000",
            "email": "synthetic@example.test",
        },
        format="json",
        **csrf,
    )
    assert guardian.status_code == 201, guardian.json()
    guardian_id = guardian.json()["id"]
    links = path(world, f"candidates/{candidate}/guardians/")
    linked = client.post(
        links,
        {
            "guardian": guardian_id,
            "relationship": "Synthetic relation",
            "contact_authorized": False,
        },
        format="json",
        **csrf,
    )
    assert linked.status_code == 201, linked.json()
    assert linked.json()["guardian_detail"]["phone"] == ""
    profile = client.get(path(world, f"candidates/{candidate}/profile/")).json()
    assert (
        profile["sections"]["guardians"]["records"][0]["guardian_detail"]["email"] == ""
    )
    reader_client, _ = client_for(reader)
    assert reader_client.get(links).status_code == 403
    assert (
        reader_client.get(path(world, f"candidates/{candidate}/profile/")).json()[
            "sections"
        ]["guardians"]["state"]
        == "restricted"
    )
    assert (
        client.post(
            links,
            {
                "guardian": guardian_id,
                "relationship": "Repeat",
                "contact_authorized": True,
            },
            format="json",
            **csrf,
        ).status_code
        == 409
    )
    link_url = path(world, f"candidates/{candidate}/guardians/{linked.json()['id']}/")
    updated = client.patch(
        link_url,
        {
            "contact_authorized": True,
            "reason": "Synthetic confirmed authorization",
            "expected_version": 1,
        },
        format="json",
        **csrf,
    )
    assert updated.status_code == 200, updated.json()
    assert updated.json()["guardian_detail"]["phone"] == "+233 20 000 0000"
    assert (
        client.patch(
            link_url,
            {"relationship": "Other", "reason": "Stale", "expected_version": 1},
            format="json",
            **csrf,
        ).status_code
        == 409
    )
    change = client.patch(
        path(world, f"guardians/{guardian_id}/"),
        {
            "phone": "+233 30 000 0000",
            "expected_version": 1,
            "reason": "Synthetic authorized correction",
        },
        format="json",
        **csrf,
    )
    assert change.status_code == 200, change.json()
    assert GuardianChange.objects.count() == GuardianLinkChange.objects.count() == 1
    assert "30 000" not in str(
        AuditEvent.objects.get(action="academic.guardian.corrected").metadata
    )
    assert "confirmed authorization" not in str(
        AuditEvent.objects.get(action="academic.guardian.link.corrected").metadata
    )
    outsider_guardian = client.post(
        path(world, "guardians/"), {"name": "Other synthetic"}, format="json", **csrf
    ).json()["id"]
    other_reader = actor("synthetic-other-guardian")
    grant(other_reader, world["other"], CANDIDATE_READ, GUARDIAN_READ, GUARDIAN_WRITE)
    other_client, other_csrf = client_for(other_reader)
    assert (
        other_client.get(path(world, f"guardians/{outsider_guardian}/")).status_code
        == 403
    )
    assert (
        other_client.get(
            f"/api/v1/institutions/{world['other'].pk}/academic/guardians/{outsider_guardian}/"
        ).status_code
        == 404
    )
    assert (
        other_client.post(
            f"/api/v1/institutions/{world['other'].pk}/academic/candidates/{candidate}/guardians/",
            {
                "guardian": guardian_id,
                "relationship": "Forbidden",
                "contact_authorized": True,
            },
            format="json",
            **other_csrf,
        ).status_code
        == 404
    )


def test_import_preview_errors_idempotency_and_atomic_commit(
    world: dict[str, Any],
) -> None:
    import uuid

    from academic.models import Candidate, CandidateImport
    from academic.permissions import CANDIDATE_IMPORT

    user = actor("synthetic-import-operator")
    grant(user, world["institution"], CANDIDATE_IMPORT)
    client, csrf = client_for(user)
    url = path(world, "candidate-imports/preview/")
    key = str(uuid.uuid4())
    row = candidate_data(world, "Import One")
    invalid = {
        "idempotency_key": key,
        "rows": [
            row,
            {**row, "given_name": " Import One "},
            {
                **row,
                "given_name": "Different",
                "academic_year": str(uuid.uuid4()),
            },
        ],
    }
    preview = client.post(url, invalid, format="json", **csrf)
    assert preview.status_code == 200, preview.json()
    assert preview.json()["valid"] is False
    assert [e["row"] for e in preview.json()["errors"]] == [2, 3]
    assert Candidate.objects.count() == 0
    batch = CandidateImport.objects.get(pk=preview.json()["batch"]["id"])
    assert batch.error_count == 2
    assert "Import One" not in str(
        AuditEvent.objects.get(action="academic.candidate.import.previewed").metadata
    )
    assert (
        client.post(
            path(world, f"candidate-imports/{batch.pk}/commit/"),
            invalid,
            format="json",
            **csrf,
        ).status_code
        == 409
    )
    altered = {"idempotency_key": key, "rows": [{**row, "given_name": "Altered"}]}
    assert client.post(url, altered, format="json", **csrf).status_code == 409
    valid = {
        "idempotency_key": str(uuid.uuid4()),
        "rows": [row, candidate_data(world, "Import Two")],
    }
    good = client.post(url, valid, format="json", **csrf)
    assert good.status_code == 200 and good.json()["valid"]
    commit_url = path(world, f"candidate-imports/{good.json()['batch']['id']}/commit/")
    applied = client.post(commit_url, valid, format="json", **csrf)
    assert applied.status_code == 201, applied.json()
    repeated = client.post(commit_url, valid, format="json", **csrf)
    assert (
        repeated.status_code == 200
        and repeated.json()["candidate_ids"] == applied.json()["candidate_ids"]
    )
    assert Candidate.objects.count() == 2
    assert (
        AuditEvent.objects.filter(action="academic.candidate.import.applied").count()
        == 1
    )
    # Preview can go stale after another operator creates the identity.
    pending = {
        "idempotency_key": str(uuid.uuid4()),
        "rows": [candidate_data(world, "Stale")],
    }
    staged = client.post(url, pending, format="json", **csrf).json()["batch"]["id"]
    steward = actor("synthetic-other-steward")
    grant(steward, world["institution"], CANDIDATE_WRITE)
    own, own_csrf = client_for(steward)
    assert (
        own.post(
            path(world, "candidates/"), pending["rows"][0], format="json", **own_csrf
        ).status_code
        == 201
    )
    assert (
        client.post(
            path(world, f"candidate-imports/{staged}/commit/"),
            pending,
            format="json",
            **csrf,
        ).status_code
        == 409
    )
    assert Candidate.objects.count() == 3
    assert (
        own.post(
            path(world, f"candidate-imports/{staged}/commit/"),
            pending,
            format="json",
            **own_csrf,
        ).status_code
        == 403
    )
    assert (
        client.post(
            url,
            {
                "idempotency_key": str(uuid.uuid4()),
                "rows": [{"given_name": "Malformed", "unexpected": "ignore me"}],
            },
            format="json",
            **csrf,
        ).json()["valid"]
        is False
    )


def test_ba0_approval_immutability_and_independent_correction(
    world: dict[str, Any],
) -> None:
    from django.core.exceptions import ValidationError as DjangoValidationError

    from academic.models import (
        Baseline,
        BaselineCorrection,
        BaselineEdit,
        BaselineObservation,
    )
    from academic.permissions import (
        BASELINE_APPROVE,
        BASELINE_CORRECT,
        BASELINE_CORRECTION_AUTHORIZE,
        BASELINE_ENTER,
        BASELINE_READ,
        BASELINE_SUBMIT,
    )
    from academic.tests.conftest import make_candidate

    maker = actor("synthetic-baseline-maker")
    reviewer = actor("synthetic-baseline-reviewer")
    authorizer = actor("synthetic-baseline-authorizer")
    grant(
        maker,
        world["institution"],
        BASELINE_ENTER,
        BASELINE_READ,
        BASELINE_SUBMIT,
        BASELINE_CORRECT,
        BASELINE_APPROVE,
        BASELINE_CORRECTION_AUTHORIZE,
    )
    grant(reviewer, world["institution"], BASELINE_APPROVE, BASELINE_READ)
    grant(authorizer, world["institution"], BASELINE_CORRECTION_AUTHORIZE)
    candidate = make_candidate(world, maker, "Baseline Learner")
    client, csrf = client_for(maker)
    url = path(world, "baselines/")
    data = {
        "candidate": candidate,
        "academic_year": str(world["year"].pk),
        "effective_date": "2026-03-02",
        "source_label": "Synthetic baseline source",
        "source_date": "2026-03-01",
        "observations": [
            {
                "offering": str(world["offering"].pk),
                "state": "scored",
                "score": "0.00",
                "maximum_score": "50.00",
            },
            {"offering": str(world["second_offering"].pk), "state": "missing"},
        ],
    }
    response = client.post(url, data, format="json", **csrf)
    assert response.status_code == 201, response.json()
    baseline_id = response.json()["id"]
    assert response.json()["observations"][0]["score"] in ("0.00", None)
    base_url = path(world, f"baselines/{baseline_id}/")
    assert client.post(url, data, format="json", **csrf).status_code == 409
    invalid = client.patch(
        base_url,
        {
            "expected_version": 1,
            "reason": "Synthetic malformed value",
            "observations": [
                {
                    "offering": str(world["offering"].pk),
                    "state": "absent",
                    "score": "0.00",
                },
            ],
        },
        format="json",
        **csrf,
    )
    assert invalid.status_code == 400, invalid.json()
    assert BaselineObservation.objects.filter(baseline_id=baseline_id).count() == 2
    edit = client.patch(
        base_url,
        {
            "expected_version": 1,
            "reason": "Synthetic corrected provenance",
            "source_label": "Rechecked synthetic source",
        },
        format="json",
        **csrf,
    )
    assert edit.status_code == 200, edit.json()
    assert BaselineEdit.objects.filter(baseline_id=baseline_id).count() == 1
    assert (
        client.patch(
            base_url,
            {"expected_version": 1, "reason": "Stale", "source_label": "No"},
            format="json",
            **csrf,
        ).status_code
        == 409
    )
    actions = path(world, f"baselines/{baseline_id}/actions/")
    assert (
        client.post(
            actions + "approve/", {"expected_version": 2}, format="json", **csrf
        ).status_code
        == 403
    )
    submitted = client.post(
        actions + "submit/", {"expected_version": 2}, format="json", **csrf
    )
    assert submitted.status_code == 200, submitted.json()
    assert (
        client.patch(
            base_url,
            {"expected_version": 3, "reason": "Too late", "source_label": "Unsafe"},
            format="json",
            **csrf,
        ).status_code
        == 409
    )
    assert (
        client.post(
            actions + "approve/", {"expected_version": 3}, format="json", **csrf
        ).status_code
        == 403
    )
    check_client, check_csrf = client_for(reviewer)
    approved = check_client.post(
        actions + "approve/", {"expected_version": 3}, format="json", **check_csrf
    )
    assert approved.status_code == 200, approved.json()
    assert (
        approved.json()["status"] == "approved" and approved.json()["snapshot_digest"]
    )
    assert {row["state"] for row in approved.json()["observations"]} == {
        "scored",
        "missing",
    }
    assert approved.json()["quality"]["missing"] == 1
    assert approved.json()["quality"]["observations_resolved"] is False
    assert approved.json()["quality"]["coverage_verified"] is False
    assert approved.json()["quality"]["complete"] is False
    original_digest = approved.json()["snapshot_digest"]
    baseline = Baseline.objects.get(pk=baseline_id)
    baseline.source_label = "Tampered"
    with pytest.raises(DjangoValidationError):
        baseline.save()
    observation = BaselineObservation.objects.get(baseline=baseline, state="scored")
    observation.score = 30
    with pytest.raises(DjangoValidationError):
        observation.save()
    with pytest.raises(DjangoValidationError):
        BaselineObservation.objects.filter(pk=observation.pk).update(score=30)
    with pytest.raises(DjangoValidationError):
        BaselineObservation.objects.bulk_create(
            [
                BaselineObservation(
                    baseline=baseline, offering=world["offering"], state="missing"
                )
            ]
        )
    assert Baseline.objects.get(pk=baseline_id).snapshot_digest == original_digest
    correction = client.post(
        path(world, f"baselines/{baseline_id}/corrections/"),
        {"reason": "Synthetic missing source received later"},
        format="json",
        **csrf,
    )
    assert correction.status_code == 201, correction.json()
    decision_url = path(
        world, f"baseline-corrections/{correction.json()['id']}/decision/"
    )
    assert (
        client.post(
            decision_url,
            {"expected_status": "pending", "decision": "authorize"},
            format="json",
            **csrf,
        ).status_code
        == 403
    )
    auth_client, auth_csrf = client_for(authorizer)
    authorized = auth_client.post(
        decision_url,
        {"expected_status": "pending", "decision": "authorize"},
        format="json",
        **auth_csrf,
    )
    assert authorized.status_code == 200, authorized.json()
    assert authorized.json()["status"] == "authorized"
    assert (
        auth_client.post(
            decision_url,
            {"expected_status": "pending", "decision": "authorize"},
            format="json",
            **auth_csrf,
        ).status_code
        == 409
    )
    successor = Baseline.objects.get(pk=authorized.json()["successor"])
    assert (
        successor.revision == 2
        and successor.previous_id == baseline.pk
        and successor.status == "draft"
    )
    assert (
        BaselineCorrection.objects.get(pk=correction.json()["id"]).reason
        == "Synthetic missing source received later"
    )
    assert BaselineObservation.objects.filter(baseline=successor).count() == 2
    successor_url = path(world, f"baselines/{successor.pk}/")
    corrected = client.patch(
        successor_url,
        {
            "expected_version": 1,
            "reason": "Synthetic resolved missing observation",
            "observations": [
                {
                    "offering": str(world["offering"].pk),
                    "state": "scored",
                    "score": "0.00",
                    "maximum_score": "50.00",
                },
                {"offering": str(world["second_offering"].pk), "state": "absent"},
            ],
        },
        format="json",
        **csrf,
    )
    assert corrected.status_code == 200, corrected.json()
    assert (
        client.post(
            path(world, f"baselines/{successor.pk}/actions/submit/"),
            {"expected_version": 2},
            format="json",
            **csrf,
        ).status_code
        == 200
    )
    new_approved = check_client.post(
        path(world, f"baselines/{successor.pk}/actions/approve/"),
        {"expected_version": 3},
        format="json",
        **check_csrf,
    )
    assert new_approved.status_code == 200, new_approved.json()
    assert new_approved.json()["quality"]["observations_resolved"] is True
    assert new_approved.json()["quality"]["complete"] is False
    assert new_approved.json()["snapshot_digest"] != original_digest
    assert Baseline.objects.get(pk=baseline_id).snapshot_digest == original_digest
    assert "Synthetic" not in str(
        AuditEvent.objects.get(action="academic.baseline.correction.decided").metadata
    )
    approval = (
        AuditEvent.objects.filter(action="academic.baseline.approved")
        .order_by("occurred_at")
        .last()
    )
    assert approval is not None
    assert approval.metadata["before_digest"] == original_digest
    assert approval.metadata["after_digest"] == new_approved.json()["snapshot_digest"]


def test_weekly_marks_moderation_publication_and_republication(
    world: dict[str, Any],
) -> None:
    from django.core.exceptions import ValidationError as DjangoValidationError

    from academic.models import AcademicActivity, AcademicMark, MarkChange
    from academic.permissions import (
        WEEKLY_APPROVE,
        WEEKLY_CORRECT,
        WEEKLY_CORRECTION_AUTHORIZE,
        WEEKLY_ENTER,
        WEEKLY_PUBLISH,
        WEEKLY_READ,
        WEEKLY_REVIEW,
        WEEKLY_SCHEDULE,
    )
    from academic.tests.conftest import make_candidate

    scheduler = actor("synthetic-weekly-scheduler")
    reviewer = actor("synthetic-weekly-reviewer")
    approver = actor("synthetic-weekly-approver")
    authorizer = actor("synthetic-weekly-correction-authorizer")
    intruder = actor("synthetic-weekly-intruder")
    teacher = world["teacher"]
    grant(
        scheduler,
        world["institution"],
        WEEKLY_SCHEDULE,
        WEEKLY_READ,
        WEEKLY_REVIEW,
        WEEKLY_APPROVE,
        WEEKLY_CORRECT,
        CANDIDATE_READ,
    )
    grant(teacher, world["institution"], WEEKLY_ENTER)
    grant(intruder, world["institution"], WEEKLY_ENTER)
    grant(reviewer, world["institution"], WEEKLY_REVIEW)
    grant(approver, world["institution"], WEEKLY_APPROVE, WEEKLY_PUBLISH)
    grant(authorizer, world["institution"], WEEKLY_CORRECTION_AUTHORIZE)
    candidate_one = make_candidate(world, scheduler, "Weekly One")
    candidate_two = make_candidate(world, scheduler, "Weekly Two")
    client, csrf = client_for(scheduler)
    created = client.post(
        path(world, "weekly/"),
        {
            "academic_year": str(world["year"].pk),
            "school_class": str(world["class"].pk),
            "stream": str(world["stream"].pk),
            "teacher_assignment": str(world["assignment"].pk),
            "scheduled_for": "2026-03-07",
            "title": "Synthetic week",
            "assessment_type": "Owner-entered exercise",
            "subjects": [
                {"offering": str(world["offering"].pk), "maximum_score": "25.00"}
            ],
        },
        format="json",
        **csrf,
    )
    assert created.status_code == 201, created.json()
    event_id = created.json()["id"]
    event_url = path(world, f"weekly/{event_id}/")
    invalid_subject = client.post(
        path(world, "weekly/"),
        {
            "academic_year": str(world["year"].pk),
            "school_class": str(world["class"].pk),
            "stream": str(world["stream"].pk),
            "teacher_assignment": str(world["assignment"].pk),
            "scheduled_for": "2026-03-07",
            "title": "Incorrect blueprint",
            "assessment_type": "Synthetic",
            "subjects": [
                {"offering": str(world["second_offering"].pk), "maximum_score": "25.00"}
            ],
        },
        format="json",
        **csrf,
    )
    assert invalid_subject.status_code == 400
    assert AcademicActivity.objects.count() == 1  # Transactional create.
    roster = client.post(
        path(world, f"weekly/{event_id}/roster/"),
        {
            "expected_activity_version": 1,
            "entries": [
                {
                    "candidate": candidate_one,
                    "eligible": True,
                    "participation": "attended",
                },
                {
                    "candidate": candidate_two,
                    "eligible": True,
                    "participation": "absent",
                },
            ],
        },
        format="json",
        **csrf,
    )
    assert roster.status_code == 200, roster.json()
    assert roster.json()["quality"]["missing"] == 2
    marks = {row["candidate"]: row for row in roster.json()["marks"]}
    mark_url = path(world, f"weekly/{event_id}/marks/")
    one = {
        "participant": marks[candidate_one]["participant"],
        "subject": marks[candidate_one]["subject"],
        "state": "scored",
        "score": "0.00",
        "expected_version": 1,
    }
    two = {
        "participant": marks[candidate_two]["participant"],
        "subject": marks[candidate_two]["subject"],
        "state": "absent",
        "expected_version": 1,
    }
    teach_client, teach_csrf = client_for(teacher)
    wrong, wrong_csrf = client_for(intruder)
    assert (
        wrong.post(
            mark_url,
            {"expected_activity_version": 2, "marks": [one]},
            format="json",
            **wrong_csrf,
        ).status_code
        == 403
    )
    assert (
        client.post(
            mark_url,
            {"expected_activity_version": 2, "marks": [one]},
            format="json",
            **csrf,
        ).status_code
        == 403
    )
    over = {**one, "score": "25.01"}
    assert (
        teach_client.post(
            mark_url,
            {"expected_activity_version": 2, "marks": [one, over]},
            format="json",
            **teach_csrf,
        ).status_code
        == 400
    )
    assert (
        teach_client.post(
            mark_url,
            {"expected_activity_version": 2, "marks": [one, {**two, "score": "0.00"}]},
            format="json",
            **teach_csrf,
        ).status_code
        == 400
    )
    assert (
        AcademicMark.objects.filter(activity_id=event_id, state="missing").count() == 2
    )
    entered = teach_client.post(
        mark_url,
        {"expected_activity_version": 2, "marks": [one]},
        format="json",
        **teach_csrf,
    )
    assert entered.status_code == 200, entered.json()
    assert (
        entered.json()["quality"]["scored"] == 1
        and entered.json()["quality"]["missing"] == 1
    )
    assert (
        teach_client.post(
            mark_url,
            {"expected_activity_version": 2, "marks": [one]},
            format="json",
            **teach_csrf,
        ).status_code
        == 409
    )
    assert MarkChange.objects.filter(mark_id=marks[candidate_one]["id"]).count() == 1
    candidate_profile = client.get(
        path(world, f"candidates/{candidate_one}/profile/")
    ).json()
    assert len(candidate_profile["sections"]["assessments"]["records"][0]["marks"]) == 1
    assert (
        candidate_profile["sections"]["assessments"]["records"][0]["marks"][0][
            "candidate"
        ]
        == candidate_one
    )
    actions = path(world, f"weekly/{event_id}/actions/")
    assert (
        client.post(
            actions + "approve/", {"expected_version": 3}, format="json", **csrf
        ).status_code
        == 403
    )
    submitted = client.post(
        actions + "submit/", {"expected_version": 3}, format="json", **csrf
    )
    assert submitted.status_code == 200, submitted.json()
    assert (
        teach_client.post(
            mark_url,
            {"expected_activity_version": 3, "marks": [two]},
            format="json",
            **teach_csrf,
        ).status_code
        == 409
    )
    assert (
        client.post(
            actions + "moderate/", {"expected_version": 4}, format="json", **csrf
        ).status_code
        == 403
    )
    review_client, review_csrf = client_for(reviewer)
    moderated = review_client.post(
        actions + "moderate/", {"expected_version": 4}, format="json", **review_csrf
    )
    assert moderated.status_code == 200, moderated.json()
    assert (
        client.post(
            actions + "approve/", {"expected_version": 5}, format="json", **csrf
        ).status_code
        == 403
    )
    approve_client, approve_csrf = client_for(approver)
    approved = approve_client.post(
        actions + "approve/", {"expected_version": 5}, format="json", **approve_csrf
    )
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert (
        approved.json()["quality"]["missing"] == 1
        and approved.json()["quality"]["complete"] is False
    )
    before_digest = approved.json()["snapshot_digest"]
    assert (
        approve_client.post(
            actions + "publish/", {"expected_version": 6}, format="json", **approve_csrf
        ).status_code
        == 409
    )
    mark = AcademicMark.objects.get(pk=marks[candidate_one]["id"])
    mark.score = 12
    with pytest.raises(DjangoValidationError):
        mark.save()
    assert (
        client.patch(
            event_url,
            {"expected_version": 6, "title": "Unsafe", "reason": "Test"},
            format="json",
            **csrf,
        ).status_code
        == 409
    )
    correction = client.post(
        path(world, f"weekly/{event_id}/corrections/"),
        {"reason": "Synthetic absent value verified"},
        format="json",
        **csrf,
    )
    assert correction.status_code == 201, correction.json()
    decision_url = path(
        world, f"weekly/corrections/{correction.json()['id']}/decision/"
    )
    assert (
        client.post(
            decision_url,
            {"expected_status": "pending", "decision": "authorize"},
            format="json",
            **csrf,
        ).status_code
        == 403
    )
    auth_client, auth_csrf = client_for(authorizer)
    decision = auth_client.post(
        decision_url,
        {"expected_status": "pending", "decision": "authorize"},
        format="json",
        **auth_csrf,
    )
    assert decision.status_code == 200, decision.json()
    revised_id = decision.json()["successor"]
    revised = client.get(path(world, f"weekly/{revised_id}/")).json()
    assert revised["revision"] == 2 and revised["previous"] == event_id
    missing = next(row for row in revised["marks"] if row["candidate"] == candidate_two)
    revised_two = {
        "participant": missing["participant"],
        "subject": missing["subject"],
        "state": "absent",
        "expected_version": 1,
    }
    assert (
        teach_client.post(
            path(world, f"weekly/{revised_id}/marks/"),
            {"expected_activity_version": 1, "marks": [revised_two]},
            format="json",
            **teach_csrf,
        ).status_code
        == 200
    )
    revised_actions = path(world, f"weekly/{revised_id}/actions/")
    assert (
        client.post(
            revised_actions + "submit/", {"expected_version": 2}, format="json", **csrf
        ).status_code
        == 200
    )
    assert (
        review_client.post(
            revised_actions + "moderate/",
            {"expected_version": 3},
            format="json",
            **review_csrf,
        ).status_code
        == 200
    )
    final = approve_client.post(
        revised_actions + "approve/",
        {"expected_version": 4},
        format="json",
        **approve_csrf,
    )
    assert final.status_code == 200, final.json()
    assert final.json()["snapshot_digest"] != before_digest
    assert final.json()["quality"]["complete"] is True
    published = approve_client.post(
        revised_actions + "publish/",
        {"expected_version": 5},
        format="json",
        **approve_csrf,
    )
    assert published.status_code == 200, published.json()
    assert published.json()["status"] == "published"
    assert AcademicActivity.objects.get(pk=event_id).snapshot_digest == before_digest
    assert client.get(path(world, f"weekly/{event_id}/")).json()["status"] == "approved"
    assert (
        approve_client.post(
            revised_actions + "publish/",
            {"expected_version": 6},
            format="json",
            **approve_csrf,
        ).status_code
        == 409
    )
    assert AuditEvent.objects.filter(action="academic.weekly.mark.edited").count() == 2
    assert (
        AuditEvent.objects.get(action="academic.weekly.correction.decided").metadata[
            "before_digest"
        ]
        == before_digest
    )
    assert "Synthetic absent" not in str(
        AuditEvent.objects.get(action="academic.weekly.correction.decided").metadata
    )


def test_mock_governance_blueprint_and_immutable_result_history(
    world: dict[str, Any], settings: Any
) -> None:
    from django.core.exceptions import ValidationError as DjangoValidationError

    from academic.models import AcademicActivity, AcademicMark
    from academic.permissions import (
        MOCK_APPROVE,
        MOCK_CORRECT,
        MOCK_CORRECTION_AUTHORIZE,
        MOCK_ENTER,
        MOCK_PREPARE,
        MOCK_PUBLISH,
        MOCK_READ,
        MOCK_REVIEW,
    )
    from academic.tests.conftest import enable_mfa, make_candidate

    preparer = actor("synthetic-jhs-contact")
    head = actor("synthetic-headmaster", staff=True)
    local_manager = actor("synthetic-manager")
    reviewer = actor("synthetic-mock-reviewer")
    grant(
        preparer,
        world["institution"],
        MOCK_PREPARE,
        MOCK_ENTER,
        MOCK_READ,
        MOCK_CORRECT,
        role_code="synthetic-contact",
    )
    grant(
        head,
        world["institution"],
        MOCK_APPROVE,
        MOCK_PUBLISH,
        MOCK_CORRECTION_AUTHORIZE,
        role_code="synthetic-head",
    )
    grant(local_manager, world["institution"], MOCK_APPROVE)
    grant(reviewer, world["institution"], MOCK_REVIEW)
    candidate = make_candidate(world, preparer, "Mock Candidate")
    excluded = make_candidate(world, preparer, "Mock Excluded")
    client, csrf = client_for(preparer)
    payload = {
        "academic_year": str(world["year"].pk),
        "school_class": str(world["class"].pk),
        "stream": str(world["stream"].pk),
        "scheduled_for": "2026-06-17",
        "title": "Synthetic June full mock",
        "subjects": [
            {"offering": str(world["offering"].pk), "maximum_score": "80.00"},
            {"offering": str(world["second_offering"].pk), "maximum_score": "80.00"},
        ],
    }
    assert (
        client.post(path(world, "mock/"), payload, format="json", **csrf).status_code
        == 403
    )
    settings.ACADEMIC_MOCK_PREPARER_ROLE_CODE = "synthetic-contact"
    settings.ACADEMIC_MOCK_APPROVER_ROLE_CODE = "synthetic-head"
    assert (
        client.post(path(world, "mock/"), payload, format="json", **csrf).status_code
        == 403
    )
    settings.ACADEMIC_BECE_LEVEL_CODE = "unrelated-level"
    assert (
        client.post(path(world, "mock/"), payload, format="json", **csrf).status_code
        == 403
    )
    settings.ACADEMIC_BECE_LEVEL_CODE = "synthetic-level"
    scheduled = client.post(path(world, "mock/"), payload, format="json", **csrf)
    assert scheduled.status_code == 201, scheduled.json()
    event_id = scheduled.json()["id"]
    assert scheduled.json()["kind"] == "mock" and len(scheduled.json()["subjects"]) == 2
    roster_url = path(world, f"mock/{event_id}/roster/")
    roster = client.post(
        roster_url,
        {
            "expected_activity_version": 1,
            "entries": [
                {"candidate": candidate, "eligible": True, "participation": "attended"},
                {
                    "candidate": excluded,
                    "eligible": False,
                    "participation": "not_assessed",
                },
            ],
        },
        format="json",
        **csrf,
    )
    assert roster.status_code == 200, roster.json()
    assert len(roster.json()["marks"]) == 2
    assert (
        roster.json()["quality"]["eligible"] == 1
        and roster.json()["quality"]["ineligible"] == 1
    )
    teacher = world["teacher"]
    grant(teacher, world["institution"], MOCK_ENTER)
    teach_client, teach_csrf = client_for(teacher)
    by_offering = {row["id"]: row["offering"] for row in roster.json()["subjects"]}
    marks = roster.json()["marks"]
    first = next(
        mark
        for mark in marks
        if by_offering[mark["subject"]] == str(world["offering"].pk)
    )
    second = next(
        mark
        for mark in marks
        if by_offering[mark["subject"]] == str(world["second_offering"].pk)
    )
    mark_url = path(world, f"mock/{event_id}/marks/")
    scored = {
        "participant": first["participant"],
        "subject": first["subject"],
        "state": "scored",
        "score": "0.00",
        "expected_version": 1,
    }
    absent = {
        "participant": second["participant"],
        "subject": second["subject"],
        "state": "absent",
        "expected_version": 1,
    }
    assert (
        teach_client.post(
            mark_url,
            {"expected_activity_version": 2, "marks": [absent]},
            format="json",
            **teach_csrf,
        ).status_code
        == 403
    )
    assert (
        AcademicMark.objects.filter(activity_id=event_id, state="missing").count() == 2
    )
    assert (
        client.post(
            mark_url,
            {"expected_activity_version": 2, "marks": [scored, absent]},
            format="json",
            **csrf,
        ).status_code
        == 200
    )
    assert (
        client.get(path(world, f"mock/{event_id}/marks/{first['id']}/history/")).json()[
            "results"
        ][0]["after_score"]
        == "0.00"
    )
    actions = path(world, f"mock/{event_id}/actions/")
    assert (
        client.post(
            actions + "submit/", {"expected_version": 3}, format="json", **csrf
        ).status_code
        == 200
    )
    review_client, review_csrf = client_for(reviewer)
    assert (
        review_client.post(
            actions + "moderate/", {"expected_version": 4}, format="json", **review_csrf
        ).status_code
        == 200
    )
    manager_client, manager_csrf = client_for(local_manager)
    assert (
        manager_client.post(
            actions + "approve/", {"expected_version": 5}, format="json", **manager_csrf
        ).status_code
        == 403
    )
    head_client, head_csrf = client_for(head)
    assert (
        head_client.post(
            actions + "approve/", {"expected_version": 5}, format="json", **head_csrf
        ).status_code
        == 403
    )
    enable_mfa(head)
    approved = head_client.post(
        actions + "approve/", {"expected_version": 5}, format="json", **head_csrf
    )
    assert approved.status_code == 200, approved.json()
    assert approved.json()["quality"]["complete"] is True
    initial_digest = approved.json()["snapshot_digest"]
    assert (
        head_client.post(
            actions + "publish/", {"expected_version": 6}, format="json", **head_csrf
        ).status_code
        == 200
    )
    initial = AcademicActivity.objects.get(pk=event_id)
    with pytest.raises(DjangoValidationError):
        AcademicMark.objects.bulk_create(
            [
                AcademicMark(
                    activity=initial,
                    subject_id=first["subject"],
                    participant_id=first["participant"],
                )
            ]
        )
    initial.title = "Unsafe mutation"
    with pytest.raises(DjangoValidationError):
        initial.save()
    correction = client.post(
        path(world, f"mock/{event_id}/corrections/"),
        {"reason": "Synthetic authorized result correction"},
        format="json",
        **csrf,
    )
    assert correction.status_code == 201, correction.json()
    assert (
        client.post(
            path(world, f"mock/corrections/{correction.json()['id']}/decision/"),
            {"expected_status": "pending", "decision": "authorize"},
            format="json",
            **csrf,
        ).status_code
        == 403
    )
    decision = head_client.post(
        path(world, f"mock/corrections/{correction.json()['id']}/decision/"),
        {"expected_status": "pending", "decision": "authorize"},
        format="json",
        **head_csrf,
    )
    assert decision.status_code == 200, decision.json()
    successor_id = decision.json()["successor"]
    successor = client.get(path(world, f"mock/{successor_id}/")).json()
    assert successor["previous"] == event_id and successor["revision"] == 2
    second_mark = next(
        row
        for row in successor["marks"]
        if row["subject"] != successor["marks"][0]["subject"]
    )
    corrected_mark = {
        "participant": second_mark["participant"],
        "subject": second_mark["subject"],
        "state": "scored",
        "score": "42.00",
        "expected_version": 1,
    }
    assert (
        client.post(
            path(world, f"mock/{successor_id}/marks/"),
            {"expected_activity_version": 1, "marks": [corrected_mark]},
            format="json",
            **csrf,
        ).status_code
        == 200
    )
    revised_actions = path(world, f"mock/{successor_id}/actions/")
    assert (
        client.post(
            revised_actions + "submit/", {"expected_version": 2}, format="json", **csrf
        ).status_code
        == 200
    )
    assert (
        review_client.post(
            revised_actions + "moderate/",
            {"expected_version": 3},
            format="json",
            **review_csrf,
        ).status_code
        == 200
    )
    final = head_client.post(
        revised_actions + "approve/",
        {"expected_version": 4},
        format="json",
        **head_csrf,
    )
    assert final.status_code == 200, final.json()
    assert final.json()["snapshot_digest"] != initial_digest
    assert (
        head_client.post(
            revised_actions + "publish/",
            {"expected_version": 5},
            format="json",
            **head_csrf,
        ).status_code
        == 200
    )
    assert AcademicActivity.objects.get(pk=event_id).snapshot_digest == initial_digest
    assert "Synthetic authorized" not in str(
        AuditEvent.objects.get(action="academic.mock.correction.decided").metadata
    )
    assert AuditEvent.objects.filter(action="academic.mock.approve").count() == 2
    assert not AuditEvent.objects.filter(action__contains="allowance").exists()


def test_institution_metadata_uses_effective_tenant_grants(
    world: dict[str, Any],
) -> None:
    """Global session hints cannot make a different school's operation visible."""
    from academic.permissions import WEEKLY_READ

    member = actor("synthetic-context-reader")
    grant(member, world["institution"], CANDIDATE_READ)
    grant(member, world["other"], WEEKLY_READ)
    client, _ = client_for(member)
    directory = client.get("/api/v1/academic/institutions/")
    assert directory.status_code == 200, directory.json()
    assert {item["id"] for item in directory.json()} == {
        str(world["institution"].pk),
        str(world["other"].pk),
    }
    school = client.get(path(world, "context/"))
    assert school.status_code == 200, school.json()
    assert school.json()["permissions"] == [CANDIDATE_READ]
    assert school.json()["assignments"] == []
    assert "no-store" in school.headers["Cache-Control"]
    other_context = client.get(
        f"/api/v1/institutions/{world['other'].pk}/academic/context/"
    )
    assert other_context.status_code == 200
    assert other_context.json()["permissions"] == [WEEKLY_READ]
    assert not other_context.json()["years"]
    assert (
        client.get(
            f"/api/v1/institutions/{world['other'].pk}/academic/candidates/"
        ).status_code
        == 403
    )
    no_grant = actor("synthetic-context-outsider")
    outsider, _ = client_for(no_grant)
    assert outsider.get(path(world, "context/")).status_code == 403
    assert outsider.get("/api/v1/academic/institutions/").json() == []


def test_candidate_scoped_history_minimizes_roster_marks_and_quality(
    world: dict[str, Any],
) -> None:
    """Candidate 360 and candidate-filtered history never embed peer records."""
    from academic.permissions import WEEKLY_READ, WEEKLY_SCHEDULE
    from academic.tests.conftest import make_candidate

    scheduler = actor("synthetic-minimized-scheduler")
    grant(scheduler, world["institution"], WEEKLY_SCHEDULE)
    first = make_candidate(world, scheduler, "Scoped One")
    second = make_candidate(world, scheduler, "Scoped Two")
    reader = actor("synthetic-minimized-reader")
    grant(reader, world["institution"], CANDIDATE_READ, WEEKLY_READ)
    client, csrf = client_for(scheduler)
    created = client.post(
        path(world, "weekly/"),
        {
            "academic_year": str(world["year"].pk),
            "school_class": str(world["class"].pk),
            "stream": str(world["stream"].pk),
            "teacher_assignment": str(world["assignment"].pk),
            "scheduled_for": "2026-03-07",
            "title": "Synthetic scoped exercise",
            "assessment_type": "Synthetic",
            "subjects": [
                {"offering": str(world["offering"].pk), "maximum_score": "20.00"}
            ],
        },
        format="json",
        **csrf,
    )
    assert created.status_code == 201, created.json()
    activity_id = created.json()["id"]
    roster = client.post(
        path(world, f"weekly/{activity_id}/roster/"),
        {
            "expected_activity_version": 1,
            "entries": [
                {"candidate": first, "eligible": True, "participation": "attended"},
                {
                    "candidate": second,
                    "eligible": False,
                    "participation": "not_assessed",
                },
            ],
        },
        format="json",
        **csrf,
    )
    assert roster.status_code == 200, roster.json()
    reader_client, _ = client_for(reader)
    profile = reader_client.get(path(world, f"candidates/{first}/profile/"))
    assert profile.status_code == 200
    record = profile.json()["sections"]["assessments"]["records"][0]
    assert {row["candidate"] for row in record["participants"]} == {first}
    assert {row["candidate"] for row in record["marks"]} == {first}
    assert record["quality"]["eligible"] == 1
    assert record["quality"]["ineligible"] == 0
    url = path(world, f"weekly/?candidate={first}")
    page = reader_client.get(url)
    assert page.status_code == 200, page.json()
    assert page.json()["count"] == 1
    filtered = page.json()["results"][0]
    assert filtered["participants"] == record["participants"]
    assert filtered["quality"] == record["quality"]
    assert second not in str(filtered)
    detail = reader_client.get(path(world, f"weekly/{activity_id}/?candidate={first}"))
    assert detail.status_code == 200 and second not in str(detail.json())
    assert (
        reader_client.get(path(world, "weekly/?candidate=not-a-uuid")).status_code
        == 400
    )


def test_candidate_placement_lifecycle_rejects_overlap_in_one_year(
    world: dict[str, Any],
) -> None:
    from datetime import date

    from academic.models import CandidatePlacement

    writer = actor("synthetic-placement-writer")
    grant(writer, world["institution"], CANDIDATE_WRITE, CANDIDATE_READ)
    client, csrf = client_for(writer)
    initial = client.post(
        path(world, "candidates/"),
        candidate_data(world, "Placed"),
        format="json",
        **csrf,
    )
    assert initial.status_code == 201, initial.json()
    candidate = initial.json()["id"]
    original = CandidatePlacement.objects.get(candidate_id=candidate)
    original.enrolment.effective_until = date(2026, 3, 31)
    original.enrolment.save()  # Disposable synthetic prerequisite; production closing requires scoped Phase 03 API.
    url = path(world, f"candidates/{candidate}/placements/")
    newer = {
        "academic_year": str(world["year"].pk),
        "school_class": str(world["class"].pk),
        "stream": str(world["stream"].pk),
        "effective_from": "2026-03-01",
    }
    assert client.post(url, newer, format="json", **csrf).status_code == 409
    assert CandidatePlacement.objects.filter(candidate_id=candidate).count() == 1
    newer["effective_from"] = "2026-04-01"
    created = client.post(url, newer, format="json", **csrf)
    assert created.status_code == 201, created.json()
    assert CandidatePlacement.objects.filter(candidate_id=candidate).count() == 2


def test_reconciliation_requires_policy_even_with_unapproved_evidence(
    world: dict[str, Any],
) -> None:
    from academic.permissions import BASELINE_ENTER, CANDIDATE_RECONCILE

    steward = actor("synthetic-evidence-steward")
    grant(
        steward,
        world["institution"],
        CANDIDATE_WRITE,
        CANDIDATE_RECONCILE,
        BASELINE_ENTER,
    )
    client, csrf = client_for(steward)
    first = client.post(
        path(world, "candidates/"),
        candidate_data(world, "Evidence one"),
        format="json",
        **csrf,
    ).json()["id"]
    second = client.post(
        path(world, "candidates/"),
        candidate_data(world, "Evidence two"),
        format="json",
        **csrf,
    ).json()["id"]
    draft = client.post(
        path(world, "baselines/"),
        {
            "candidate": first,
            "academic_year": str(world["year"].pk),
            "effective_date": "2026-03-01",
            "source_label": "Synthetic source",
            "source_date": "2026-03-01",
            "observations": [],
        },
        format="json",
        **csrf,
    )
    assert draft.status_code == 201, draft.json()
    result = client.post(
        path(world, f"candidates/{first}/reconcile/"),
        {
            "canonical_candidate": second,
            "expected_version": 1,
            "reason": "Synthetic possible duplicate",
        },
        format="json",
        **csrf,
    )
    assert result.status_code == 409, result.json()
    assert result.json()["detail"] == (
        "Reconciliation with academic evidence requires a separately approved historical data policy."
    )


def test_scoped_before_after_evidence_endpoints(world: dict[str, Any]) -> None:
    from academic.permissions import (
        BASELINE_ENTER,
        BASELINE_READ,
        WEEKLY_READ,
        WEEKLY_SCHEDULE,
    )
    from academic.tests.conftest import make_candidate

    maker = actor("synthetic-evidence-reader")
    grant(
        maker,
        world["institution"],
        BASELINE_ENTER,
        BASELINE_READ,
        WEEKLY_READ,
        WEEKLY_SCHEDULE,
    )
    candidate = make_candidate(world, maker, "History Learner")
    client, csrf = client_for(maker)
    draft = client.post(
        path(world, "baselines/"),
        {
            "candidate": candidate,
            "academic_year": str(world["year"].pk),
            "effective_date": "2026-03-01",
            "source_label": "Before source",
            "source_date": "2026-03-01",
            "observations": [],
        },
        format="json",
        **csrf,
    )
    assert draft.status_code == 201, draft.json()
    baseline_id = draft.json()["id"]
    changed = client.patch(
        path(world, f"baselines/{baseline_id}/"),
        {
            "expected_version": 1,
            "reason": "Synthetic source correction",
            "source_label": "After source",
        },
        format="json",
        **csrf,
    )
    assert changed.status_code == 200, changed.json()
    baseline_history = path(world, f"baselines/{baseline_id}/history/")
    baseline_evidence = client.get(baseline_history)
    assert baseline_evidence.status_code == 200
    assert baseline_evidence.json()["count"] == 1
    edit = baseline_evidence.json()["results"][0]
    assert edit["reason"] == "Synthetic source correction"
    assert edit["before"]["source_label"] == "Before source"
    assert edit["after"]["source_label"] == "After source"
    assert "no-store" in baseline_evidence.headers["Cache-Control"]

    scheduled = client.post(
        path(world, "weekly/"),
        {
            "academic_year": str(world["year"].pk),
            "school_class": str(world["class"].pk),
            "stream": str(world["stream"].pk),
            "teacher_assignment": str(world["assignment"].pk),
            "scheduled_for": "2026-03-07",
            "title": "Before title",
            "assessment_type": "Exercise",
            "subjects": [
                {"offering": str(world["offering"].pk), "maximum_score": "25.00"}
            ],
        },
        format="json",
        **csrf,
    )
    assert scheduled.status_code == 201, scheduled.json()
    activity_id = scheduled.json()["id"]
    changed_activity = client.patch(
        path(world, f"weekly/{activity_id}/"),
        {
            "expected_version": 1,
            "title": "After title",
            "reason": "Synthetic date review",
        },
        format="json",
        **csrf,
    )
    assert changed_activity.status_code == 200, changed_activity.json()
    activity_history = path(world, f"weekly/{activity_id}/history/")
    activity_evidence = client.get(activity_history)
    assert activity_evidence.status_code == 200
    assert activity_evidence.json()["results"][0]["before"]["title"] == "Before title"
    assert activity_evidence.json()["results"][0]["after"]["title"] == "After title"

    roster = client.post(
        path(world, f"weekly/{activity_id}/roster/"),
        {
            "expected_activity_version": 2,
            "entries": [
                {
                    "candidate": candidate,
                    "eligible": True,
                    "participation": "expected",
                }
            ],
        },
        format="json",
        **csrf,
    )
    assert roster.status_code == 200, roster.json()
    participant = roster.json()["participants"][0]
    updated = client.post(
        path(world, f"weekly/{activity_id}/roster/"),
        {
            "expected_activity_version": 3,
            "entries": [
                {
                    "candidate": candidate,
                    "eligible": True,
                    "participation": "attended",
                    "expected_version": participant["version"],
                    "reason": "Synthetic attendance source verified",
                }
            ],
        },
        format="json",
        **csrf,
    )
    assert updated.status_code == 200, updated.json()
    participant_history = path(
        world, f"weekly/{activity_id}/participants/{participant['id']}/history/"
    )
    participant_evidence = client.get(participant_history)
    assert participant_evidence.status_code == 200
    assert (
        participant_evidence.json()["results"][0]["before"]["participation"]
        == "expected"
    )
    assert (
        participant_evidence.json()["results"][0]["after"]["participation"]
        == "attended"
    )

    intruder = actor("synthetic-evidence-other")
    grant(intruder, world["other"], BASELINE_READ, WEEKLY_READ)
    intruder_client, _ = client_for(intruder)
    for url in (baseline_history, activity_history, participant_history):
        assert intruder_client.get(url).status_code == 403
        other_url = url.replace(str(world["institution"].pk), str(world["other"].pk))
        assert intruder_client.get(other_url).status_code == 404


def test_registry_services_recheck_permissions_even_outside_api(
    world: dict[str, Any],
) -> None:
    from django.core.exceptions import PermissionDenied
    from django.test import RequestFactory

    from academic.services import registry

    unprivileged = actor("synthetic-direct-service-caller")
    grant(unprivileged, world["institution"], CANDIDATE_READ)
    request = RequestFactory().post("/synthetic-direct-call/")
    request.user = unprivileged
    with pytest.raises(PermissionDenied):
        registry.create_candidate(
            institution=world["institution"],
            actor=unprivileged,
            request=request,
            data=candidate_data(world, "Not registered"),
        )
    with pytest.raises(PermissionDenied):
        registry.create_guardian(
            institution=world["institution"],
            actor=unprivileged,
            request=request,
            data={"name": "Not registered", "phone": "", "email": ""},
        )
