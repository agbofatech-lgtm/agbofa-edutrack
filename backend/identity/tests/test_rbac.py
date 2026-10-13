from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from identity.models import AccessPermission, AccessRole, AuditEvent, ScopeGrant, User
from identity.services.rbac import (
    HasRBACPermission,
    scope_queryset,
    user_has_permission,
)

pytestmark = pytest.mark.django_db
LOGIN_VALUE = "local-rbac-fixture-75"


class TestServerSideRbac:
    def setup_method(self) -> None:
        self.user = User.objects.create_user(username="teacher", password=LOGIN_VALUE)
        self.permission = AccessPermission.objects.create(
            code="academic.assessment.read",
            description="Read an approved assessment record.",
        )
        self.role = AccessRole.objects.create(
            code="assessment-reviewer", label="Reviewer"
        )
        self.role.permissions.add(self.permission)

    def grant(self, scope_type: str, scope_key: str, **kwargs: object) -> ScopeGrant:
        return ScopeGrant.objects.create(
            user=self.user,
            role=self.role,
            scope_type=scope_type,
            scope_key=scope_key,
            **kwargs,
        )

    def test_denies_without_grant_and_does_not_bypass_for_superuser(self) -> None:
        assert not user_has_permission(self.user, self.permission.code)
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        assert not user_has_permission(self.user, self.permission.code)

    def test_scope_is_exact_and_an_explicit_global_grant_is_required_for_unscoped_access(
        self,
    ) -> None:
        self.grant("class", "b9-stream-a")

        assert user_has_permission(
            self.user,
            self.permission.code,
            scope_type="class",
            scope_key="b9-stream-a",
        )
        assert not user_has_permission(
            self.user,
            self.permission.code,
            scope_type="class",
            scope_key="b9-stream-b",
        )
        assert not user_has_permission(self.user, self.permission.code)

    def test_inactive_role_grant_and_expired_grant_are_denied(self) -> None:
        expired = timezone.now() - timedelta(days=1)
        self.grant(
            "class",
            "old-cohort",
            valid_from=expired - timedelta(days=1),
            valid_until=expired,
        )
        assert not user_has_permission(
            self.user,
            self.permission.code,
            scope_type="class",
            scope_key="old-cohort",
        )

        ScopeGrant.objects.filter(user=self.user).update(is_active=False)
        self.grant("class", "new-cohort")
        self.role.is_active = False
        self.role.save(update_fields=["is_active"])
        assert not user_has_permission(
            self.user,
            self.permission.code,
            scope_type="class",
            scope_key="new-cohort",
        )

    def test_expired_scope_grant_can_be_reissued_without_erasing_history(self) -> None:
        expired = timezone.now() - timedelta(days=1)
        self.grant(
            "class",
            "b9-stream-a",
            valid_from=expired - timedelta(days=30),
            valid_until=expired,
        )
        reissued = self.grant(
            "class",
            "b9-stream-a",
            valid_from=timezone.now(),
        )

        assert reissued.pk is not None
        assert (
            ScopeGrant.objects.filter(
                user=self.user,
                role=self.role,
                scope_type="class",
                scope_key="b9-stream-a",
            ).count()
            == 2
        )
        assert user_has_permission(
            self.user,
            self.permission.code,
            scope_type="class",
            scope_key="b9-stream-a",
        )

    def test_scope_must_be_supplied_as_a_pair(self) -> None:
        with pytest.raises(ValueError):
            user_has_permission(self.user, self.permission.code, scope_type="class")

    def test_rbac_permission_uses_view_scope_and_denies_missing_permission_contract(
        self,
    ) -> None:
        self.grant("class", "b9-stream-a")
        request = APIRequestFactory().get("/api/v1/private/")
        request.user = self.user
        checker = HasRBACPermission()
        allowed_view = SimpleNamespace(
            required_permission=self.permission.code,
            get_authorization_scope=lambda _request: ("class", "b9-stream-a"),
        )
        wrong_scope_view = SimpleNamespace(
            required_permission=self.permission.code,
            get_authorization_scope=lambda _request: ("class", "b9-stream-b"),
        )
        unconfigured_view = SimpleNamespace()

        assert checker.has_permission(request, allowed_view)
        assert not checker.has_permission(request, wrong_scope_view)
        assert not checker.has_permission(request, unconfigured_view)

    def test_scoped_queryset_fails_closed_without_a_matching_grant(self) -> None:
        self.grant("class", "b9-stream-a")
        queryset = ScopeGrant.objects.filter(user=self.user)
        permitted = scope_queryset(
            queryset,
            self.user,
            permission_code=self.permission.code,
            scope_type="class",
            scope_field="scope_key",
        )
        denied = scope_queryset(
            queryset,
            self.user,
            permission_code=self.permission.code,
            scope_type="learner",
            scope_field="scope_key",
        )

        assert list(permitted.values_list("scope_key", flat=True)) == ["b9-stream-a"]
        assert not denied.exists()

    def test_global_scope_cannot_be_partially_misrepresented(self) -> None:
        with pytest.raises(ValidationError):
            self.grant("global", "b9-stream-a")


class TestAppendOnlyAuditEvents:
    def test_audit_event_cannot_be_updated_or_deleted_through_ordinary_orm_paths(
        self,
    ) -> None:
        event = AuditEvent.objects.create(
            action="identity.test", metadata={"safe": True}
        )

        with pytest.raises(ValidationError):
            event.save()
        with pytest.raises(ValidationError):
            AuditEvent.objects.filter(pk=event.pk).update(action="tampered")
        with pytest.raises(ValidationError):
            event.delete()
        with pytest.raises(ValidationError):
            AuditEvent.objects.filter(pk=event.pk).delete()

        assert AuditEvent.objects.get(pk=event.pk).action == "identity.test"
