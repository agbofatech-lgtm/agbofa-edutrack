from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from identity.services.audit import record_audit_event
from identity.services.rbac import HasRBACPermission, authorized_scope_keys
from institutional.models import (
    ConfigurationRelease,
    Enrolment,
    Institution,
    InstitutionStaffMembership,
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
    RESOURCE_PERMISSION,
    STAFF_MANAGE,
    STAFF_READ,
)
from institutional.schema import CONFIGURATION_SCHEMA, RELEASE_FORM_SCHEMA
from institutional.serializers import (
    RESOURCE_SERIALIZERS,
    ConfigurationReleaseSerializer,
    EnrolmentSerializer,
    InstitutionCreateSerializer,
    InstitutionSerializer,
    InstitutionStaffMembershipSerializer,
)
from institutional.services import (
    approve_release,
    create_draft_release,
    submit_release,
)


class ConfigurationPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


def _api_validation_error(error: DjangoValidationError) -> ValidationError:
    if hasattr(error, "message_dict"):
        return ValidationError(error.message_dict)
    return ValidationError(error.messages)


def _not_a_draft() -> Response:
    return Response(
        {
            "detail": "Create a new draft revision before changing approved configuration."
        },
        status=status.HTTP_409_CONFLICT,
    )


class InstitutionScopedAPIView(APIView):
    """Permission boundary whose scope is taken only from the route UUID."""

    permission_classes = (IsAuthenticated, HasRBACPermission)
    required_permission = INSTITUTION_READ

    def get_authorization_scope(self, request: Request) -> tuple[str, str] | None:
        institution_id = self.kwargs.get("institution_id")
        if institution_id is None:
            return None
        return ("institution", str(institution_id))

    def get_permissions(self) -> list[Any]:
        return [IsAuthenticated(), HasRBACPermission()]


