from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from identity.models import User
from identity.services.audit import record_audit_event


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=False)
    password = serializers.CharField(
        max_length=4096,
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenView(APIView):
    authentication_classes: tuple = ()
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        return Response({"csrfToken": get_token(request._request)})


@method_decorator(csrf_protect, name="dispatch")
class SessionView(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (AllowAny,)

    @staticmethod
    def _session_payload(user: User) -> dict[str, object]:
        username = user.get_username()
        full_name = user.get_full_name()
        return {
            "authenticated": True,
            "user": {
                "id": user.pk,
                "username": username,
                "displayName": full_name or username,
            },
        }

    def get(self, request: Request) -> Response:
        if not request.user.is_authenticated:
            return Response({"authenticated": False})
        return Response(self._session_payload(request.user))

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credentials = serializer.validated_data
        user = authenticate(
            request=request._request,
            username=credentials["username"],
            password=credentials["password"],
        )
        if user is None:
            return Response(
                {"detail": "Unable to sign in with the supplied credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request._request, user)
        record_audit_event(
            action="identity.session.started",
            request=request._request,
            actor=user,
            subject_type="identity.user",
            subject_id=str(user.pk),
        )
        payload = self._session_payload(user)
        payload["csrfToken"] = get_token(request._request)
        return Response(payload, status=status.HTTP_200_OK)


class LogoutView(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        user = request.user
        record_audit_event(
            action="identity.session.ended",
            request=request._request,
            actor=user,
            subject_type="identity.user",
            subject_id=str(user.pk),
        )
        logout(request._request)
        return Response({"authenticated": False}, status=status.HTTP_200_OK)
