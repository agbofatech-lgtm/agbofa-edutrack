"""Session/CSRF-protected, exact-institution academic API entry points."""

from __future__ import annotations

import uuid
from typing import Any, cast

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from academic.models import (
    AcademicActivity,
    AcademicMark,
    ActivityCorrection,
    ActivityEdit,
    ActivityParticipant,
    Baseline,
    BaselineCorrection,
    BaselineEdit,
    Candidate,
    CandidateChange,
    CandidateImport,
    CandidatePlacement,
    Guardian,
    GuardianChange,
    GuardianLink,
    MarkChange,
    ParticipationChange,
)
from academic.permissions import (
    ACADEMIC_ACCESS_CODES,
    ACTIVITY_PERMISSIONS,
    BASELINE_APPROVE,
    BASELINE_CORRECT,
    BASELINE_CORRECTION_AUTHORIZE,
    BASELINE_ENTER,
    BASELINE_READ,
    BASELINE_SUBMIT,
    CANDIDATE_IMPORT,
    CANDIDATE_READ,
    CANDIDATE_RECONCILE,
    CANDIDATE_WRITE,
    GUARDIAN_READ,
    GUARDIAN_WRITE,
)
from academic.serializers import (
    ActivityCorrectionSerializer,
    ActivityEditSerializer,
    ActivityInput,
    ActivityPatch,
    ActivitySerializer,
    BaselineCorrectionSerializer,
    BaselineEditSerializer,
    BaselineInput,
    BaselinePatch,
    BaselineSerializer,
    CandidateInput,
    CandidatePatch,
    CandidatePlacementSerializer,
    CandidateSerializer,
    CorrectionDecision,
    CorrectionInput,
    GuardianInput,
    GuardianLinkInput,
    GuardianLinkPatch,
    GuardianLinkSerializer,
    GuardianPatch,
    GuardianSerializer,
    ImportInput,
    ImportSerializer,
    MarkBulkInput,
    MarkChangeSerializer,
    ParticipantBulkInput,
    ParticipationChangeSerializer,
    PlacementInput,
    ReconcileInput,
    ReviewInput,
    VersionInput,
)
from academic.services import activities, baselines, registry
from academic.validation import Conflict, as_api_error, require_permission
from identity.services.rbac import (
    HasRBACPermission,
    authorized_scope_keys,
    user_has_permission,
)
from institutional.models import (
    AcademicYear,
    ConfigurationRelease,
    Institution,
    SchoolClass,
    Stream,
    SubjectOffering,
    TeachingAssignment,
)
from institutional.serializers import InstitutionSerializer


class AcademicPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def page_response(
    view: APIView, request: Request, rows: Any, serializer: Any
) -> Response:
    paginator = AcademicPagination()
    page = paginator.paginate_queryset(rows, request, view=view)
    return paginator.get_paginated_response(serializer(page, many=True).data)


def validated(cls: Any, request: Request) -> dict[str, Any]:
    serializer = cls(data=request.data)
    serializer.is_valid(raise_exception=True)
    return cast(dict[str, Any], serializer.validated_data)


def _institution(institution_id: Any) -> Institution:
    return get_object_or_404(Institution, pk=institution_id)


class PrivateAcademicResponses:
    """Prevent browser/proxy storage of candidate, guardian and result records."""

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        result = super().finalize_response(request, response, *args, **kwargs)  # type: ignore[misc]
        result["Cache-Control"] = "no-store, private"
        result["Pragma"] = "no-cache"
        return cast(Response, result)


class AcademicAPIView(PrivateAcademicResponses, APIView):
    permission_classes = (IsAuthenticated, HasRBACPermission)
    required_permission = ""  # Fail closed if a view forgets an action contract.

    def get_permissions(self) -> list[Any]:
        return [IsAuthenticated(), HasRBACPermission()]

    def get_authorization_scope(self, request: Request) -> tuple[str, str] | None:
        institution_id = self.kwargs.get("institution_id")
        return (
            ("institution", str(institution_id)) if institution_id is not None else None
        )

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, DjangoValidationError):
            exc = as_api_error(exc)
        elif isinstance(exc, IntegrityError):
            exc = Conflict(
                "A conflicting academic record already exists. Reload and review before retrying."
            )
        return super().handle_exception(exc)


