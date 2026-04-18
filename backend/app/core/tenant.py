"""PetroLedger — Tenant Isolation Helpers.

These functions enforce tenant-level data isolation across all queries.
Call tenant_scope() on every query that returns tenant-owned data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User


class TenantForbiddenError(AuthorizationError):
    """Raised when a user attempts a cross-tenant or over-limit action."""


# ── Query Scoping ───────────────────────────────────────────────────────────


def tenant_scope(query, model, current_user: User):
    """Apply tenant (and optionally org) isolation to a SQLAlchemy select().

    Rules:
    - Always filters by ``current_user.tenant_id`` (primary isolation boundary).
    - For org-scoped roles (manager, worker) the query is further narrowed to
      ``current_user.org_id`` when the model also carries an ``org_id`` column.

    Args:
        query:        A SQLAlchemy ``select()`` statement.
        model:        The ORM model class being queried (must have tenant_id).
        current_user: Authenticated ``User`` from the JWT dependency.

    Returns:
        The original query with WHERE clauses appended.

    Raises:
        ValueError:           If the model has no ``tenant_id`` column.
        TenantForbiddenError: If an org-scoped user has no org_id assigned.

    Example::

        query = select(Organization).where(Organization.is_active == True)
        query = tenant_scope(query, Organization, current_user)
        result = await db.execute(query)
    """
    if not hasattr(model, "tenant_id"):
        raise ValueError(f"Model {model.__name__} does not have a tenant_id column")

    # Primary tenant boundary — every user sees only their own tenant
    query = query.where(model.tenant_id == current_user.tenant_id)

    # Secondary org boundary for org-scoped roles
    # Handle both Enum (UserRole) and string roles
    org_scoped_roles = {"manager", "worker"}
    role_str = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    if role_str.lower() in org_scoped_roles:
        if current_user.org_id is None:
            raise TenantForbiddenError(
                f"Users with role '{role_str}' must be assigned to an "
                "organization before accessing this resource."
            )
        if hasattr(model, "org_id"):
            query = query.where(model.org_id == current_user.org_id)

    return query


# ── Subscription Limits ─────────────────────────────────────────────────────


async def get_tenant_org_count(tenant_id: UUID, db: AsyncSession) -> int:
    """Return the number of **active** organizations that belong to *tenant_id*.

    Deactivated / soft-deleted orgs don't count against the plan limit.
    """
    from app.models.organization import Organization

    result = await db.execute(
        select(func.count()).where(
            Organization.tenant_id == tenant_id,
            Organization.is_active == True,  # noqa: E712
            Organization.is_deleted == False,  # noqa: E712
        )
    )
    return result.scalar() or 0


async def check_org_limit(tenant: Tenant, db: AsyncSession) -> None:
    """Raise TenantForbiddenError if the tenant has reached its org limit.

    Call this *before* creating a new Organization.

    Raises:
        TenantForbiddenError: If ``current_count >= tenant.max_orgs``.
    """
    current_count = await get_tenant_org_count(tenant.id, db)
    if current_count >= tenant.max_orgs:
        raise TenantForbiddenError(
            f"Organization limit reached. "
            f"Plan: {tenant.subscription_plan}, "
            f"limit: {tenant.max_orgs}, "
            f"current: {current_count}. "
            "Upgrade your subscription to add more locations."
        )


# ── Cross-Tenant Access Guard ───────────────────────────────────────────────


def verify_tenant_match(resource_tenant_id: UUID, current_user: User) -> None:
    """Raise HTTP 404 if *resource_tenant_id* doesn't match the user's tenant.

    Returns 404 (not 403) to avoid revealing that the resource exists.

    Example::

        org = await db.get(Organization, org_id)
        if org is None:
            raise NotFoundError(...)
        verify_tenant_match(org.tenant_id, current_user)
    """
    if resource_tenant_id != current_user.tenant_id:
        raise NotFoundError("Resource not found")
