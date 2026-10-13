from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ValidationError
from django.http import HttpRequest

from identity.models import AuditEvent

AUDIT_ACTIONS = frozenset(
    {
        "identity.session.started",
        "identity.session.ended",
        "identity.session.rejected",
        "identity.mfa.setup.started",
        "identity.mfa.enabled",
        "identity.mfa.challenge.succeeded",
        "identity.mfa.challenge.rejected",
        "identity.recovery.requested",
        "identity.recovery.completed",
        "identity.maker_checker.evaluated",
        "institution.created",
        "institution.configuration.release.created",
        "institution.configuration.release.submitted",
        "institution.configuration.release.approved",
        "institution.configuration.record.created",
        "institution.configuration.record.updated",
        "institution.staff.membership.created",
        "institution.staff.membership.updated",
        "institution.enrolment.created",
        "institution.enrolment.updated",
    }
)
_SENSITIVE_METADATA_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "csrf",
        "csrf_token",
        "new_password",
        "otp",
        "password",
        "request_body",
        "secret",
        "session",
        "token",
    }
)


def _contains_sensitive_key(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).casefold() in _SENSITIVE_METADATA_KEYS
            or _contains_sensitive_key(nested)
            for key, nested in value.items()
        )
    if isinstance(value, list | tuple):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def record_audit_event(
    *,
    action: str,
    request: HttpRequest,
    actor: Any = None,
    subject_type: str = "",
    subject_id: str = "",
    metadata: dict[str, object] | None = None,
) -> AuditEvent:
    """Create an action-allow-listed event without secrets or request bodies."""

    if action not in AUDIT_ACTIONS:
        raise ValidationError("The audit action is not allow-listed.")
    safe_metadata = metadata or {}
    if _contains_sensitive_key(safe_metadata):
        raise ValidationError("Sensitive authentication data cannot be audited.")

    return AuditEvent.objects.create(
        action=action,
        actor=actor,
        subject_type=subject_type,
        subject_id=subject_id,
        request_id=getattr(request, "request_id", ""),
        metadata=safe_metadata,
    )
