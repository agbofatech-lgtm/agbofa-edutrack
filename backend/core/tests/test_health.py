from unittest.mock import patch
from uuid import UUID

import pytest
from django.db import OperationalError
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestHealthEndpoints:
    def setup_method(self) -> None:
        self.client = APIClient()

    def test_liveness_is_public_and_does_not_claim_database_health(self) -> None:
        response = self.client.get("/api/v1/health/live/")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "checks": {"application": "ok"}}

    def test_readiness_checks_the_database(self) -> None:
        response = self.client.get("/api/v1/health/ready/")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "checks": {"database": "available"}}

    def test_readiness_returns_generic_unavailable_when_database_check_fails(
        self,
    ) -> None:
        with patch(
            "core.api.v1.health.connection.cursor", side_effect=OperationalError
        ):
            response = self.client.get("/api/v1/health/ready/")

        assert response.status_code == 503
        assert response.json() == {
            "status": "unavailable",
            "checks": {"database": "unavailable"},
        }
        assert "OperationalError" not in response.content.decode()

    def test_request_id_is_generated_instead_of_trusting_a_client_header(self) -> None:
        response = self.client.get(
            "/api/v1/health/live/",
            HTTP_X_REQUEST_ID="client-controlled-value",
        )

        request_id = response["X-Request-ID"]
        assert request_id != "client-controlled-value"
        assert UUID(request_id).hex == request_id
