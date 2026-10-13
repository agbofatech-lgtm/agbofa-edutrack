from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import Client, RequestFactory
from django.utils import timezone

from identity.models import AccountRecoveryToken, AuditEvent, User
from identity.services.recovery import (
    complete_account_recovery,
    request_account_recovery,
)

pytestmark = pytest.mark.django_db
OLD_PASSWORD = "fixture-old-password-value"  # pragma: allowlist secret
NEW_PASSWORD = "fixture-new-recovery-password-672!"  # pragma: allowlist secret
NEXT_PASSWORD = "fixture-next-recovery-password-973!"  # pragma: allowlist secret


class CapturingRecoveryBackend:
    def __init__(self) -> None:
        self.tokens: list[tuple[str, str]] = []

    def deliver_recovery_token(self, user: User, token: str) -> None:
        self.tokens.append((user.username, token))


class TestAccountRecovery:
    def setup_method(self) -> None:
        self.request = RequestFactory().post("/api/v1/auth/recovery/request/")
        self.user = User.objects.create_user(
            username="recovery-user",
            password=OLD_PASSWORD,
        )
        self.backend = CapturingRecoveryBackend()

    def test_token_is_only_delivered_through_explicit_backend_and_consumed_once(
        self,
    ) -> None:
        issued = request_account_recovery(
            self.user.username,
            request=self.request,
            delivery_backend=self.backend,
        )
        assert issued
        username, token = self.backend.tokens[0]
        challenge = AccountRecoveryToken.objects.get(user=self.user)

        assert username == self.user.username
        assert token not in challenge.token_digest
        assert len(challenge.token_digest) == 64
        assert AuditEvent.objects.filter(action="identity.recovery.requested").exists()

        new_password = NEW_PASSWORD
        assert not complete_account_recovery(
            token,
            "weak",
            request=self.request,
        )
        assert complete_account_recovery(
            token,
            new_password,
            request=self.request,
        )
        self.user.refresh_from_db()
        challenge.refresh_from_db()
        assert self.user.check_password(new_password)
        assert challenge.consumed_at is not None
        assert not complete_account_recovery(
            token,
            NEXT_PASSWORD,
            request=self.request,
        )
        assert AuditEvent.objects.filter(
            action="identity.recovery.completed",
            subject_id=str(self.user.pk),
        ).exists()

    def test_unknown_user_does_not_create_or_deliver_a_token(self) -> None:
        issued = request_account_recovery(
            "not-a-real-account",
            request=self.request,
            delivery_backend=self.backend,
        )

        assert not issued
        assert self.backend.tokens == []
        assert not AccountRecoveryToken.objects.exists()
        assert AuditEvent.objects.filter(
            action="identity.recovery.requested", subject_id=""
        ).exists()

    def test_expired_token_is_rejected_and_never_changes_the_password(self) -> None:
        assert request_account_recovery(
            self.user.username,
            request=self.request,
            delivery_backend=self.backend,
        )
        token = self.backend.tokens[0][1]
        challenge = AccountRecoveryToken.objects.get(user=self.user)
        expired_at = timezone.now() - timedelta(seconds=1)
        challenge.created_at = expired_at - timedelta(seconds=30)
        challenge.expires_at = expired_at
        challenge.save(update_fields=["created_at", "expires_at"])

        assert not complete_account_recovery(
            token,
            NEW_PASSWORD,
            request=self.request,
        )
        self.user.refresh_from_db()
        assert self.user.check_password(OLD_PASSWORD)

    def test_password_recovery_invalidates_existing_django_sessions(self) -> None:
        client = Client()
        client.force_login(self.user)
        assert client.get("/api/v1/auth/session/").json()["authenticated"] is True
        assert request_account_recovery(
            self.user.username,
            request=self.request,
            delivery_backend=self.backend,
        )
        token = self.backend.tokens[0][1]

        assert complete_account_recovery(
            token,
            NEW_PASSWORD,
            request=self.request,
        )
        assert client.get("/api/v1/auth/session/").json() == {"authenticated": False}
