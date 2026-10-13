from __future__ import annotations

import base64
from dataclasses import dataclass, replace

import pytest
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import RequestFactory
from django.utils import timezone

from identity.models import (
    AccessPermission,
    AccessRole,
    AuditEvent,
    ScopeGrant,
    User,
)
from identity.services.approvals import (
    MakerCheckerContext,
    may_checker_approve,
)
from identity.services.audit import record_audit_event
from identity.services.mfa import (
    begin_mfa_enrollment,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_totp_code,
    generate_totp_secret,
    mfa_is_enabled,
    verify_mfa_code,
)
from identity.services.rbac import active_permission_codes, active_role_labels

pytestmark = pytest.mark.django_db
FIXTURE_PASSWORD = "local-only-fixture-password"  # pragma: allowlist secret


class TestPrivilegedMfa:
    def test_totp_matches_rfc6238_sha1_six_digit_vector(self) -> None:
        secret = base64.b32encode(b"12345678901234567890").decode("ascii").rstrip("=")
        assert generate_totp_code(secret, at=59) == "287082"

    def test_encryption_authenticates_user_binding_and_does_not_store_plaintext(
        self,
    ) -> None:
        user = User.objects.create_user(
            username="mfa-reviewer",
            password=FIXTURE_PASSWORD,
        )
        other = User.objects.create_user(
            username="mfa-other",
            password=FIXTURE_PASSWORD,
        )
        secret = generate_totp_secret()

        encrypted = encrypt_totp_secret(user, secret)
        assert secret.encode("ascii") not in encrypted
        assert decrypt_totp_secret(user, encrypted) == secret
        with pytest.raises(ImproperlyConfigured):
            decrypt_totp_secret(other, encrypted)

    def test_privileged_enrollment_requires_a_valid_one_time_code(self) -> None:
        user = User.objects.create_user(
            username="platform-admin",
            password=FIXTURE_PASSWORD,
            is_staff=True,
        )
        secret = begin_mfa_enrollment(user)

        assert not mfa_is_enabled(user)
        code = generate_totp_code(secret)
        assert verify_mfa_code(user, code, setup=True)
        assert mfa_is_enabled(user)
        assert not verify_mfa_code(user, code)
        assert AuditEvent.objects.filter(action="identity.mfa.enabled").count() == 0

    def test_non_privileged_account_cannot_enroll_a_privileged_factor(self) -> None:
        user = User.objects.create_user(username="teacher", password=FIXTURE_PASSWORD)
        with pytest.raises(PermissionError):
            begin_mfa_enrollment(user)

    def test_expired_pending_enrollment_is_rejected(self) -> None:
        from datetime import timedelta

        from identity.models import MfaCredential

        user = User.objects.create_user(
            username="platform-admin",
            password=FIXTURE_PASSWORD,
            is_superuser=True,
        )
        secret = begin_mfa_enrollment(user)
        credential = MfaCredential.objects.get(user=user)
        credential.setup_expires_at = timezone.now() - timedelta(seconds=1)
        credential.save(update_fields=["setup_expires_at"])

        assert not verify_mfa_code(user, generate_totp_code(secret), setup=True)


@dataclass
class _AllowChecker:
    def may_check(self, context: MakerCheckerContext) -> bool:
        return context.resource_type == "future-record"


class TestMakerCheckerContract:
    def test_contract_fails_closed_without_policy_or_distinct_scoped_checker(
        self,
    ) -> None:
        maker = User.objects.create_user(username="maker", password=FIXTURE_PASSWORD)
        checker = User.objects.create_user(
            username="checker", password=FIXTURE_PASSWORD
        )
        permission = AccessPermission.objects.create(code="future.record.review")
        role = AccessRole.objects.create(code="future-reviewer", label="Reviewer")
        role.permissions.add(permission)
        ScopeGrant.objects.create(
            user=checker,
            role=role,
            scope_type="future-record",
            scope_key="opaque-7",
        )
        context = MakerCheckerContext(
            maker_id=str(maker.pk),
            checker_id=str(checker.pk),
            resource_type="future-record",
            resource_id="opaque-7",
            permission_code=permission.code,
            scope_type="future-record",
            scope_key="opaque-7",
        )

        assert not may_checker_approve(context, checker=checker, policy=None)
        assert may_checker_approve(context, checker=checker, policy=_AllowChecker())
        same_actor = replace(context, checker_id=str(maker.pk))
        assert not may_checker_approve(
            same_actor, checker=maker, policy=_AllowChecker()
        )

    def test_active_roles_and_permissions_are_data_derived(self) -> None:
        user = User.objects.create_user(username="reviewer", password=FIXTURE_PASSWORD)
        permission = AccessPermission.objects.create(code="opaque.permission.read")
        role = AccessRole.objects.create(
            code="opaque-role", label="Owner-approved role"
        )
        role.permissions.add(permission)
        ScopeGrant.objects.create(
            user=user,
            role=role,
            scope_type="opaque-scope",
            scope_key="opaque-key",
        )

        assert active_permission_codes(user) == ("opaque.permission.read",)
        assert active_role_labels(user) == ("Owner-approved role",)


class TestAuditService:
    def test_service_allows_only_known_actions_and_rejects_sensitive_metadata(
        self,
    ) -> None:
        request = RequestFactory().get("/")
        event = record_audit_event(
            action="identity.session.started",
            request=request,
            metadata={"method": "session"},
        )
        assert event.request_id == ""

        with pytest.raises(ValidationError):
            record_audit_event(action="unapproved.action", request=request)
        with pytest.raises(ValidationError):
            record_audit_event(
                action="identity.session.started",
                request=request,
                metadata={
                    "nested": {"password": "not-stored"},  # pragma: allowlist secret
                },
            )
