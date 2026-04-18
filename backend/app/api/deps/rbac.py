"""PetroLedger — Role-Based Access Control Dependency."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends

from app.api.deps.auth import get_current_active_user
from app.core.exceptions import AuthorizationError
from app.models.user import User, UserRole


def require_role(*roles: UserRole) -> Callable[..., Coroutine[Any, Any, User]]:
    """
    Dependency factory that restricts access to users whose role
    is in the given *roles*.

    Usage::

        @router.get("/admin-only")
        async def admin_view(
            user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
        ):
            ...
    """
    allowed = set(roles)

    async def _check_role(
        user: User = Depends(get_current_active_user),
    ) -> User:
        if user.role not in allowed:
            raise AuthorizationError(
                f"Role '{user.role.value}' is not permitted. "
                f"Required: {', '.join(r.value for r in allowed)}"
            )
        return user

    return _check_role
