from django.urls import path

from institutional.api.v1.views import (
    ConfigurationReleaseActionView,
    ConfigurationReleaseCollectionView,
    ConfigurationResourceView,
    ConfigurationSchemaView,
    EnrolmentView,
    InstitutionCollectionView,
    InstitutionDetailView,
    InstitutionStaffMembershipView,
)

app_name = "institutional_v1"

urlpatterns = [
    path("institutions/", InstitutionCollectionView.as_view(), name="institution-list"),
    path(
        "institutions/<uuid:institution_id>/",
        InstitutionDetailView.as_view(),
        name="institution-detail",
    ),
    path(
        "institutions/<uuid:institution_id>/configuration/schema/",
        ConfigurationSchemaView.as_view(),
        name="configuration-schema",
    ),
    path(
        "institutions/<uuid:institution_id>/configuration/releases/",
        ConfigurationReleaseCollectionView.as_view(),
        name="configuration-releases",
    ),
    path(
        "institutions/<uuid:institution_id>/configuration/releases/<uuid:release_id>/actions/<str:action>/",
        ConfigurationReleaseActionView.as_view(),
        name="configuration-release-action",
    ),
    path(
        "institutions/<uuid:institution_id>/configuration/releases/<uuid:release_id>/resources/<slug:resource>/",
        ConfigurationResourceView.as_view(),
        name="configuration-resource-list",
    ),
    path(
        "institutions/<uuid:institution_id>/configuration/releases/<uuid:release_id>/resources/<slug:resource>/<uuid:record_id>/",
        ConfigurationResourceView.as_view(),
        name="configuration-resource-detail",
    ),
    path(
        "institutions/<uuid:institution_id>/staff-memberships/",
        InstitutionStaffMembershipView.as_view(),
        name="staff-membership-list",
    ),
    path(
        "institutions/<uuid:institution_id>/staff-memberships/<uuid:membership_id>/",
        InstitutionStaffMembershipView.as_view(),
        name="staff-membership-detail",
    ),
    path(
        "institutions/<uuid:institution_id>/configuration/releases/<uuid:release_id>/enrolments/",
        EnrolmentView.as_view(),
        name="enrolment-list",
    ),
    path(
        "institutions/<uuid:institution_id>/configuration/releases/<uuid:release_id>/enrolments/<uuid:enrolment_id>/",
        EnrolmentView.as_view(),
        name="enrolment-detail",
    ),
]