class AcademicInstitutionView(PrivateAcademicResponses, APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        codes = ACADEMIC_ACCESS_CODES
        global_access = False
        allowed: set[str] = set()
        for code in codes:
            has_global, keys = authorized_scope_keys(request.user, code, "institution")
            global_access |= has_global
            allowed.update(keys)
        institutions = (
            Institution.objects.all()
            if global_access
            else Institution.objects.filter(pk__in=allowed)
        )
        return Response(InstitutionSerializer(institutions, many=True).data)


class AcademicContextView(AcademicAPIView):
    required_permission = CANDIDATE_READ

    def get_permissions(self) -> list[Any]:
        # Institution-scoped metadata only; never a grant-management endpoint.
        return [IsAuthenticated()]

    def get(self, request: Request, institution_id: Any) -> Response:
        institution = _institution(institution_id)
        codes = ACADEMIC_ACCESS_CODES
        if not any(
            user_has_permission(
                request.user,
                code,
                scope_type="institution",
                scope_key=str(institution.pk),
            )
            for code in codes
        ):
            return Response(
                {"detail": "No academic metadata permission for this institution."},
                status=403,
            )
        # The session's global permission identifiers are UI hints, not tenant grants.
        # Return only effective actions for the selected institution; every endpoint
        # still checks the action and resource again before reading or writing.
        effective_permissions = [
            code
            for code in codes
            if user_has_permission(
                request.user,
                code,
                scope_type="institution",
                scope_key=str(institution.pk),
            )
        ]
        releases = ConfigurationRelease.objects.filter(
            institution=institution, status=ConfigurationRelease.Status.APPROVED
        )
        years = AcademicYear.objects.filter(release__in=releases)
        classes = SchoolClass.objects.filter(release__in=releases).select_related(
            "level"
        )
        streams = Stream.objects.filter(release__in=releases)
        offerings = SubjectOffering.objects.filter(release__in=releases).select_related(
            "subject"
        )
        assignments = TeachingAssignment.objects.filter(
            release__in=releases
        ).select_related("staff_membership")
        return Response(
            {
                "permissions": effective_permissions,
                "years": [
                    {
                        "id": str(y.pk),
                        "name": y.name,
                        "release": str(y.release_id),
                        "start_date": y.start_date,
                        "end_date": y.end_date,
                    }
                    for y in years[:500]
                ],
                "classes": [
                    {
                        "id": str(c.pk),
                        "name": c.name,
                        "release": str(c.release_id),
                        "level": c.level.name,
                        "mock_eligible": bool(settings.ACADEMIC_BECE_LEVEL_CODE)
                        and c.level.code == settings.ACADEMIC_BECE_LEVEL_CODE,
                    }
                    for c in classes[:500]
                ],
                "streams": [
                    {
                        "id": str(s.pk),
                        "name": s.name,
                        "school_class": str(s.school_class_id),
                    }
                    for s in streams[:500]
                ],
                "offerings": [
                    {
                        "id": str(o.pk),
                        "subject": o.subject.name,
                        "academic_year": str(o.academic_year_id),
                        "school_class": str(o.school_class_id),
                        "stream": str(o.stream_id) if o.stream_id else None,
                        "term": str(o.term_id) if o.term_id else None,
                    }
                    for o in offerings[:500]
                ],
                "assignments": [
                    {
                        "id": str(a.pk),
                        "offering": str(a.offering_id),
                        "user_id": a.staff_membership.user_id,
                        "effective_from": a.effective_from,
                        "effective_until": a.effective_until,
                    }
                    for a in assignments[:500]
                ]
                if any(
                    code in effective_permissions
                    for code in (
                        ACTIVITY_PERMISSIONS["weekly"]["schedule"],
                        ACTIVITY_PERMISSIONS["weekly"]["enter"],
                        ACTIVITY_PERMISSIONS["mock"]["schedule"],
                    )
                )
                else [],
                "truncated": any(
                    qs.count() > 500
                    for qs in (years, classes, streams, offerings, assignments)
                ),
            }
        )


class CandidateView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = (
            CANDIDATE_READ if self.request.method == "GET" else CANDIDATE_WRITE
        )
        return super().get_permissions()

    def get(
        self, request: Request, institution_id: Any, candidate_id: Any = None
    ) -> Response:
        institution = _institution(institution_id)
        queryset = Candidate.objects.filter(institution=institution)
        if candidate_id is not None:
            candidate = get_object_or_404(queryset, pk=candidate_id)
            response = CandidateSerializer(candidate).data
            response["placements"] = CandidatePlacementSerializer(
                CandidatePlacement.objects.filter(candidate=candidate)
                .select_related("enrolment")
                .order_by("enrolment__effective_from"),
                many=True,
            ).data
            return Response(response)
        query = request.query_params.get("q", "").strip()
        if len(query) > 80:
            raise ValidationError({"q": "Search is limited to 80 characters."})
        if query:
            queryset = queryset.filter(
                Q(given_name__icontains=query) | Q(family_name__icontains=query)
            )
        return page_response(self, request, queryset, CandidateSerializer)

    def post(self, request: Request, institution_id: Any) -> Response:
        institution = _institution(institution_id)
        candidate = registry.create_candidate(
            institution=institution,
            actor=request.user,
            request=request._request,
            data=validated(CandidateInput, request),
        )
        return Response(
            CandidateSerializer(candidate).data, status=status.HTTP_201_CREATED
        )

    def patch(
        self, request: Request, institution_id: Any, candidate_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        candidate = get_object_or_404(
            Candidate, pk=candidate_id, institution=institution
        )
        result = registry.patch_candidate(
            candidate=candidate,
            institution=institution,
            actor=request.user,
            request=request._request,
            data=validated(CandidatePatch, request),
        )
        return Response(CandidateSerializer(result).data)


class CandidatePlacementView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = (
            CANDIDATE_READ if self.request.method == "GET" else CANDIDATE_WRITE
        )
        return super().get_permissions()

    def get(self, request: Request, institution_id: Any, candidate_id: Any) -> Response:
        candidate = get_object_or_404(
            Candidate, pk=candidate_id, institution_id=institution_id
        )
        rows = (
            CandidatePlacement.objects.filter(candidate=candidate)
            .select_related("enrolment")
            .order_by("enrolment__effective_from")
        )
        return Response(CandidatePlacementSerializer(rows, many=True).data)

    def post(
        self, request: Request, institution_id: Any, candidate_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        candidate = get_object_or_404(
            Candidate, pk=candidate_id, institution=institution
        )
        result = registry.add_placement(
            candidate=candidate,
            institution=institution,
            actor=request.user,
            request=request._request,
            data=validated(PlacementInput, request),
        )
        return Response(CandidatePlacementSerializer(result).data, status=201)


class CandidateChangeView(AcademicAPIView):
    required_permission = CANDIDATE_WRITE

    def get(self, request: Request, institution_id: Any, candidate_id: Any) -> Response:
        candidate = get_object_or_404(
            Candidate, pk=candidate_id, institution_id=institution_id
        )
        rows = (
            CandidateChange.objects.filter(candidate=candidate)
            .values(
                "id", "version", "before", "after", "reason", "actor_id", "created_at"
            )
            .order_by("version")
        )
        return Response(list(rows))


class CandidateReconcileView(AcademicAPIView):
    required_permission = CANDIDATE_RECONCILE

    def post(
        self, request: Request, institution_id: Any, candidate_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        candidate = get_object_or_404(
            Candidate, pk=candidate_id, institution=institution
        )
        result = registry.reconcile_candidate(
            candidate=candidate,
            institution=institution,
            actor=request.user,
            request=request._request,
            data=validated(ReconcileInput, request),
        )
        return Response(CandidateSerializer(result).data)


class CandidateImportView(AcademicAPIView):
    required_permission = CANDIDATE_IMPORT

    def post(self, request: Request, institution_id: Any) -> Response:
        institution = _institution(institution_id)
        batch, errors = registry.preview_import(
            institution=institution,
            actor=request.user,
            request=request._request,
            data=validated(ImportInput, request),
        )
        return Response(
            {
                "batch": ImportSerializer(batch).data,
                "errors": errors,
                "valid": not errors and batch.error_count == 0,
            }
        )


class CandidateImportCommitView(AcademicAPIView):
    required_permission = CANDIDATE_IMPORT

    def get(self, request: Request, institution_id: Any, batch_id: Any) -> Response:
        batch = get_object_or_404(
            CandidateImport,
            pk=batch_id,
            institution_id=institution_id,
            actor=request.user,
        )
        return Response(ImportSerializer(batch).data)

    def post(self, request: Request, institution_id: Any, batch_id: Any) -> Response:
        institution = _institution(institution_id)
        batch = get_object_or_404(
            CandidateImport, pk=batch_id, institution=institution, actor=request.user
        )
        result, created = registry.apply_import(
            institution=institution,
            actor=request.user,
            request=request._request,
            batch=batch,
            data=validated(ImportInput, request),
        )
        return Response(
            {"created": created, "candidate_ids": [str(c.pk) for c in result]},
            status=201 if created else 200,
        )


class GuardianView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = (
            GUARDIAN_READ if self.request.method == "GET" else GUARDIAN_WRITE
        )
        return super().get_permissions()

    def get(
        self, request: Request, institution_id: Any, guardian_id: Any = None
    ) -> Response:
        institution = _institution(institution_id)
        queryset = Guardian.objects.filter(institution=institution)
        if guardian_id:
            return Response(
                GuardianSerializer(get_object_or_404(queryset, pk=guardian_id)).data
            )
        return page_response(self, request, queryset, GuardianSerializer)

    def post(self, request: Request, institution_id: Any) -> Response:
        institution = _institution(institution_id)
        result = registry.create_guardian(
            institution=institution,
            actor=request.user,
            request=request._request,
            data=validated(GuardianInput, request),
        )
        return Response(GuardianSerializer(result).data, status=201)

    def patch(
        self, request: Request, institution_id: Any, guardian_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        guardian = get_object_or_404(Guardian, pk=guardian_id, institution=institution)
        result = registry.patch_guardian(
            guardian=guardian,
            institution=institution,
            actor=request.user,
            request=request._request,
            data=validated(GuardianPatch, request),
        )
        return Response(GuardianSerializer(result).data)


class GuardianChangeView(AcademicAPIView):
    required_permission = GUARDIAN_WRITE

    def get(self, request: Request, institution_id: Any, guardian_id: Any) -> Response:
        guardian = get_object_or_404(
            Guardian, pk=guardian_id, institution_id=institution_id
        )
        return Response(
            list(
                GuardianChange.objects.filter(guardian=guardian)
                .values(
                    "id",
                    "version",
                    "before",
                    "after",
                    "reason",
                    "actor_id",
                    "created_at",
                )
                .order_by("version")
            )
        )


class GuardianLinkView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = (
            GUARDIAN_READ if self.request.method == "GET" else GUARDIAN_WRITE
        )
        return super().get_permissions()

    def _candidate(
        self, institution_id: Any, candidate_id: Any, user: Any
    ) -> Candidate:
        institution = _institution(institution_id)
        require_permission(user, CANDIDATE_READ, institution)
        return get_object_or_404(Candidate, institution=institution, pk=candidate_id)

    def get(
        self,
        request: Request,
        institution_id: Any,
        candidate_id: Any,
        link_id: Any = None,
    ) -> Response:
        candidate = self._candidate(institution_id, candidate_id, request.user)
        rows = GuardianLink.objects.filter(candidate=candidate).select_related(
            "guardian"
        )
        if link_id:
            return Response(
                GuardianLinkSerializer(get_object_or_404(rows, pk=link_id)).data
            )
        return Response(GuardianLinkSerializer(rows, many=True).data)

    def post(
        self, request: Request, institution_id: Any, candidate_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        candidate = self._candidate(institution_id, candidate_id, request.user)
        result = registry.create_link(
            candidate=candidate,
            institution=institution,
            actor=request.user,
            request=request._request,
            data=validated(GuardianLinkInput, request),
        )
        return Response(GuardianLinkSerializer(result).data, status=201)

    def patch(
        self, request: Request, institution_id: Any, candidate_id: Any, link_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        candidate = self._candidate(institution_id, candidate_id, request.user)
        link = get_object_or_404(
            GuardianLink, pk=link_id, candidate=candidate, institution=institution
        )
        result = registry.patch_link(
            link=link,
            institution=institution,
            actor=request.user,
            request=request._request,
            data=validated(GuardianLinkPatch, request),
        )
        return Response(GuardianLinkSerializer(result).data)


class BaselineView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = (
            BASELINE_READ if self.request.method == "GET" else BASELINE_ENTER
        )
        return super().get_permissions()

    def get(
        self, request: Request, institution_id: Any, baseline_id: Any = None
    ) -> Response:
        queryset = Baseline.objects.filter(
            institution_id=institution_id
        ).prefetch_related("observations")
        if baseline_id:
            return Response(
                BaselineSerializer(get_object_or_404(queryset, pk=baseline_id)).data
            )
        candidate_id = request.query_params.get("candidate")
        if candidate_id:
            queryset = queryset.filter(candidate_id=candidate_id)
        return page_response(self, request, queryset, BaselineSerializer)

    def post(self, request: Request, institution_id: Any) -> Response:
        institution = _institution(institution_id)
        result = baselines.create_baseline(
            institution=institution,
            actor=request.user,
            request=request._request,
            data=validated(BaselineInput, request),
        )
        return Response(BaselineSerializer(result).data, status=201)

    def patch(
        self, request: Request, institution_id: Any, baseline_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        baseline = get_object_or_404(Baseline, pk=baseline_id, institution=institution)
        result = baselines.patch_baseline(
            baseline=baseline,
            institution=institution,
            actor=request.user,
            request=request._request,
            data=validated(BaselinePatch, request),
        )
        return Response(BaselineSerializer(result).data)


class BaselineActionView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = {
            "submit": BASELINE_SUBMIT,
            "approve": BASELINE_APPROVE,
        }.get(self.kwargs.get("action"), "")
        return super().get_permissions()

    def post(
        self, request: Request, institution_id: Any, baseline_id: Any, action: str
    ) -> Response:
        institution = _institution(institution_id)
        baseline = get_object_or_404(Baseline, pk=baseline_id, institution=institution)
        data = validated(VersionInput, request)
        result = baselines.transition_baseline(
            baseline=baseline,
            institution=institution,
            actor=request.user,
            request=request._request,
            action=action,
            expected_version=data["expected_version"],
        )
        return Response(BaselineSerializer(result).data)


class BaselineHistoryView(AcademicAPIView):
    required_permission = BASELINE_READ

    def get(self, request: Request, institution_id: Any, baseline_id: Any) -> Response:
        baseline = get_object_or_404(
            Baseline, pk=baseline_id, institution_id=institution_id
        )
        rows = BaselineEdit.objects.filter(baseline=baseline).order_by("-version")
        return page_response(self, request, rows, BaselineEditSerializer)


class BaselineCorrectionView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = (
            BASELINE_READ if self.request.method == "GET" else BASELINE_CORRECT
        )
        return super().get_permissions()

    def get(self, request: Request, institution_id: Any, baseline_id: Any) -> Response:
        baseline = get_object_or_404(
            Baseline, institution_id=institution_id, pk=baseline_id
        )
        return Response(
            BaselineCorrectionSerializer(
                BaselineCorrection.objects.filter(baseline=baseline), many=True
            ).data
        )

    def post(self, request: Request, institution_id: Any, baseline_id: Any) -> Response:
        institution = _institution(institution_id)
        baseline = get_object_or_404(Baseline, institution=institution, pk=baseline_id)
        result = baselines.request_correction(
            baseline=baseline,
            institution=institution,
            actor=request.user,
            request=request._request,
            reason=validated(CorrectionInput, request)["reason"],
        )
        return Response(BaselineCorrectionSerializer(result).data, status=201)


class BaselineCorrectionDecisionView(AcademicAPIView):
    required_permission = BASELINE_CORRECTION_AUTHORIZE

    def post(
        self, request: Request, institution_id: Any, correction_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        correction = get_object_or_404(
            BaselineCorrection, pk=correction_id, institution=institution
        )
        data = validated(CorrectionDecision, request)
        result = baselines.decide_correction(
            correction=correction,
            institution=institution,
            actor=request.user,
            request=request._request,
            decision=data["decision"],
        )
        return Response(BaselineCorrectionSerializer(result).data)


def _candidate_activity_view(record: dict[str, Any], candidate_id: str) -> None:
    """Never include peers' roster, marks or quality in candidate-scoped views."""

    record["participants"] = [
        row for row in record["participants"] if str(row["candidate"]) == candidate_id
    ]
    record["marks"] = [
        row for row in record["marks"] if str(row["candidate"]) == candidate_id
    ]
    participants = record["participants"]
    marks = record["marks"]
    record["quality"] = {
        "eligible": sum(row["eligible"] for row in participants),
        "ineligible": sum(not row["eligible"] for row in participants),
        "expected": sum(
            row["eligible"] and row["participation"] == "expected"
            for row in participants
        ),
        **{
            state: sum(row["state"] == state for row in marks)
            for state in ("scored", "absent", "missing", "not_assessed")
        },
        "complete": bool(participants and participants[0]["eligible"])
        and participants[0]["participation"] != "expected"
        and bool(marks)
        and all(row["state"] not in ("missing", "not_assessed") for row in marks),
    }


class ActivityView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        kind = self.kwargs.get("kind")
        perms = ACTIVITY_PERMISSIONS.get(kind, {})
        self.required_permission = perms.get(
            "read" if self.request.method == "GET" else "schedule", ""
        )
        return super().get_permissions()

    def get(
        self, request: Request, institution_id: Any, kind: str, activity_id: Any = None
    ) -> Response:
        queryset = AcademicActivity.objects.filter(
            institution_id=institution_id, kind=kind
        ).prefetch_related("subjects", "participants", "marks__participant")
        candidate_id = request.query_params.get("candidate")
        if candidate_id:
            try:
                candidate_id = str(uuid.UUID(candidate_id))
            except ValueError as error:
                raise ValidationError(
                    {"candidate": "Supply a candidate UUID."}
                ) from error
        if activity_id:
            record = ActivitySerializer(
                get_object_or_404(queryset, pk=activity_id)
            ).data
            if candidate_id:
                _candidate_activity_view(record, candidate_id)
            return Response(record)
        if candidate_id:
            queryset = queryset.filter(
                participants__candidate_id=candidate_id
            ).distinct()
            paginator = AcademicPagination()
            page = paginator.paginate_queryset(queryset, request, view=self)
            records = ActivitySerializer(page, many=True).data
            for record in records:
                _candidate_activity_view(record, candidate_id)
            return paginator.get_paginated_response(records)
        return page_response(self, request, queryset, ActivitySerializer)

    def post(self, request: Request, institution_id: Any, kind: str) -> Response:
        institution = _institution(institution_id)
        result = activities.create_activity(
            institution=institution,
            actor=request.user,
            request=request._request,
            kind=kind,
            data=validated(ActivityInput, request),
        )
        return Response(ActivitySerializer(result).data, status=201)

    def patch(
        self, request: Request, institution_id: Any, kind: str, activity_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        activity = get_object_or_404(
            AcademicActivity, institution=institution, kind=kind, pk=activity_id
        )
        result = activities.patch_activity(
            activity=activity,
            institution=institution,
            actor=request.user,
            request=request._request,
            data=validated(ActivityPatch, request),
        )
        return Response(ActivitySerializer(result).data)


class ActivityRosterView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = ACTIVITY_PERMISSIONS.get(
            self.kwargs.get("kind"), {}
        ).get("schedule", "")
        return super().get_permissions()

    def post(
        self, request: Request, institution_id: Any, kind: str, activity_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        activity = get_object_or_404(
            AcademicActivity, institution=institution, kind=kind, pk=activity_id
        )
        payload = validated(ParticipantBulkInput, request)
        result = activities.upsert_participants(
            activity=activity,
            institution=institution,
            actor=request.user,
            request=request._request,
            entries=payload["entries"],
            expected_activity_version=payload["expected_activity_version"],
        )
        return Response(ActivitySerializer(result).data)


class ActivityMarksView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = ACTIVITY_PERMISSIONS.get(
            self.kwargs.get("kind"), {}
        ).get("enter", "")
        return super().get_permissions()

    def post(
        self, request: Request, institution_id: Any, kind: str, activity_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        activity = get_object_or_404(
            AcademicActivity, institution=institution, kind=kind, pk=activity_id
        )
        payload = validated(MarkBulkInput, request)
        result = activities.enter_marks(
            activity=activity,
            institution=institution,
            actor=request.user,
            request=request._request,
            entries=payload["marks"],
            expected_activity_version=payload["expected_activity_version"],
        )
        return Response(ActivitySerializer(result).data)


class ActivityHistoryView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = ACTIVITY_PERMISSIONS.get(
            self.kwargs.get("kind"), {}
        ).get("read", "")
        return super().get_permissions()

    def get(
        self, request: Request, institution_id: Any, kind: str, activity_id: Any
    ) -> Response:
        activity = get_object_or_404(
            AcademicActivity, pk=activity_id, institution_id=institution_id, kind=kind
        )
        rows = ActivityEdit.objects.filter(activity=activity).order_by("-version")
        return page_response(self, request, rows, ActivityEditSerializer)


class ParticipantHistoryView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = ACTIVITY_PERMISSIONS.get(
            self.kwargs.get("kind"), {}
        ).get("read", "")
        return super().get_permissions()

    def get(
        self,
        request: Request,
        institution_id: Any,
        kind: str,
        activity_id: Any,
        participant_id: Any,
    ) -> Response:
        participant = get_object_or_404(
            ActivityParticipant,
            pk=participant_id,
            activity_id=activity_id,
            activity__institution_id=institution_id,
            activity__kind=kind,
        )
        rows = ParticipationChange.objects.filter(participant=participant).order_by(
            "-version"
        )
        return page_response(self, request, rows, ParticipationChangeSerializer)


class MarkHistoryView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = ACTIVITY_PERMISSIONS.get(
            self.kwargs.get("kind"), {}
        ).get("read", "")
        return super().get_permissions()

    def get(
        self,
        request: Request,
        institution_id: Any,
        kind: str,
        activity_id: Any,
        mark_id: Any,
    ) -> Response:
        mark = get_object_or_404(
            AcademicMark,
            pk=mark_id,
            activity_id=activity_id,
            activity__institution_id=institution_id,
            activity__kind=kind,
        )
        changes = MarkChange.objects.filter(mark=mark).order_by("-version")
        return page_response(self, request, changes, MarkChangeSerializer)


class ActivityActionView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        kind = self.kwargs.get("kind")
        action = self.kwargs.get("action")
        key = {
            "submit": "schedule",
            "moderate": "review",
            "return": "review",
            "approve": "approve",
            "publish": "publish",
        }.get(action, "")
        self.required_permission = ACTIVITY_PERMISSIONS.get(kind, {}).get(key, "")
        return super().get_permissions()

    def post(
        self,
        request: Request,
        institution_id: Any,
        kind: str,
        activity_id: Any,
        action: str,
    ) -> Response:
        institution = _institution(institution_id)
        activity = get_object_or_404(
            AcademicActivity, pk=activity_id, institution=institution, kind=kind
        )
        data = validated(ReviewInput if action == "return" else VersionInput, request)
        result = activities.transition_activity(
            activity=activity,
            institution=institution,
            actor=request.user,
            request=request._request,
            action=action,
            expected_version=data["expected_version"],
            reason=data.get("reason", ""),
        )
        return Response(ActivitySerializer(result).data)


class ActivityCorrectionView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        kind = self.kwargs.get("kind")
        self.required_permission = ACTIVITY_PERMISSIONS.get(kind, {}).get(
            "read" if self.request.method == "GET" else "correct", ""
        )
        return super().get_permissions()

    def get(
        self, request: Request, institution_id: Any, kind: str, activity_id: Any
    ) -> Response:
        activity = get_object_or_404(
            AcademicActivity, institution_id=institution_id, pk=activity_id, kind=kind
        )
        return Response(
            ActivityCorrectionSerializer(
                ActivityCorrection.objects.filter(activity=activity), many=True
            ).data
        )

    def post(
        self, request: Request, institution_id: Any, kind: str, activity_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        activity = get_object_or_404(
            AcademicActivity, pk=activity_id, institution=institution, kind=kind
        )
        result = activities.request_correction(
            activity=activity,
            institution=institution,
            actor=request.user,
            request=request._request,
            reason=validated(CorrectionInput, request)["reason"],
        )
        return Response(ActivityCorrectionSerializer(result).data, status=201)


class ActivityCorrectionDecisionView(AcademicAPIView):
    def get_permissions(self) -> list[Any]:
        self.required_permission = ACTIVITY_PERMISSIONS.get(
            self.kwargs.get("kind"), {}
        ).get("authorize", "")
        return super().get_permissions()

    def post(
        self, request: Request, institution_id: Any, kind: str, correction_id: Any
    ) -> Response:
        institution = _institution(institution_id)
        correction = get_object_or_404(
            ActivityCorrection,
            pk=correction_id,
            institution=institution,
            activity__kind=kind,
        )
        result = activities.decide_correction(
            correction=correction,
            institution=institution,
            actor=request.user,
            request=request._request,
            decision=validated(CorrectionDecision, request)["decision"],
        )
        return Response(ActivityCorrectionSerializer(result).data)


class CandidateProfileView(AcademicAPIView):
    required_permission = CANDIDATE_READ

    def get(self, request: Request, institution_id: Any, candidate_id: Any) -> Response:
        institution = _institution(institution_id)
        candidate = get_object_or_404(
            Candidate, pk=candidate_id, institution=institution
        )

        def can(code: str) -> bool:
            return user_has_permission(
                request.user,
                code,
                scope_type="institution",
                scope_key=str(institution.pk),
            )

        sections: dict[str, Any] = {}
        if can(BASELINE_READ):
            records = Baseline.objects.filter(
                candidate=candidate, institution=institution
            ).prefetch_related("observations")
            count = records.count()
            sections["baseline"] = {
                "state": "available",
                "records": BaselineSerializer(records[:50], many=True).data,
                "count": count,
                "more_available": count > 50,
            }
        else:
            sections["baseline"] = {"state": "restricted", "records": []}
        for name, kind in (("assessments", "weekly"), ("mocks", "mock")):
            if can(ACTIVITY_PERMISSIONS[kind]["read"]):
                records = (
                    AcademicActivity.objects.filter(
                        institution=institution,
                        kind=kind,
                        participants__candidate=candidate,
                    )
                    .prefetch_related("subjects", "participants", "marks__participant")
                    .distinct()
                )
                count = records.count()
                serialized = ActivitySerializer(records[:50], many=True).data
                for record in serialized:
                    _candidate_activity_view(record, str(candidate.pk))
                sections[name] = {
                    "state": "available",
                    "records": serialized,
                    "count": count,
                    "more_available": count > 50,
                }
            else:
                sections[name] = {"state": "restricted", "records": []}
        if can(GUARDIAN_READ):
            links = GuardianLink.objects.filter(candidate=candidate).select_related(
                "guardian"
            )
            sections["guardians"] = {
                "state": "available",
                "records": GuardianLinkSerializer(links, many=True).data,
            }
        else:
            sections["guardians"] = {"state": "restricted", "records": []}
        for name in ("attendance", "interventions", "guardian_engagement"):
            sections[name] = {
                "state": "unavailable",
                "reason": "This module is not implemented in Phase 04.",
                "records": [],
            }
        return Response(
            {
                "candidate": CandidateSerializer(candidate).data,
                "placements": CandidatePlacementSerializer(
                    candidate.placements.select_related("enrolment"), many=True
                ).data,
                "sections": sections,
            }
        )
