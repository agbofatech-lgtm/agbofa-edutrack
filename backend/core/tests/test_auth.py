from datetime import datetime

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from identity.models import AccountRecoveryToken, AuditEvent, User
from identity.services.mfa import (
    begin_mfa_enrollment,
    generate_totp_code,
    verify_mfa_code,
)

pytestmark = pytest.mark.django_db
GOOD_LOGIN_VALUE = "local-valid-fixture-86"
BAD_LOGIN_VALUE = "local-invalid-fixture"


class TestSessionAuthentication:
    def setup_method(self) -> None:
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf_token(self) -> str:
        response = self.client.get("/api/v1/auth/csrf/")
        assert response.status_code == 200
        token = response.json().get("csrfToken")
        assert isinstance(token, str)
        return token

    def test_csrf_cookie_is_httponly_lax_and_secure(self) -> None:
        response = self.client.get("/api/v1/auth/csrf/")
        cookie = response.cookies["edutrack_csrftoken"]

        assert cookie["httponly"] is True
        assert cookie["samesite"] == "Lax"
        assert cookie["secure"] is True

    def test_anonymous_session_does_not_disclose_account_details(self) -> None:
        response = self.client.get("/api/v1/auth/session/")

        assert response.status_code == 200
        assert response.json() == {"authenticated": False}

    def test_login_requires_csrf_then_issues_a_session_and_audit_event(self) -> None:
        user = User.objects.create_user(username="reviewer", password=GOOD_LOGIN_VALUE)
        csrf_token = self.csrf_token()

        rejected = self.client.post(
            "/api/v1/auth/session/",
            {"username": "reviewer", "password": GOOD_LOGIN_VALUE},
            format="json",
        )
        assert rejected.status_code == 403

        response = self.client.post(
            "/api/v1/auth/session/",
            {"username": "reviewer", "password": GOOD_LOGIN_VALUE},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        assert response.status_code == 200
        assert response.json()["authenticated"] is True
        assert response.json()["user"] == {
            "id": user.pk,
            "username": "reviewer",
            "displayName": "reviewer",
            "isPrivileged": False,
            "mfaEnabled": False,
            "roles": [],
            "permissions": [],
        }
        assert (
            datetime.fromisoformat(response.json()["sessionExpiresAt"]) > timezone.now()
        )
        assert response.json()["csrfToken"]
        assert response["Cache-Control"].startswith("private, no-store")
        assert AuditEvent.objects.filter(
            action="identity.session.started", actor=user
        ).exists()
        assert response.cookies["edutrack_sessionid"]["httponly"] is True
        assert self.client.get("/api/v1/auth/session/").json()["authenticated"] is True

    def test_bad_credentials_use_one_generic_response_for_known_and_unknown_users(
        self,
    ) -> None:
        User.objects.create_user(username="known-reviewer", password=GOOD_LOGIN_VALUE)
        csrf_token = self.csrf_token()
        known = self.client.post(
            "/api/v1/auth/session/",
            {"username": "known-reviewer", "password": BAD_LOGIN_VALUE},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        unknown = self.client.post(
            "/api/v1/auth/session/",
            {"username": "not-a-real-user", "password": BAD_LOGIN_VALUE},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        assert known.status_code == unknown.status_code == 401
        assert (
            known.json()
            == unknown.json()
            == {"detail": "Unable to sign in with the supplied credentials."}
        )
        assert (
            AuditEvent.objects.filter(action="identity.session.rejected").count() == 2
        )

    def test_authenticated_logout_requires_csrf_and_invalidates_session(self) -> None:
        user = User.objects.create_user(username="reviewer", password=GOOD_LOGIN_VALUE)
        csrf_token = self.csrf_token()
        login_response = self.client.post(
            "/api/v1/auth/session/",
            {"username": "reviewer", "password": GOOD_LOGIN_VALUE},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        assert login_response.status_code == 200
        fresh_token = login_response.json()["csrfToken"]

        denied = self.client.post("/api/v1/auth/logout/", {}, format="json")
        assert denied.status_code == 403

        response = self.client.post(
            "/api/v1/auth/logout/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=fresh_token,
        )
        assert response.status_code == 200
        assert response.json() == {"authenticated": False}
        assert AuditEvent.objects.filter(
            action="identity.session.ended", actor=user
        ).exists()
        assert self.client.get("/api/v1/auth/session/").json() == {
            "authenticated": False
        }

    def test_privileged_login_requires_setup_and_valid_mfa_before_authentication(
        self,
    ) -> None:
        user = User.objects.create_user(
            username="platform-admin",
            password=GOOD_LOGIN_VALUE,
            is_staff=True,
        )
        csrf_token = self.csrf_token()
        response = self.client.post(
            "/api/v1/auth/session/",
            {"username": user.username, "password": GOOD_LOGIN_VALUE},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        assert response.status_code == 202
        assert response.json()["authenticated"] is False
        assert response.json()["mfaRequired"] is True
        assert response.json()["setupRequired"] is True
        secret = response.json()["setupSecret"]
        assert response.json()["provisioningUri"].startswith("otpauth://totp/")
        assert response["Cache-Control"].startswith("private, no-store")

        pending = self.client.get("/api/v1/auth/session/").json()
        assert pending["setupSecret"] == secret

        rejected = self.client.post(
            "/api/v1/auth/mfa/verify/",
            {"code": "invalid"},
            format="json",
            HTTP_X_CSRFTOKEN=response.json()["csrfToken"],
        )
        assert rejected.status_code == 400
        assert rejected.json() == {
            "detail": "Unable to verify the supplied authentication code."
        }

        verified = self.client.post(
            "/api/v1/auth/mfa/verify/",
            {"code": generate_totp_code(secret)},
            format="json",
            HTTP_X_CSRFTOKEN=response.json()["csrfToken"],
        )
        assert verified.status_code == 200
        assert verified.json()["authenticated"] is True
        assert verified.json()["user"]["mfaEnabled"] is True
        assert verified.json()["user"]["isPrivileged"] is True
        assert AuditEvent.objects.filter(
            action="identity.mfa.enabled", actor=user
        ).exists()
        assert self.client.get("/api/v1/auth/session/").json()["authenticated"] is True

    def test_enabled_privileged_mfa_is_required_and_totp_replay_is_rejected(
        self,
    ) -> None:
        user = User.objects.create_user(
            username="platform-admin",
            password=GOOD_LOGIN_VALUE,
            is_superuser=True,
        )
        secret = begin_mfa_enrollment(user)
        assert verify_mfa_code(user, generate_totp_code(secret), setup=True)
        csrf_token = self.csrf_token()

        pending = self.client.post(
            "/api/v1/auth/session/",
            {"username": user.username, "password": GOOD_LOGIN_VALUE},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        assert pending.status_code == 202
        assert pending.json()["setupRequired"] is False
        future_step = int(timezone.now().timestamp() // 30 + 1) * 30
        code = generate_totp_code(secret, at=future_step)
        verified = self.client.post(
            "/api/v1/auth/mfa/verify/",
            {"code": code},
            format="json",
            HTTP_X_CSRFTOKEN=pending.json()["csrfToken"],
        )
        assert verified.status_code == 200

        replay = self.client.post(
            "/api/v1/auth/mfa/verify/",
            {"code": code},
            format="json",
            HTTP_X_CSRFTOKEN=verified.json()["csrfToken"],
        )
        assert replay.status_code == 401
        assert replay.json() == {
            "detail": "Unable to sign in with the supplied credentials."
        }

    def test_recovery_api_is_generic_and_no_unapproved_delivery_is_configured(
        self,
    ) -> None:
        User.objects.create_user(username="known-account", password=GOOD_LOGIN_VALUE)
        csrf_token = self.csrf_token()
        existing = self.client.post(
            "/api/v1/auth/recovery/request/",
            {"username": "known-account"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        unknown = self.client.post(
            "/api/v1/auth/recovery/request/",
            {"username": "unknown-account"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        assert existing.status_code == unknown.status_code == 202
        assert existing.json() == unknown.json()
        assert "does not send email or SMS" in existing.json()["detail"]
        assert not AccountRecoveryToken.objects.exists()

    def test_recovery_request_requires_csrf(self) -> None:
        response = self.client.post(
            "/api/v1/auth/recovery/request/",
            {"username": "unknown-account"},
            format="json",
        )
        assert response.status_code == 403

    def test_login_attempts_are_throttled_without_changing_generic_failures(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            ScopedRateThrottle,
            "THROTTLE_RATES",
            {**ScopedRateThrottle.THROTTLE_RATES, "identity_login": "1/min"},
        )
        csrf_token = self.csrf_token()
        first = self.client.post(
            "/api/v1/auth/session/",
            {"username": "unknown", "password": BAD_LOGIN_VALUE},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        second = self.client.post(
            "/api/v1/auth/session/",
            {"username": "unknown", "password": BAD_LOGIN_VALUE},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        assert first.status_code == 401
        assert first.json() == {
            "detail": "Unable to sign in with the supplied credentials."
        }
        assert second.status_code == 429
