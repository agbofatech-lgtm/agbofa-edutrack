from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from rest_framework import serializers

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
    TeachingAssignment,
)

User = get_user_model()


class InstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institution
        fields = ("id", "code", "name")
        read_only_fields = fields


class InstitutionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institution
        fields = ("id", "code", "name")
        read_only_fields = ("id",)


class ConfigurationReleaseSerializer(serializers.ModelSerializer):
    created_by = serializers.IntegerField(source="created_by_id", read_only=True)
    approved_by = serializers.IntegerField(source="approved_by_id", read_only=True)
    previous_release = serializers.UUIDField(
        source="previous_release_id", read_only=True
    )

    class Meta:
        model = ConfigurationRelease
        fields = (
            "id",
            "institution",
            "revision",
            "previous_release",
            "status",
            "effective_from",
            "created_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "created_at",
        )
        read_only_fields = fields


class ReleaseScopedSerializer(serializers.ModelSerializer):
    """Restrict every related configuration reference to the route's revision."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        release = self.context.get("release")
        institution = self.context.get("institution")
        for field in self.fields.values():
            if not isinstance(field, serializers.PrimaryKeyRelatedField):
                continue
            queryset = field.queryset
            if queryset is None:
                continue
            model = queryset.model
            if release is not None and hasattr(model, "release_id"):
                field.queryset = model.objects.filter(release=release)
            elif institution is not None and model is InstitutionStaffMembership:
                field.queryset = model.objects.filter(institution=institution)


class InstitutionSettingSerializer(ReleaseScopedSerializer):
    class Meta:
        model = InstitutionSetting
        fields = ("id", "key", "label", "description", "value_type", "value")
        read_only_fields = ("id",)


class AcademicYearSerializer(ReleaseScopedSerializer):
    class Meta:
        model = AcademicYear
        fields = ("id", "code", "name", "start_date", "end_date")
        read_only_fields = ("id",)


class AcademicTermSerializer(ReleaseScopedSerializer):
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects.none()
    )

    class Meta:
        model = AcademicTerm
        fields = (
            "id",
            "academic_year",
            "code",
            "name",
            "sequence",
            "start_date",
            "end_date",
        )
        read_only_fields = ("id",)


class EducationalLevelSerializer(ReleaseScopedSerializer):
    class Meta:
        model = EducationalLevel
        fields = ("id", "code", "name", "position")
        read_only_fields = ("id",)


class SchoolClassSerializer(ReleaseScopedSerializer):
    level = serializers.PrimaryKeyRelatedField(queryset=EducationalLevel.objects.none())

    class Meta:
        model = SchoolClass
        fields = ("id", "level", "code", "name", "position")
        read_only_fields = ("id",)


class StreamSerializer(ReleaseScopedSerializer):
    school_class = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.none()
    )

    class Meta:
        model = Stream
        fields = ("id", "school_class", "code", "name")
        read_only_fields = ("id",)


class SubjectSerializer(ReleaseScopedSerializer):
    class Meta:
        model = Subject
        fields = ("id", "code", "name", "description")
        read_only_fields = ("id",)


class SubjectOfferingSerializer(ReleaseScopedSerializer):
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects.none()
    )
    term = serializers.PrimaryKeyRelatedField(
        queryset=AcademicTerm.objects.none(), allow_null=True, required=False
    )
    school_class = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.none()
    )
    stream = serializers.PrimaryKeyRelatedField(
        queryset=Stream.objects.none(), allow_null=True, required=False
    )
    subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.none())

    class Meta:
        model = SubjectOffering
        fields = (
            "id",
            "academic_year",
            "term",
            "school_class",
            "stream",
            "subject",
        )
        read_only_fields = ("id",)


class TeachingAssignmentSerializer(ReleaseScopedSerializer):
    offering = serializers.PrimaryKeyRelatedField(
        queryset=SubjectOffering.objects.none()
    )
    staff_membership = serializers.PrimaryKeyRelatedField(
        queryset=InstitutionStaffMembership.objects.none()
    )

    class Meta:
        model = TeachingAssignment
        fields = (
            "id",
            "offering",
            "staff_membership",
            "effective_from",
            "effective_until",
        )
        read_only_fields = ("id",)


class InstitutionStaffMembershipSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True)
    )
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    created_by = serializers.IntegerField(source="created_by_id", read_only=True)

    class Meta:
        model = InstitutionStaffMembership
        fields = (
            "id",
            "user",
            "user_name",
            "user_username",
            "staff_reference",
            "effective_from",
            "effective_until",
            "created_by",
        )
        read_only_fields = ("id", "created_by")


class EnrolmentSerializer(ReleaseScopedSerializer):
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects.none()
    )
    school_class = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.none()
    )
    stream = serializers.PrimaryKeyRelatedField(
        queryset=Stream.objects.none(), allow_null=True, required=False
    )
    created_by = serializers.IntegerField(source="created_by_id", read_only=True)

    class Meta:
        model = Enrolment
        fields = (
            "id",
            "learner_reference",
            "academic_year",
            "school_class",
            "stream",
            "effective_from",
            "effective_until",
            "created_by",
        )
        read_only_fields = ("id", "created_by")


RESOURCE_SERIALIZERS: dict[str, type[serializers.ModelSerializer[Any]]] = {
    "settings": InstitutionSettingSerializer,
    "academic-years": AcademicYearSerializer,
    "terms": AcademicTermSerializer,
    "levels": EducationalLevelSerializer,
    "classes": SchoolClassSerializer,
    "streams": StreamSerializer,
    "subjects": SubjectSerializer,
    "subject-offerings": SubjectOfferingSerializer,
    "teaching-assignments": TeachingAssignmentSerializer,
}
