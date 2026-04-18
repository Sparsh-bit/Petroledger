"""PetroLedger — Provider Portal Routes (SUPERADMIN only).

Management surface for the platform operator (the company running
PetroLedger). Lists tenants, lock/unlock, adjust subscriptions, KPIs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.core.tenant_lock_cache import invalidate_tenant_lock
from app.db.session import get_db
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.tenant import Tenant
from app.models.user import User, UserRole

router = APIRouter()


# ── Guard ───────────────────────────────────────────────────────────────


def require_superadmin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role not in (UserRole.SUPERADMIN, UserRole.PROVIDER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provider portal requires SUPERADMIN privileges.",
        )
    return current_user


# ── Schemas ─────────────────────────────────────────────────────────────


class OrganizationSummary(BaseModel):
    tenant_id: str
    name: str
    owner_email: str
    owner_phone: str
    subscription_plan: str
    subscription_status: str
    subscription_expires_at: datetime | None
    monthly_price_inr: int
    is_active: bool
    is_locked: bool
    user_count: int
    pump_count: int
    org_count: int
    created_at: datetime


class SubscriptionUpdate(BaseModel):
    plan: str | None = None
    status: str | None = None
    expires_at: datetime | None = None
    monthly_price_inr: int | None = None


class ProviderStats(BaseModel):
    total_orgs: int
    active_orgs: int
    locked_orgs: int
    mrr_inr: int


class MessageResponse(BaseModel):
    message: str


class SubscriptionGroup(BaseModel):
    status: str
    count: int
    mrr_inr: int
    organizations: list[OrganizationSummary]


class SubscriptionsResponse(BaseModel):
    groups: list[SubscriptionGroup]
    total_mrr_inr: int


# ── Helpers ─────────────────────────────────────────────────────────────


async def _summarize_tenant(db: AsyncSession, tenant: Tenant) -> OrganizationSummary:
    user_count = (
        await db.execute(
            select(func.count(User.id)).where(User.tenant_id == tenant.id)
        )
    ).scalar_one()
    org_count = (
        await db.execute(
            select(func.count(Organization.id)).where(Organization.tenant_id == tenant.id)
        )
    ).scalar_one()
    pump_count = (
        await db.execute(
            select(func.count(Pump.id))
            .join(Organization, Organization.id == Pump.org_id)
            .where(Organization.tenant_id == tenant.id)
        )
    ).scalar_one()
    return OrganizationSummary(
        tenant_id=str(tenant.id),
        name=tenant.name,
        owner_email=tenant.owner_email,
        owner_phone=tenant.owner_phone,
        subscription_plan=tenant.subscription_plan,
        subscription_status=tenant.subscription_status,
        subscription_expires_at=tenant.subscription_expires_at,
        monthly_price_inr=tenant.monthly_price_inr,
        is_active=tenant.is_active,
        is_locked=tenant.is_locked,
        user_count=user_count or 0,
        pump_count=pump_count or 0,
        org_count=org_count or 0,
        created_at=tenant.created_at,
    )


# ── Routes ──────────────────────────────────────────────────────────────


@router.get("/organizations", response_model=list[OrganizationSummary])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> list[OrganizationSummary]:
    """List all tenants with summary subscription + usage info."""
    rows = (await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))).scalars().all()
    return [await _summarize_tenant(db, t) for t in rows]


@router.get("/organizations/{tenant_id}")
async def get_organization(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> dict[str, Any]:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    summary = await _summarize_tenant(db, tenant)
    users = (
        await db.execute(
            select(User).where(User.tenant_id == tenant.id).order_by(User.created_at.desc())
        )
    ).scalars().all()
    pumps = (
        await db.execute(
            select(Pump)
            .join(Organization, Organization.id == Pump.org_id)
            .where(Organization.tenant_id == tenant.id)
        )
    ).scalars().all()
    return {
        "summary": summary.model_dump(),
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "role": u.role.value,
                "is_active": u.is_active,
                "last_login": u.last_login,
            }
            for u in users
        ],
        "pumps": [
            {
                "id": str(p.id),
                "name": p.name,
                "code": p.code,
                "is_active": p.is_active,
            }
            for p in pumps
        ],
    }


@router.post("/organizations/{tenant_id}/lock", response_model=MessageResponse)
async def lock_organization(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> MessageResponse:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.is_locked = True
    await db.commit()
    await invalidate_tenant_lock(str(tenant.id))
    return MessageResponse(message=f"Tenant {tenant.name} locked.")


@router.post("/organizations/{tenant_id}/unlock", response_model=MessageResponse)
async def unlock_organization(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> MessageResponse:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.is_locked = False
    await db.commit()
    await invalidate_tenant_lock(str(tenant.id))
    return MessageResponse(message=f"Tenant {tenant.name} unlocked.")


@router.patch("/organizations/{tenant_id}/subscription", response_model=OrganizationSummary)
async def update_subscription(
    tenant_id: uuid.UUID,
    payload: SubscriptionUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> OrganizationSummary:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if payload.plan is not None:
        tenant.subscription_plan = payload.plan
    if payload.status is not None:
        tenant.subscription_status = payload.status
    if payload.expires_at is not None:
        tenant.subscription_expires_at = payload.expires_at
    if payload.monthly_price_inr is not None:
        tenant.monthly_price_inr = payload.monthly_price_inr
    await db.commit()
    await db.refresh(tenant)
    return await _summarize_tenant(db, tenant)


@router.get("/subscriptions", response_model=SubscriptionsResponse)
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> SubscriptionsResponse:
    """All tenants grouped by subscription_status, with per-group MRR rollup."""
    tenants = (
        await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    ).scalars().all()

    summaries = [await _summarize_tenant(db, t) for t in tenants]

    buckets: dict[str, list[OrganizationSummary]] = {
        "ACTIVE": [],
        "TRIAL": [],
        "EXPIRED": [],
        "CANCELLED": [],
    }
    for s in summaries:
        key = (s.subscription_status or "").upper() or "ACTIVE"
        buckets.setdefault(key, []).append(s)

    order = ["ACTIVE", "TRIAL", "EXPIRED", "CANCELLED"]
    groups: list[SubscriptionGroup] = []
    for status_key in order + [k for k in buckets if k not in order]:
        if status_key not in buckets:
            continue
        orgs = buckets[status_key]
        mrr = sum(o.monthly_price_inr for o in orgs)
        groups.append(
            SubscriptionGroup(
                status=status_key,
                count=len(orgs),
                mrr_inr=mrr,
                organizations=orgs,
            )
        )

    total_mrr = sum(g.mrr_inr for g in groups if g.status == "ACTIVE")
    return SubscriptionsResponse(groups=groups, total_mrr_inr=total_mrr)


@router.get("/stats", response_model=ProviderStats)
async def provider_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> ProviderStats:
    total = (await db.execute(select(func.count(Tenant.id)))).scalar_one() or 0
    active = (
        await db.execute(
            select(func.count(Tenant.id)).where(
                Tenant.is_active.is_(True), Tenant.is_locked.is_(False)
            )
        )
    ).scalar_one() or 0
    locked = (
        await db.execute(select(func.count(Tenant.id)).where(Tenant.is_locked.is_(True)))
    ).scalar_one() or 0
    mrr = (
        await db.execute(
            select(func.coalesce(func.sum(Tenant.monthly_price_inr), 0)).where(
                Tenant.is_active.is_(True),
                Tenant.is_locked.is_(False),
                Tenant.subscription_status == "active",
            )
        )
    ).scalar_one() or 0
    return ProviderStats(
        total_orgs=int(total),
        active_orgs=int(active),
        locked_orgs=int(locked),
        mrr_inr=int(mrr),
    )
