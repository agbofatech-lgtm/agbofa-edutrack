"""Strict, bounded API inputs and minimal role-scoped output representations."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from rest_framework import serializers

from academic.models import (
    AcademicActivity,
    AcademicMark,
    ActivityCorrection,
    ActivityEdit,
    ActivityParticipant,
    ActivitySubject,
    Baseline,
    BaselineCorrection,
    BaselineEdit,
    BaselineObservation,
    Candidate,
    CandidateImport,
    CandidatePlacement,
    Guardian,
    GuardianLink,
    MarkChange,
    ParticipationChange,
)
from academic.validation import canonical_name


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data: Any) -> Any:
        if not isinstance(data, dict):
            raise serializers.ValidationError("Expected an object.")
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {field: "Unknown field." for field in sorted(unknown)}
            )
        return super().to_internal_value(data)


class CandidateInput(StrictSerializer):
    given_name = serializers.CharField(max_length=100)
    family_name = serializers.CharField(max_length=100)
    birth_date = serializers.DateField(required=False, allow_null=True)
    academic_year = serializers.UUIDField()
    school_class = serializers.UUIDField()
    stream = serializers.UUIDField(required=False, allow_null=True)
    effective_from = serializers.DateField()

    def validate_given_name(self, value: str) -> str:
        return self._validate_name(value)

    def validate_family_name(self, value: str) -> str:
        return self._validate_name(value)

    @staticmethod
    def _validate_name(value: str) -> str:
        name = canonical_name(value)
        if not name or any(ord(char) < 32 for char in name):
            raise serializers.ValidationError("Enter a valid name.")
        return name

    def validate_birth_date(self, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise serializers.ValidationError("Birth date cannot be in the future.")
        return value


class CandidatePatch(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500)
    given_name = serializers.CharField(max_length=100, required=False)
    family_name = serializers.CharField(max_length=100, required=False)
    birth_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=(Candidate.Status.ACTIVE, Candidate.Status.INACTIVE), required=False
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        for key in ("given_name", "family_name"):
            if key in attrs:
                attrs[key] = CandidateInput._validate_name(attrs[key])
        if attrs.get("birth_date") and attrs["birth_date"] > date.today():
            raise serializers.ValidationError(
                {"birth_date": "Birth date cannot be in the future."}
            )
        if not set(attrs) - {"expected_version", "reason"}:
            raise serializers.ValidationError("Supply a change to make.")
        return attrs


class PlacementInput(StrictSerializer):
    academic_year = serializers.UUIDField()
    school_class = serializers.UUIDField()
    stream = serializers.UUIDField(required=False, allow_null=True)
    effective_from = serializers.DateField()


class ReconcileInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    canonical_candidate = serializers.UUIDField()
    reason = serializers.CharField(max_length=500)


class ImportInput(StrictSerializer):
    idempotency_key = serializers.UUIDField()
    rows = serializers.ListField(
        child=serializers.JSONField(), min_length=1, max_length=100
    )


class GuardianInput(StrictSerializer):
    name = serializers.CharField(max_length=160)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True)

    def validate_name(self, value: str) -> str:
        return CandidateInput._validate_name(value)

    def validate_phone(self, value: str) -> str:
        if value and not re.fullmatch(r"\+?[0-9() \-]{5,32}", value):
            raise serializers.ValidationError(
                "Use digits and optional phone separators."
            )
        return value


class GuardianPatch(GuardianInput):
    name = serializers.CharField(max_length=160, required=False)
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not set(attrs) - {"expected_version", "reason"}:
            raise serializers.ValidationError("Supply a change to make.")
        return attrs


class GuardianLinkInput(StrictSerializer):
    guardian = serializers.UUIDField()
    relationship = serializers.CharField(max_length=80)
    contact_authorized = serializers.BooleanField()


class GuardianLinkPatch(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500)
    relationship = serializers.CharField(max_length=80, required=False)
    contact_authorized = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not set(attrs) - {"expected_version", "reason"}:
            raise serializers.ValidationError("Supply a change to make.")
        return attrs


class ObservationInput(StrictSerializer):
    offering = serializers.UUIDField()
    state = serializers.ChoiceField(choices=BaselineObservation.State.choices)
    score = serializers.DecimalField(
        max_digits=7, decimal_places=2, required=False, allow_null=True
    )
    maximum_score = serializers.DecimalField(
        max_digits=7, decimal_places=2, required=False, allow_null=True
    )


class BaselineInput(StrictSerializer):
    candidate = serializers.UUIDField()
    academic_year = serializers.UUIDField()
    effective_date = serializers.DateField()
    source_label = serializers.CharField(max_length=160)
    source_date = serializers.DateField()
    observations = ObservationInput(many=True, allow_empty=True, max_length=40)


class BaselinePatch(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500)
    effective_date = serializers.DateField(required=False)
    source_label = serializers.CharField(max_length=160, required=False)
    source_date = serializers.DateField(required=False)
    observations = ObservationInput(
        many=True, allow_empty=True, max_length=40, required=False
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not set(attrs) - {"expected_version", "reason"}:
            raise serializers.ValidationError("Supply a change to make.")
        return attrs


class VersionInput(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)


class ReviewInput(VersionInput):
    reason = serializers.CharField(max_length=500, required=False)


class CorrectionInput(StrictSerializer):
    reason = serializers.CharField(max_length=500)


class CorrectionDecision(StrictSerializer):
    expected_status = serializers.ChoiceField(choices=("pending",))
    decision = serializers.ChoiceField(choices=("authorize", "reject"))


class BlueprintInput(StrictSerializer):
    offering = serializers.UUIDField()
    maximum_score = serializers.DecimalField(
        max_digits=7, decimal_places=2, min_value=Decimal("0.01")
    )


class ActivityInput(StrictSerializer):
    academic_year = serializers.UUIDField()
    school_class = serializers.UUIDField()
    stream = serializers.UUIDField(required=False, allow_null=True)
    teacher_assignment = serializers.UUIDField(required=False, allow_null=True)
    scheduled_for = serializers.DateField()
    title = serializers.CharField(max_length=160)
    assessment_type = serializers.CharField(
        max_length=80, required=False, allow_blank=True
    )
    subjects = BlueprintInput(many=True, allow_empty=False, max_length=20)


class ActivityPatch(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=500)
    scheduled_for = serializers.DateField(required=False)
    title = serializers.CharField(max_length=160, required=False)
    assessment_type = serializers.CharField(max_length=80, required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not set(attrs) - {"expected_version", "reason"}:
            raise serializers.ValidationError("Supply a change to make.")
        return attrs


class ParticipantInput(StrictSerializer):
    candidate = serializers.UUIDField()
    eligible = serializers.BooleanField()
    participation = serializers.ChoiceField(
        choices=ActivityParticipant.Participation.choices
    )
    expected_version = serializers.IntegerField(min_value=1, required=False)
    reason = serializers.CharField(max_length=500, required=False)


class ParticipantBulkInput(StrictSerializer):
    expected_activity_version = serializers.IntegerField(min_value=1)
    entries = ParticipantInput(many=True, allow_empty=False, max_length=100)


class MarkInput(StrictSerializer):
    participant = serializers.UUIDField()
    subject = serializers.UUIDField()
    state = serializers.ChoiceField(choices=BaselineObservation.State.choices)
    score = serializers.DecimalField(
        max_digits=7, decimal_places=2, required=False, allow_null=True
    )
    expected_version = serializers.IntegerField(min_value=1)


class MarkBulkInput(StrictSerializer):
    expected_activity_version = serializers.IntegerField(min_value=1)
    marks = MarkInput(many=True, allow_empty=False, max_length=100)


class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = (
            "id",
            "given_name",
            "family_name",
            "birth_date",
            "status",
            "canonical_candidate",
            "version",
            "created_at",
        )


class CandidatePlacementSerializer(serializers.ModelSerializer):
    academic_year = serializers.UUIDField(source="enrolment.academic_year_id")
    school_class = serializers.UUIDField(source="enrolment.school_class_id")
    stream = serializers.UUIDField(source="enrolment.stream_id")
    effective_from = serializers.DateField(source="enrolment.effective_from")
    effective_until = serializers.DateField(source="enrolment.effective_until")

    class Meta:
        model = CandidatePlacement
        fields = (
            "id",
            "academic_year",
            "school_class",
            "stream",
            "effective_from",
            "effective_until",
        )


class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = ("id", "name", "phone", "email", "version")


class GuardianLinkSerializer(serializers.ModelSerializer):
    guardian_detail = serializers.SerializerMethodField()

    def get_guardian_detail(self, obj: GuardianLink) -> dict[str, Any]:
        data = dict(GuardianSerializer(obj.guardian).data)
        if not obj.contact_authorized or not obj.is_active:
            data["phone"] = ""
            data["email"] = ""
        return data

    class Meta:
        model = GuardianLink
        fields = (
            "id",
            "candidate",
            "guardian",
            "guardian_detail",
            "relationship",
            "contact_authorized",
            "is_active",
            "version",
        )


class BaselineObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BaselineObservation
        fields = ("id", "offering", "state", "score", "maximum_score")


class BaselineSerializer(serializers.ModelSerializer):
    observations = BaselineObservationSerializer(many=True, read_only=True)
    quality = serializers.SerializerMethodField()

    def get_quality(self, obj: Baseline) -> dict[str, int | bool]:
        observations = list(obj.observations.all())
        counts = {
            state: sum(row.state == state for row in observations)
            for state in ("scored", "absent", "missing", "not_assessed")
        }
        # No approved BA-0 subject-coverage policy exists yet. Resolving all
        # *entered* rows does not establish that every expected subject was
        # assessed; approval attests source provenance, not completeness.
        return {
            **counts,
            "observations_resolved": bool(observations)
            and not counts["missing"]
            and not counts["not_assessed"],
            "coverage_verified": False,
            "complete": False,
        }

    class Meta:
        model = Baseline
        fields = (
            "id",
            "candidate",
            "academic_year",
            "revision",
            "previous",
            "status",
            "version",
            "effective_date",
            "source_label",
            "source_date",
            "created_by",
            "submitted_by",
            "approved_by",
            "submitted_at",
            "approved_at",
            "snapshot_digest",
            "observations",
            "quality",
        )


class BaselineCorrectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BaselineCorrection
        fields = (
            "id",
            "baseline",
            "reason",
            "status",
            "requested_by",
            "authorized_by",
            "successor",
            "created_at",
            "resolved_at",
        )


class ActivitySubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivitySubject
        fields = ("id", "offering", "maximum_score")


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityParticipant
        fields = ("id", "candidate", "eligible", "participation", "version")


class MarkSerializer(serializers.ModelSerializer):
    candidate = serializers.UUIDField(source="participant.candidate_id", read_only=True)

    class Meta:
        model = AcademicMark
        fields = (
            "id",
            "subject",
            "participant",
            "candidate",
            "state",
            "score",
            "version",
            "recorded_by",
        )


class ActivitySerializer(serializers.ModelSerializer):
    subjects = ActivitySubjectSerializer(many=True, read_only=True)
    participants = ParticipantSerializer(many=True, read_only=True)
    marks = MarkSerializer(many=True, read_only=True)
    quality = serializers.SerializerMethodField()

    class Meta:
        model = AcademicActivity
        fields = (
            "id",
            "kind",
            "academic_year",
            "school_class",
            "stream",
            "teacher_assignment",
            "scheduled_for",
            "title",
            "assessment_type",
            "revision",
            "previous",
            "status",
            "version",
            "snapshot_digest",
            "created_by",
            "submitted_by",
            "moderated_by",
            "approved_by",
            "published_by",
            "submitted_at",
            "moderated_at",
            "approved_at",
            "published_at",
            "subjects",
            "participants",
            "marks",
            "quality",
        )

    def get_quality(self, obj: AcademicActivity) -> dict[str, int | bool]:
        participants = list(obj.participants.all())
        marks = list(obj.marks.all())
        return {
            "eligible": sum(p.eligible for p in participants),
            "ineligible": sum(not p.eligible for p in participants),
            "expected": sum(
                p.participation == "expected" for p in participants if p.eligible
            ),
            "scored": sum(m.state == "scored" for m in marks),
            "absent": sum(m.state == "absent" for m in marks),
            "missing": sum(m.state == "missing" for m in marks),
            "not_assessed": sum(m.state == "not_assessed" for m in marks),
            "complete": all(
                p.participation != "expected" for p in participants if p.eligible
            )
            and all(m.state not in ("missing", "not_assessed") for m in marks)
            and any(p.eligible for p in participants),
        }


class ActivityCorrectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityCorrection
        fields = (
            "id",
            "activity",
            "reason",
            "status",
            "requested_by",
            "authorized_by",
            "successor",
            "created_at",
            "resolved_at",
        )


class ImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateImport
        fields = (
            "id",
            "idempotency_key",
            "row_count",
            "error_count",
            "status",
            "created_at",
            "applied_at",
        )


class MarkChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarkChange
        fields = (
            "id",
            "version",
            "before_state",
            "before_score",
            "after_state",
            "after_score",
            "actor",
            "created_at",
        )


class BaselineEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = BaselineEdit
        fields = ("id", "version", "before", "after", "reason", "actor", "created_at")


class ActivityEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityEdit
        fields = ("id", "version", "before", "after", "reason", "actor", "created_at")


class ParticipationChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParticipationChange
        fields = (
            "id",
            "participant",
            "version",
            "before",
            "after",
            "reason",
            "actor",
            "created_at",
        )
