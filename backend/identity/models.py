from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

GLOBAL_SCOPE_TYPE = "global"
GLOBAL_SCOPE_KEY = "global"


class User(AbstractUser):
    """Custom user model selected before domain records or migrations exist."""

    class Meta:
        db_table = "identity_user"


class AccessPermission(models.Model):
    """A stable, server-enforced permission identifier; no school policy is seeded."""

    code = models.CharField(max_length=120, unique=True)
    description = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "identity_permission"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class AccessRole(models.Model):
    """A school-managed role label and its explicitly approved permissions."""

    code = models.SlugField(max_length=64, unique=True)
    label = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    permissions: models.ManyToManyField[AccessPermission, AccessPermission] = (
        models.ManyToManyField(
            AccessPermission,
            through="RolePermission",
            related_name="roles",
        )
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "identity_role"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.label


class RolePermission(models.Model):
    role = models.ForeignKey(
        AccessRole,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    permission = models.ForeignKey(
        AccessPermission,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    granted_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "identity_role_permission"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="identity_role_permission_unique",
            )
        ]


class ScopeGrant(models.Model):
    """An effective-dated role grant for one exact, opaque server-side scope."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="scope_grants",
    )
    role = models.ForeignKey(
        AccessRole,
        on_delete=models.PROTECT,
        related_name="scope_grants",
    )
    scope_type = models.CharField(max_length=64)
    scope_key = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="issued_scope_grants",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "identity_scope_grant"
        indexes = [
            models.Index(
                fields=["user", "scope_type", "scope_key", "is_active"],
                name="identity_grant_scope_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "scope_type", "scope_key", "valid_from"],
                name="identity_grant_version_unique",
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True)
                | Q(valid_until__gt=F("valid_from")),
                name="identity_grant_valid_period",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if (self.scope_type == GLOBAL_SCOPE_TYPE) != (
            self.scope_key == GLOBAL_SCOPE_KEY
        ):
            raise ValidationError(
                "Global grants must use the canonical global scope type and key."
            )
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValidationError("Grant expiry must be later than its start time.")

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class ImmutableAuditQuerySet(models.QuerySet):
    """Refuse ordinary ORM mutation paths for append-only audit evidence."""

    def update(self, **kwargs: object) -> int:
        raise ValidationError("Audit events are append-only and cannot be updated.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("Audit events are append-only and cannot be deleted.")


class AuditEvent(models.Model):
    """Minimal append-only audit record. Never store passwords or request bodies."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    action = models.CharField(max_length=120)
    subject_type = models.CharField(max_length=120, blank=True)
    subject_id = models.CharField(max_length=128, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(
        default=timezone.now, editable=False, db_index=True
    )

    objects = ImmutableAuditQuerySet.as_manager()

    class Meta:
        db_table = "identity_audit_event"
        ordering = ["occurred_at", "id"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ValidationError("Audit events are append-only and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("Audit events are append-only and cannot be deleted.")
