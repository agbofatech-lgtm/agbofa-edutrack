import logging

from django.db import DatabaseError, connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class LivenessView(APIView):
    authentication_classes: tuple = ()
    permission_classes = (AllowAny,)

    def get(self, request) -> Response:
        """Process liveness only; it intentionally does not claim DB readiness."""
        return Response({"status": "ok", "checks": {"application": "ok"}})


class ReadinessView(APIView):
    authentication_classes: tuple = ()
    permission_classes = (AllowAny,)

    def get(self, request) -> Response:
        """Check PostgreSQL with a constant query and omit internal error details."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            logger.warning("database readiness check failed")
            return Response(
                {"status": "unavailable", "checks": {"database": "unavailable"}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"status": "ok", "checks": {"database": "available"}})
