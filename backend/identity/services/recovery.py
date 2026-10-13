"""Disabled-by-default account recovery with single-use, hashed bearer tokens."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta
from typing import Protocol, cast

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from identity.models import AccountRecoveryToken, User
from identity.services.audit import record_audit_event

logger = logging.getLogger(__name__)


class RecoveryDeliveryBackend(Protocol):
    """Owner-configured adapter; it must implement approved identity proofing."""

    def deliver_recovery_token(self, user: User, token: str) -> None: ...


def _configured_delivery_backend() -> RecoveryDeliveryBackend | None:
    backend_path = getattr(settings, "IDENTITY_RECOVERY_DELIVERY_BACKEND", "")
    if not backend_path:
        return None
    backend_class = import_string(backend_path)
    backend = backend_class() if isinstance(backend_class, type) else backend_class
    if not callable(getattr(backend, "deliver_recovery_token", None)):
        raise ImproperlyConfigured(
            "The recovery delivery backend must implement deliver_recovery_token."
        )
    return cast(RecoveryDeliveryBackend, backend)


def _token_ttl_seconds() -> int:
    ttl = getattr(settings, "IDENTITY_RECOVERY_TOKEN_TTL_SECONDS", 0)
    if not isinstance(ttl, int) or ttl <= 0:
        raise ImproperlyConfigured(
            "An approved recovery token lifetime must be configured."
        )
    return ttl


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_account_recovery(
    identifier: str,
    *,
    request,
    delivery_backend: RecoveryDeliveryBackend | None = None,
) -> bool:
    """Create and deliver a token only when an explicit adapter is configured.

    The return value is internal only. The public endpoint always returns the same
    response for known/unknown accounts and disabled delivery.
    """

    record_audit_event(action="identity.recovery.requested", request=request)
    try:
        backend = delivery_backend or _configured_delivery_backend()
    except (ImportError, ImproperlyConfigured):
        logger.error("account recovery delivery is misconfigured")
        return False
    if backend is None:
        return False

    user = User.objects.filter(username=identifier, is_active=True).first()
    if user is None:
        return False

    try:
        ttl_seconds = _token_ttl_seconds()
    except ImproperlyConfigured:
        logger.error("account recovery lifetime is not configured")
        return False

    raw_token = secrets.token_urlsafe(32)
    challenge = AccountRecoveryToken.objects.create(
        user=user,
        token_digest=_token_digest(raw_token),
        expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
    )
    try:
        backend.deliver_recovery_token(user, raw_token)
    except Exception:  # A provider error must never disclose account state to caller.
        AccountRecoveryToken.objects.filter(pk=challenge.pk).update(
            revoked_at=timezone.now()
        )
        logger.warning("account recovery delivery failed")
        return False
    return True


def complete_account_recovery(
    token: str,
    new_password: str,
    *,
    request,
) -> bool:
    """Consume a valid token, update the password and revoke sibling challenges."""

    if not token or len(token) > 512:
        return False
    digest = _token_digest(token)
    now = timezone.now()
    try:
        with transaction.atomic():
            try:
                challenge = (
                    AccountRecoveryToken.objects.select_for_update()
                    .select_related("user")
                    .get(token_digest=digest)
                )
            except AccountRecoveryToken.DoesNotExist:
                return False

            if (
                challenge.consumed_at is not None
                or challenge.revoked_at is not None
                or challenge.expires_at <= now
                or not challenge.user.is_active
            ):
                return False

            try:
                validate_password(new_password, user=challenge.user)
            except ValidationError:
                return False

            challenge.user.set_password(new_password)
            challenge.user.save(update_fields=["password"])
            challenge.consumed_at = now
            challenge.save(update_fields=["consumed_at"])
            AccountRecoveryToken.objects.filter(
                user=challenge.user,
                consumed_at__isnull=True,
                revoked_at__isnull=True,
            ).exclude(pk=challenge.pk).update(revoked_at=now)
            record_audit_event(
                action="identity.recovery.completed",
                request=request,
                subject_type="identity.user",
                subject_id=str(challenge.user_id),
            )
    except (ImproperlyConfigured, DatabaseError):
        logger.error("account recovery could not be completed")
        return False
    return True
