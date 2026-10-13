from typing import Any

from django.http import HttpRequest

from identity.models import AuditEvent


def record_audit_event(
    *,
    action: str,
    request: HttpRequest,
    actor: Any = None,
    subject_type: str = "",
    subject_id: str = "",
    metadata: dict[str, object] | None = None,
) -> AuditEvent:
    """Create an allow-listed audit event; callers must not pass secrets or bodies."""

    return AuditEvent.objects.create(
        action=action,
        actor=actor,
        subject_type=subject_type,
        subject_id=subject_id,
        request_id=getattr(request, "request_id", ""),
        metadata=metadata or {},
    )
