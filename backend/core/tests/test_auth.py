import pytest
from rest_framework.test import APIClient

from identity.models import AuditEvent, User

pytestmark = pytest.mark.django_db
GOOD_LOGIN_VALUE = "local-valid-fixture-86"
BAD_LOGIN_VALUE = "local-invalid-fixture"


class TestSessionAuthentication:
    def setup_method(self) -> None:
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
        }
        assert response.json()["csrfToken"]
        assert AuditEvent.objects.filter(
            action="identity.session.started", actor=user
        ).exists()
        assert response.cookies["edutrack_sessionid"]["httponly"] is True
        assert self.client.get("/api/v1/auth/session/").json()["authenticated"] is True

    def test_bad_credentials_use_one_generic_response(self) -> None:
        csrf_token = self.csrf_token()
        response = self.client.post(
            "/api/v1/auth/session/",
            {"username": "not-a-real-user", "password": BAD_LOGIN_VALUE},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        assert response.status_code == 401
        assert response.json() == {
            "detail": "Unable to sign in with the supplied credentials."
        }

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
