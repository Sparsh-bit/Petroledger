"""PetroLedger — Superadmin (Developer Portal) Dependency.

Grants cross-tenant access to the user whose email matches SUPERADMIN_EMAIL.
This is intentionally email-gated, not role-gated, so no DB migration is needed.
"""

from __future__ import annotations

from fastapi import Depends

from app.api.deps.auth import get_current_active_user
from app.core.config import get_settings
from app.core.exceptions import AuthorizationError
from app.models.user import User


async def get_superadmin(
    user: User = Depends(get_current_active_user),
) -> User:
    """Allow only the configured SUPERADMIN_EMAIL user through."""
    settings = get_settings()
    if user.email.lower() != settings.SUPERADMIN_EMAIL.lower():
        raise AuthorizationError(
            "This endpoint is restricted to the platform superadmin."
        )
    return user
