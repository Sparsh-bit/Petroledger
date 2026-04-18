"""PetroLedger — Tenant FastAPI Dependency."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.core.tenant import TenantForbiddenError
from app.db.session import get_db
from app.models.tenant import Tenant
from app.models.user import User


async def get_current_tenant(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Resolve the authenticated user's Tenant and verify it is active.

    Use this dependency in routes that need the full Tenant object
    (e.g. checking subscription plan, enforcing org limits).

    Example::

        @router.get("/tenants/me")
        async def get_my_tenant(
            tenant: Tenant = Depends(get_current_tenant),
        ):
            return {"name": tenant.name, "plan": tenant.subscription_plan}

    Raises:
        TenantForbiddenError: If the tenant record is missing or inactive.
    """
    tenant = await db.get(Tenant, current_user.tenant_id)

    if tenant is None:
        raise TenantForbiddenError("Tenant record not found — contact support")

    if not tenant.is_active:
        raise TenantForbiddenError(
            "Your account has been deactivated — contact support"
        )

    return tenant
