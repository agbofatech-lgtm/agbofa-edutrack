"""Policy-neutral maker-checker contract; no approval workflow is configured."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from identity.services.rbac import user_has_permission


@dataclass(frozen=True, slots=True)
class MakerCheckerContext:
    """Opaque resource and exact authorization scope supplied by a trusted service."""

    maker_id: str
    checker_id: str
    resource_type: str
    resource_id: str
    permission_code: str
    scope_type: str
    scope_key: str


class MakerCheckerPolicy(Protocol):
    """Owner-approved domain policy decides whether a qualified checker may act."""

    def may_check(self, context: MakerCheckerContext) -> bool: ...


def may_checker_approve(
    context: MakerCheckerContext,
    *,
    checker,
    policy: MakerCheckerPolicy | None,
) -> bool:
    """Fail closed without a policy, scoped grant, or distinct maker/checker."""

    values = (
        context.maker_id,
        context.checker_id,
        context.resource_type,
        context.resource_id,
        context.permission_code,
        context.scope_type,
        context.scope_key,
    )
    if not all(isinstance(value, str) and value for value in values):
        return False
    if str(checker.pk) != context.checker_id or context.maker_id == context.checker_id:
        return False
    if policy is None:
        return False
    if not user_has_permission(
        checker,
        context.permission_code,
        scope_type=context.scope_type,
        scope_key=context.scope_key,
    ):
        return False
    return policy.may_check(context) is True
