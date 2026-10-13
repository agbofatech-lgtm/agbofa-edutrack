import logging

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from identity.models import User
from identity.services.audit import record_audit_event
from identity.services.mfa import (
    account_requires_mfa,
    begin_mfa_enrollment,
    get_pending_mfa_secret,
    mfa_is_enabled,
    privileged_account_requires_mfa,
    provisioning_uri,
    verify_mfa_code,
)
from identity.services.rbac import active_permission_codes, active_role_labels
from identity.services.recovery import (
    complete_account_recovery,
    request_account_recovery,
)

logger = logging.getLogger(__name__)
INVALID_CREDENTIALS_DETAIL = "Unable to sign in with the supplied credentials."
INVALID_MFA_DETAIL = "Unable to verify the supplied authentication code."
PENDING_USER_KEY = "identity.mfa.pending_user_id"
PENDING_MODE_KEY = "identity.mfa.pending_mode"
PENDING_TTL_SETTING = "IDENTITY_MFA_SETUP_TTL_SECONDS"


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=False)
    password = serializers.CharField(
        max_length=4096,
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )


class MfaCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32, trim_whitespace=False, write_only=True)


class RecoveryRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=False)


class RecoveryCompleteSerializer(serializers.Serializer):
    token = serializers.CharField(
        max_length=512, trim_whitespace=False, write_only=True
    )
    newPassword = serializers.CharField(
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


def _authenticated_payload(user: User, request) -> dict[str, object]:
    username = user.get_username()
    full_name = user.get_full_name()
    return {
        "authenticated": True,
        "user": {
            "id": user.pk,
            "username": username,
            "displayName": full_name or username,
            "isPrivileged": privileged_account_requires_mfa(user),
            "mfaEnabled": mfa_is_enabled(user),
            "roles": list(active_role_labels(user)),
            "permissions": list(active_permission_codes(user)),
        },
        "sessionExpiresAt": request.session.get_expiry_date().isoformat(),
    }


def _clear_pending_state(request) -> None:
    request.session.pop(PENDING_USER_KEY, None)
    request.session.pop(PENDING_MODE_KEY, None)


def _set_pending_state(request, user: User, mode: str) -> None:
    request.session.cycle_key()
    request.session[PENDING_USER_KEY] = str(user.pk)
    request.session[PENDING_MODE_KEY] = mode
    request.session.set_expiry(getattr(settings, PENDING_TTL_SETTING, 300))


def _pending_payload(request) -> dict[str, object] | None:
    raw_user_id = request.session.get(PENDING_USER_KEY)
    mode = request.session.get(PENDING_MODE_KEY)
    if raw_user_id is None or mode not in {"setup", "verify"}:
        return None
    try:
        user = User.objects.get(pk=raw_user_id, is_active=True)
    except (User.DoesNotExist, ValueError, TypeError):
        request.session.flush()
        return None

    if not account_requires_mfa(user):
        request.session.flush()
        return None
    pending_expiry = request.session.get_expiry_date().isoformat()
    if mode == "setup":
        secret = get_pending_mfa_secret(user)
        if secret is None:
            secret = begin_mfa_enrollment(user)
        return {
            "authenticated": False,
            "mfaRequired": True,
            "setupRequired": True,
            "setupSecret": secret,
            "provisioningUri": provisioning_uri(secret),
            "pendingExpiresAt": pending_expiry,
        }
    return {
        "authenticated": False,
        "mfaRequired": True,
        "setupRequired": False,
        "pendingExpiresAt": pending_expiry,
    }


def _finish_login(request, user: User) -> dict[str, object]:
    _clear_pending_state(request)
    # MFA uses a short-lived pre-authentication session; restore the configured
    # ordinary session lifetime before finalizing the authenticated session.
    request.session.set_expiry(None)
    login(request, user)
    record_audit_event(
        action="identity.session.started",
        request=request,
        actor=user,
        subject_type="identity.user",
        subject_id=str(user.pk),
    )
    return _authenticated_payload(user, request)


@method_decorator(csrf_protect, name="dispatch")
class SessionView(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (AllowAny,)
    throttle_scope = "identity_login"

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def get(self, request: Request) -> Response:
        if request.user.is_authenticated:
            return Response(_authenticated_payload(request.user, request._request))
        try:
            pending = _pending_payload(request._request)
        except (ImproperlyConfigured, DatabaseError):
            logger.error("MFA session state could not be loaded")
            return Response(
                {"detail": "Sign-in is temporarily unavailable. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(pending or {"authenticated": False})

    def post(self, request: Request) -> Response:
        if (
            request._request.user.is_authenticated
            or request._request.session.get(PENDING_USER_KEY) is not None
        ):
            request._request.session.flush()
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credentials = serializer.validated_data
        user = authenticate(
            request=request._request,
            username=credentials["username"],
            password=credentials["password"],
        )
        if user is None:
            record_audit_event(
                action="identity.session.rejected",
                request=request._request,
            )
            return Response(
                {"detail": INVALID_CREDENTIALS_DETAIL},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            if account_requires_mfa(user):
                if mfa_is_enabled(user):
                    mode = "verify"
                    payload: dict[str, object] = {
                        "authenticated": False,
                        "mfaRequired": True,
                        "setupRequired": False,
                    }
                else:
                    secret = begin_mfa_enrollment(user)
                    mode = "setup"
                    payload = {
                        "authenticated": False,
                        "mfaRequired": True,
                        "setupRequired": True,
                        "setupSecret": secret,
                        "provisioningUri": provisioning_uri(secret),
                    }
                    record_audit_event(
                        action="identity.mfa.setup.started",
                        request=request._request,
                        actor=user,
                        subject_type="identity.user",
                        subject_id=str(user.pk),
                    )
                _set_pending_state(request._request, user, mode)
                payload["pendingExpiresAt"] = (
                    request._request.session.get_expiry_date().isoformat()
                )
                payload["csrfToken"] = get_token(request._request)
                return Response(payload, status=status.HTTP_202_ACCEPTED)
        except (ImproperlyConfigured, DatabaseError):
            logger.error("privileged sign-in could not initialize MFA")
            request._request.session.flush()
            return Response(
                {"detail": "Sign-in is temporarily unavailable. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        request._request.session.set_expiry(None)
        login(request._request, user)
        record_audit_event(
            action="identity.session.started",
            request=request._request,
            actor=user,
            subject_type="identity.user",
            subject_id=str(user.pk),
        )
        payload = _authenticated_payload(user, request._request)
        payload["csrfToken"] = get_token(request._request)
        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_protect, name="dispatch")
class MfaChallengeView(APIView):
    authentication_classes: tuple = ()
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "identity_mfa"

    def post(self, request: Request) -> Response:
        serializer = MfaCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_user_id = request._request.session.get(PENDING_USER_KEY)
        mode = request._request.session.get(PENDING_MODE_KEY)
        if raw_user_id is None or mode not in {"setup", "verify"}:
            return Response(
                {"detail": INVALID_CREDENTIALS_DETAIL},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user = None
        try:
            user = User.objects.get(pk=raw_user_id, is_active=True)
            if not account_requires_mfa(user):
                request._request.session.flush()
                return Response(
                    {"detail": INVALID_CREDENTIALS_DETAIL},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            verified = verify_mfa_code(
                user,
                serializer.validated_data["code"],
                setup=(mode == "setup"),
            )
        except (User.DoesNotExist, ValueError, TypeError):
            verified = False
        except (ImproperlyConfigured, DatabaseError):
            logger.error("MFA verification could not be completed")
            return Response(
                {"detail": "Sign-in is temporarily unavailable. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not verified:
            record_audit_event(
                action="identity.mfa.challenge.rejected",
                request=request._request,
                actor=user,
                subject_type="identity.user" if user is not None else "",
                subject_id=str(user.pk) if user is not None else "",
            )
            return Response(
                {"detail": INVALID_MFA_DETAIL},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user is None:
            return Response(
                {"detail": INVALID_CREDENTIALS_DETAIL},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        record_audit_event(
            action=(
                "identity.mfa.enabled"
                if mode == "setup"
                else "identity.mfa.challenge.succeeded"
            ),
            request=request._request,
            actor=user,
            subject_type="identity.user",
            subject_id=str(user.pk),
        )
        payload = _finish_login(request._request, user)
        payload["csrfToken"] = get_token(request._request)
        return Response(payload, status=status.HTTP_200_OK)


@method_decorator(csrf_protect, name="dispatch")
class MfaCancelView(APIView):
    authentication_classes: tuple = ()
    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        request._request.session.flush()
        return Response({"authenticated": False})


@method_decorator(csrf_protect, name="dispatch")
class RecoveryRequestView(APIView):
    authentication_classes: tuple = ()
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "identity_recovery"

    def post(self, request: Request) -> Response:
        serializer = RecoveryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_account_recovery(
            serializer.validated_data["username"],
            request=request._request,
        )
        return Response(
            {
                "detail": (
                    "If an approved recovery method is available, use its instructions. "
                    "This foundation does not send email or SMS."
                )
            },
            status=status.HTTP_202_ACCEPTED,
        )


@method_decorator(csrf_protect, name="dispatch")
class RecoveryCompleteView(APIView):
    authentication_classes: tuple = ()
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "identity_recovery"

    def post(self, request: Request) -> Response:
        serializer = RecoveryCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        complete_account_recovery(
            serializer.validated_data["token"],
            serializer.validated_data["newPassword"],
            request=request._request,
        )
        return Response(
            {
                "detail": (
                    "If the recovery token is valid and the password meets the "
                    "security requirements, the password has been updated."
                )
            }
        )


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