class InstitutionCollectionView(APIView):
    """List only institution scopes already granted; create is globally gated."""

    permission_classes = (IsAuthenticated,)

    def get_permissions(self) -> list[Any]:
        if self.request.method == "POST":
            self.required_permission = INSTITUTION_CREATE
            return [IsAuthenticated(), HasRBACPermission()]
        return [IsAuthenticated()]

    def get(self, request: Request) -> Response:
        has_global, allowed_keys = authorized_scope_keys(
            request.user, INSTITUTION_READ, "institution"
        )
        institutions = Institution.objects.all()
        if not has_global:
            institutions = institutions.filter(pk__in=allowed_keys)
        return Response(InstitutionSerializer(institutions, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = InstitutionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                institution = serializer.save()
                record_audit_event(
                    action="institution.created",
                    request=request._request,
                    actor=request.user,
                    subject_type="institution",
                    subject_id=str(institution.pk),
                    metadata={"institution_code": institution.code},
                )
        except DjangoValidationError as error:
            raise _api_validation_error(error) from error
        except IntegrityError as error:
            raise ValidationError("Institution code already exists.") from error
        return Response(
            InstitutionSerializer(institution).data,
            status=status.HTTP_201_CREATED,
        )


class InstitutionDetailView(InstitutionScopedAPIView):
    def get(self, request: Request, institution_id: Any) -> Response:
        institution = get_object_or_404(Institution, pk=institution_id)
        return Response(InstitutionSerializer(institution).data)


class ConfigurationSchemaView(InstitutionScopedAPIView):
    def get(self, request: Request, institution_id: Any) -> Response:
        get_object_or_404(Institution, pk=institution_id)
        return Response(
            {
                "resources": CONFIGURATION_SCHEMA,
                "release_fields": RELEASE_FORM_SCHEMA,
                "effective_date_semantics": (
                    "Configuration releases take effect on their effective_from date; "
                    "the latest approved release on or before the requested date applies."
                ),
                "policy_values_seeded": False,
            }
        )


class CreateReleaseSerializer(serializers.Serializer):
    effective_from = serializers.DateField()
    source_release = serializers.UUIDField(required=False, allow_null=True)


class ConfigurationReleaseCollectionView(InstitutionScopedAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = (
            CONFIGURATION_MANAGE
            if self.request.method == "POST"
            else CONFIGURATION_READ
        )
        return super().get_permissions()

    def get(self, request: Request, institution_id: Any) -> Response:
        institution = get_object_or_404(Institution, pk=institution_id)
        releases = ConfigurationRelease.objects.filter(institution=institution)
        return Response(ConfigurationReleaseSerializer(releases, many=True).data)

    def post(self, request: Request, institution_id: Any) -> Response:
        institution = get_object_or_404(Institution, pk=institution_id)
        serializer = CreateReleaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source_id = serializer.validated_data.get("source_release")
        source = None
        if source_id is not None:
            source = get_object_or_404(
                ConfigurationRelease,
                pk=source_id,
                institution=institution,
                status=ConfigurationRelease.Status.APPROVED,
            )
        try:
            release = create_draft_release(
                institution=institution,
                actor=request.user,
                effective_from=serializer.validated_data["effective_from"],
                source_release=source,
                request=request._request,
            )
        except DjangoValidationError as error:
            raise _api_validation_error(error) from error
        except IntegrityError as error:
            raise ValidationError(
                "The configuration revision could not be created."
            ) from error
        return Response(
            ConfigurationReleaseSerializer(release).data,
            status=status.HTTP_201_CREATED,
        )


class ConfigurationReleaseActionView(InstitutionScopedAPIView):
    def get_permissions(self) -> list[Any]:
        action = self.kwargs.get("action")
        codes = {
            "submit": CONFIGURATION_SUBMIT,
            "approve": CONFIGURATION_APPROVE,
        }
        required_permission = codes.get(action)
        if required_permission is None:
            from django.http import Http404

            raise Http404
        self.required_permission = required_permission
        return super().get_permissions()

    def post(
        self, request: Request, institution_id: Any, release_id: Any, action: str
    ) -> Response:
        release = get_object_or_404(
            ConfigurationRelease,
            pk=release_id,
            institution_id=institution_id,
        )
        try:
            if action == "submit":
                release = submit_release(
                    release=release,
                    actor=request.user,
                    request=request._request,
                )
            elif action == "approve":
                release = approve_release(
                    release=release,
                    actor=request.user,
                    request=request._request,
                )
            else:
                return Response(
                    {"detail": "Unknown configuration action."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except DjangoValidationError as error:
            raise _api_validation_error(error) from error
        except IntegrityError as error:
            raise ValidationError(
                "The release conflicts with another approved effective date."
            ) from error
        return Response(ConfigurationReleaseSerializer(release).data)


class ConfigurationResourceView(InstitutionScopedAPIView):
    """CRUD for release-scoped resources; no hard delete or approved edits."""

    def get_permissions(self) -> list[Any]:
        resource = self.kwargs.get("resource", "")
        manage_permission = RESOURCE_PERMISSION.get(resource)
        if manage_permission is None:
            from django.http import Http404

            raise Http404
        self.required_permission = (
            CONFIGURATION_READ
            if self.request.method in {"GET", "HEAD"}
            else manage_permission
        )
        return super().get_permissions()

    def _get_context(
        self, institution_id: Any, release_id: Any
    ) -> tuple[Institution, ConfigurationRelease]:
        institution = get_object_or_404(Institution, pk=institution_id)
        release = get_object_or_404(
            ConfigurationRelease,
            pk=release_id,
            institution=institution,
        )
        return institution, release

    def _get_serializer_class(
        self, resource: str
    ) -> type[serializers.ModelSerializer[Any]]:
        serializer_class = RESOURCE_SERIALIZERS.get(resource)
        if serializer_class is None:
            from django.http import Http404

            raise Http404
        return serializer_class

    def _queryset(self, resource: str, release: ConfigurationRelease):
        serializer_class = self._get_serializer_class(resource)
        model = serializer_class.Meta.model
        return model.objects.filter(release=release)

    def get(
        self,
        request: Request,
        institution_id: Any,
        release_id: Any,
        resource: str,
        record_id: Any = None,
    ) -> Response:
        institution, release = self._get_context(institution_id, release_id)
        serializer_class = self._get_serializer_class(resource)
        queryset = self._queryset(resource, release)
        if record_id is not None:
            record = get_object_or_404(queryset, pk=record_id)
            return Response(
                serializer_class(
                    record,
                    context={
                        "request": request,
                        "release": release,
                        "institution": institution,
                    },
                ).data
            )
        paginator = ConfigurationPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = serializer_class(
            page,
            many=True,
            context={
                "request": request,
                "release": release,
                "institution": institution,
            },
        ).data
        return paginator.get_paginated_response(data)

    def post(
        self,
        request: Request,
        institution_id: Any,
        release_id: Any,
        resource: str,
    ) -> Response:
        institution, release = self._get_context(institution_id, release_id)
        if release.status != ConfigurationRelease.Status.DRAFT:
            return _not_a_draft()
        serializer_class = self._get_serializer_class(resource)
        serializer = serializer_class(
            data=request.data,
            context={
                "request": request,
                "release": release,
                "institution": institution,
            },
        )
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                record = serializer.save(release=release)
                record_audit_event(
                    action="institution.configuration.record.created",
                    request=request._request,
                    actor=request.user,
                    subject_type=f"institution.{resource}",
                    subject_id=str(record.pk),
                    metadata={
                        "institution_id": str(institution.pk),
                        "release_id": str(release.pk),
                        "revision": release.revision,
                    },
                )
        except DjangoValidationError as error:
            raise _api_validation_error(error) from error
        except IntegrityError as error:
            raise ValidationError(
                "A matching configuration record already exists."
            ) from error
        return Response(
            serializer_class(
                record,
                context={
                    "request": request,
                    "release": release,
                    "institution": institution,
                },
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def patch(
        self,
        request: Request,
        institution_id: Any,
        release_id: Any,
        resource: str,
        record_id: Any,
    ) -> Response:
        institution, release = self._get_context(institution_id, release_id)
        if release.status != ConfigurationRelease.Status.DRAFT:
            return _not_a_draft()
        serializer_class = self._get_serializer_class(resource)
        record = get_object_or_404(self._queryset(resource, release), pk=record_id)
        serializer = serializer_class(
            record,
            data=request.data,
            partial=True,
            context={
                "request": request,
                "release": release,
                "institution": institution,
            },
        )
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                record = serializer.save()
                record_audit_event(
                    action="institution.configuration.record.updated",
                    request=request._request,
                    actor=request.user,
                    subject_type=f"institution.{resource}",
                    subject_id=str(record.pk),
                    metadata={
                        "institution_id": str(institution.pk),
                        "release_id": str(release.pk),
                        "revision": release.revision,
                    },
                )
        except DjangoValidationError as error:
            raise _api_validation_error(error) from error
        except IntegrityError as error:
            raise ValidationError(
                "A matching configuration record already exists."
            ) from error
        return Response(
            serializer_class(
                record,
                context={
                    "request": request,
                    "release": release,
                    "institution": institution,
                },
            ).data
        )


class InstitutionStaffMembershipView(InstitutionScopedAPIView):
    """Read/create/update staff affiliations, never role or permission grants."""

    def get_permissions(self) -> list[Any]:
        self.required_permission = (
            STAFF_READ if self.request.method in {"GET", "HEAD"} else STAFF_MANAGE
        )
        return super().get_permissions()

    def get_queryset(self, institution_id: Any):
        return InstitutionStaffMembership.objects.filter(
            institution_id=institution_id
        ).select_related("user")

    def get(
        self,
        request: Request,
        institution_id: Any,
        membership_id: Any = None,
    ) -> Response:
        institution = get_object_or_404(Institution, pk=institution_id)
        queryset = self.get_queryset(institution.pk)
        if membership_id is not None:
            membership = get_object_or_404(queryset, pk=membership_id)
            data = InstitutionStaffMembershipSerializer(membership).data
            return Response(data)
        paginator = ConfigurationPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = InstitutionStaffMembershipSerializer(page, many=True).data
        return paginator.get_paginated_response(data)

    def post(self, request: Request, institution_id: Any) -> Response:
        institution = get_object_or_404(Institution, pk=institution_id)
        serializer = InstitutionStaffMembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                membership = serializer.save(
                    institution=institution,
                    created_by=request.user,
                )
                record_audit_event(
                    action="institution.staff.membership.created",
                    request=request._request,
                    actor=request.user,
                    subject_type="institution.staff_membership",
                    subject_id=str(membership.pk),
                    metadata={"institution_id": str(institution.pk)},
                )
        except DjangoValidationError as error:
            raise _api_validation_error(error) from error
        except IntegrityError as error:
            raise ValidationError(
                "A matching staff membership already exists."
            ) from error
        return Response(
            InstitutionStaffMembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )

    def patch(
        self,
        request: Request,
        institution_id: Any,
        membership_id: Any,
    ) -> Response:
        institution = get_object_or_404(Institution, pk=institution_id)
        membership = get_object_or_404(
            self.get_queryset(institution.pk), pk=membership_id
        )
        if (
            set(request.data) != {"effective_until"}
            or membership.effective_until is not None
        ):
            raise ValidationError(
                "Only an open membership may be closed by setting effective_until."
            )
        if request.data.get("effective_until") is None:
            raise ValidationError("A closed membership requires an end date.")
        previous_end = membership.effective_until
        serializer = InstitutionStaffMembershipSerializer(
            membership,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                membership = serializer.save(
                    institution=institution,
                    created_by=membership.created_by,
                )
                record_audit_event(
                    action="institution.staff.membership.updated",
                    request=request._request,
                    actor=request.user,
                    subject_type="institution.staff_membership",
                    subject_id=str(membership.pk),
                    metadata={
                        "institution_id": str(institution.pk),
                        "effective_until_before": (
                            previous_end.isoformat() if previous_end else None
                        ),
                        "effective_until_after": (
                            membership.effective_until.isoformat()
                            if membership.effective_until
                            else None
                        ),
                    },
                )
        except DjangoValidationError as error:
            raise _api_validation_error(error) from error
        return Response(InstitutionStaffMembershipSerializer(membership).data)


class EnrolmentView(InstitutionScopedAPIView):
    """Opaque-reference enrolments; no learner personal information is exposed."""

    def get_permissions(self) -> list[Any]:
        self.required_permission = (
            ENROLMENT_READ
            if self.request.method in {"GET", "HEAD"}
            else ENROLMENT_MANAGE
        )
        return super().get_permissions()

    def _get_context(
        self, institution_id: Any, release_id: Any
    ) -> tuple[Institution, ConfigurationRelease]:
        institution = get_object_or_404(Institution, pk=institution_id)
        release = get_object_or_404(
            ConfigurationRelease,
            pk=release_id,
            institution=institution,
        )
        return institution, release

    def _get_queryset(self, institution: Institution, release: ConfigurationRelease):
        return Enrolment.objects.filter(
            institution=institution,
            academic_year__release=release,
        ).select_related("academic_year", "school_class", "stream")

    def get(
        self,
        request: Request,
        institution_id: Any,
        release_id: Any,
        enrolment_id: Any = None,
    ) -> Response:
        institution, release = self._get_context(institution_id, release_id)
        queryset = self._get_queryset(institution, release)
        if enrolment_id is not None:
            enrolment = get_object_or_404(queryset, pk=enrolment_id)
            return Response(
                EnrolmentSerializer(enrolment, context={"release": release}).data
            )
        paginator = ConfigurationPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = EnrolmentSerializer(
            page, many=True, context={"release": release, "institution": institution}
        ).data
        return paginator.get_paginated_response(data)

    def post(self, request: Request, institution_id: Any, release_id: Any) -> Response:
        institution, release = self._get_context(institution_id, release_id)
        if release.status != ConfigurationRelease.Status.APPROVED:
            return Response(
                {"detail": "Enrolments require an approved configuration release."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = EnrolmentSerializer(
            data=request.data,
            context={"release": release, "institution": institution},
        )
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                enrolment = serializer.save(
                    institution=institution,
                    created_by=request.user,
                )
                record_audit_event(
                    action="institution.enrolment.created",
                    request=request._request,
                    actor=request.user,
                    subject_type="institution.enrolment",
                    subject_id=str(enrolment.pk),
                    metadata={
                        "institution_id": str(institution.pk),
                        "release_id": str(release.pk),
                    },
                )
        except DjangoValidationError as error:
            raise _api_validation_error(error) from error
        except IntegrityError as error:
            raise ValidationError("The enrolment could not be recorded.") from error
        return Response(
            EnrolmentSerializer(
                enrolment,
                context={"release": release, "institution": institution},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def patch(
        self,
        request: Request,
        institution_id: Any,
        release_id: Any,
        enrolment_id: Any,
    ) -> Response:
        institution, release = self._get_context(institution_id, release_id)
        enrolment = get_object_or_404(
            self._get_queryset(institution, release), pk=enrolment_id
        )
        if (
            set(request.data) != {"effective_until"}
            or enrolment.effective_until is not None
        ):
            raise ValidationError(
                "Only an open enrolment may be closed by setting effective_until."
            )
        if request.data.get("effective_until") is None:
            raise ValidationError("A closed enrolment requires an end date.")
        previous_end = enrolment.effective_until
        serializer = EnrolmentSerializer(
            enrolment,
            data=request.data,
            partial=True,
            context={"release": release, "institution": institution},
        )
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                enrolment = serializer.save()
                record_audit_event(
                    action="institution.enrolment.updated",
                    request=request._request,
                    actor=request.user,
                    subject_type="institution.enrolment",
                    subject_id=str(enrolment.pk),
                    metadata={
                        "institution_id": str(institution.pk),
                        "effective_until_before": (
                            previous_end.isoformat() if previous_end else None
                        ),
                        "effective_until_after": (
                            enrolment.effective_until.isoformat()
                            if enrolment.effective_until
                            else None
                        ),
                    },
                )
        except DjangoValidationError as error:
            raise _api_validation_error(error) from error
        return Response(
            EnrolmentSerializer(
                enrolment,
                context={"release": release, "institution": institution},
            ).data
        )
