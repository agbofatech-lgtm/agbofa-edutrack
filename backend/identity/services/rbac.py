from collections.abc import Iterable
from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework.permissions import BasePermission

from identity.models import GLOBAL_SCOPE_KEY, GLOBAL_SCOPE_TYPE, ScopeGrant


def _active_permission_grants(user: Any, permission_code: str) -> QuerySet[ScopeGrant]:
    now = timezone.now()
    return (
        ScopeGrant.objects.filter(
            user_id=user.pk,
            is_active=True,
            role__is_active=True,
            role__permissions__code=permission_code,
            valid_from__lte=now,
        )
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now))
        .distinct()
    )


def active_permission_codes(user: Any) -> tuple[str, ...]:
    """Return permission identifiers from effective grants for UI hinting only."""

    if not getattr(user, "is_authenticated", False) or not getattr(
        user, "is_active", False
    ):
        return ()
    now = timezone.now()
    grants = ScopeGrant.objects.filter(
        user_id=user.pk,
        is_active=True,
        role__is_active=True,
        valid_from__lte=now,
    ).filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now))
    return tuple(sorted(set(grants.values_list("role__permissions__code", flat=True))))


def active_role_labels(user: Any) -> tuple[str, ...]:
    """Return currently effective role labels for the signed-in user's shell."""

    if not getattr(user, "is_authenticated", False) or not getattr(
        user, "is_active", False
    ):
        return ()
    now = timezone.now()
    grants = ScopeGrant.objects.filter(
        user_id=user.pk,
        is_active=True,
        role__is_active=True,
        valid_from__lte=now,
    ).filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now))
    return tuple(sorted(set(grants.values_list("role__label", flat=True))))


def user_has_permission(
    user: Any,
    permission_code: str,
    *,
    scope_type: str | None = None,
    scope_key: str | None = None,
) -> bool:
    """Check an active role grant in an exact or explicit global scope.

    The scope must be derived by trusted view/service code. This function never
    interprets user-supplied query parameters as permission scope.
    """

    if not getattr(user, "is_authenticated", False) or not getattr(
        user, "is_active", False
    ):
        return False
    if (scope_type is None) != (scope_key is None):
        raise ValueError("scope_type and scope_key must be provided together")
    if not permission_code:
        return False

    grants = _active_permission_grants(user, permission_code)
    if scope_type is None:
        return grants.filter(
            scope_type=GLOBAL_SCOPE_TYPE,
            scope_key=GLOBAL_SCOPE_KEY,
        ).exists()

    return grants.filter(
        Q(scope_type=GLOBAL_SCOPE_TYPE, scope_key=GLOBAL_SCOPE_KEY)
        | Q(scope_type=scope_type, scope_key=scope_key)
    ).exists()


def authorized_scope_keys(
    user: Any,
    permission_code: str,
    scope_type: str,
) -> tuple[bool, frozenset[str]]:
    """Return whether global access exists and the exact allowed keys otherwise."""

    if not getattr(user, "is_authenticated", False) or not getattr(
        user, "is_active", False
    ):
        return False, frozenset()

    grants = _active_permission_grants(user, permission_code)
    if grants.filter(scope_type=GLOBAL_SCOPE_TYPE, scope_key=GLOBAL_SCOPE_KEY).exists():
        return True, frozenset()
    keys: Iterable[str] = grants.filter(scope_type=scope_type).values_list(
        "scope_key", flat=True
    )
    return False, frozenset(keys)


def scope_queryset(
    queryset: QuerySet[Any],
    user: Any,
    *,
    permission_code: str,
    scope_type: str,
    scope_field: str,
) -> QuerySet[Any]:
    """Apply server-derived grants to a queryset using a trusted model field name.

    Callers must choose ``scope_field`` in code, never from request parameters. A
    future record model must also validate that the chosen field represents the
    documented scope hierarchy.
    """

    has_global, allowed_keys = authorized_scope_keys(user, permission_code, scope_type)
    if has_global:
        return queryset
    if not allowed_keys:
        return queryset.none()
    return queryset.filter(**{f"{scope_field}__in": allowed_keys})


class HasRBACPermission(BasePermission):
    """DRF permission backed by server-side role, permission and scope grants."""

    message = "You do not have permission to access this resource."

    def has_permission(self, request: Any, view: Any) -> bool:
        permission_code = getattr(view, "required_permission", None)
        if not isinstance(permission_code, str) or not permission_code:
            return False

        scope_provider = getattr(view, "get_authorization_scope", None)
        scope = scope_provider(request) if callable(scope_provider) else None
        if scope is None:
            return user_has_permission(request.user, permission_code)
        if (
            not isinstance(scope, tuple)
            or len(scope) != 2
            or not all(isinstance(value, str) and value for value in scope)
        ):
            return False
        return user_has_permission(
            request.user,
            permission_code,
            scope_type=scope[0],
            scope_key=scope[1],
        )
