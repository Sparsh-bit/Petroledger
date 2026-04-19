"""PetroLedger — Provider Portal Routes (SUPERADMIN only).

Management surface for the platform operator (the company running
PetroLedger). Lists tenants, lock/unlock, adjust subscriptions, KPIs.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.core.security import hash_password
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


class TenantCreateRequest(BaseModel):
    """Payload for creating a new tenant + owner + first pump in one call."""

    tenant_name: str = Field(..., min_length=2, max_length=255)
    owner_name: str = Field(..., min_length=2, max_length=255)
    owner_email: EmailStr
    owner_phone: str = Field(..., min_length=6, max_length=20)
    password: str = Field(..., min_length=8, max_length=64)
    pump_code: str = Field(..., min_length=3, max_length=32)
    org_name: str | None = Field(default=None, max_length=255)
    pump_name: str | None = Field(default=None, max_length=255)
    subscription_plan: str = Field(default="BASIC")
    monthly_price_inr: int = Field(default=0, ge=0)


class TenantDelete(BaseModel):
    """Hard-delete confirmation — the client must echo the tenant name back."""

    confirm_name: str = Field(..., min_length=1, max_length=255)


class ProviderStats(BaseModel):
    total_orgs: int
    active_orgs: int
    locked_orgs: int
    mrr_inr: int


class MessageResponse(BaseModel):
    message: str


class ProviderUserItem(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    tenant_id: str | None
    tenant_name: str | None
    last_login: datetime | None
    created_at: datetime


class ProviderUsersResponse(BaseModel):
    items: list[ProviderUserItem]
    total: int
    page: int
    page_size: int


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


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug or "tenant"


async def _unique_slug(db: AsyncSession, base: str) -> str:
    """Append -N suffix until slug is free in organizations.slug."""
    candidate = base
    n = 2
    while True:
        existing = (
            await db.execute(select(Organization.id).where(Organization.slug == candidate))
        ).scalar_one_or_none()
        if existing is None:
            return candidate
        candidate = f"{base}-{n}"
        n += 1


@router.post(
    "/organizations",
    response_model=OrganizationSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    payload: TenantCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> OrganizationSummary:
    """Create a tenant, its owner user, first organization and first pump.

    All four rows are created in one transaction. The pump_code is
    normalised to upper-case and must be unique platform-wide — it becomes
    the login key every tenant user types alongside their email+password.
    """
    pump_code = payload.pump_code.strip().upper()
    email = payload.owner_email.lower().strip()

    # Uniqueness checks — email (users + tenants), pump_code.
    if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Email '{email}' is already registered.")
    if (
        await db.execute(select(Tenant).where(Tenant.owner_email == email))
    ).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"A tenant with email '{email}' already exists.")
    if (await db.execute(select(Pump).where(Pump.code == pump_code))).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Pump code '{pump_code}' is already in use.")

    tenant = Tenant(
        name=payload.tenant_name,
        owner_name=payload.owner_name,
        owner_phone=payload.owner_phone,
        owner_email=email,
        subscription_plan=payload.subscription_plan,
        max_orgs=999 if payload.subscription_plan == "ENTERPRISE" else (5 if payload.subscription_plan == "PRO" else 1),
        monthly_price_inr=payload.monthly_price_inr,
        is_active=True,
    )
    db.add(tenant)
    await db.flush()

    slug = await _unique_slug(db, _slugify(payload.org_name or payload.tenant_name))
    org = Organization(
        name=payload.org_name or payload.tenant_name,
        slug=slug,
        contact_email=email,
        tenant_id=tenant.id,
        is_active=True,
    )
    db.add(org)
    await db.flush()

    pump = Pump(
        org_id=org.id,
        name=payload.pump_name or f"{payload.tenant_name} Pump",
        code=pump_code,
        nozzle_count=0,
        is_active=True,
    )
    db.add(pump)

    owner = User(
        email=email,
        phone=payload.owner_phone,
        hashed_password=hash_password(payload.password),
        role=UserRole.OWNER,
        tenant_id=tenant.id,
        org_id=None,
        is_active=True,
    )
    db.add(owner)

    await db.commit()
    await db.refresh(tenant)
    return await _summarize_tenant(db, tenant)


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


# Dependency-ordered DELETE chain for hard tenant teardown.
# See app/models/ — every FK pointing at tenants/organizations/pumps/nozzles
# with ondelete=RESTRICT is cleared here before the org/tenant rows are
# removed. Tables with CASCADE FKs (shifts, workers, nozzle_meter_readings,
# etc.) are removed implicitly when organizations → pumps → nozzles fall.
_TEARDOWN_SQL: tuple[str, ...] = (
    # Inventory chain (fuel_tanks is parent of dip/deliveries)
    "DELETE FROM dip_readings WHERE org_id IN (SELECT id FROM organizations WHERE tenant_id = :tid)",
    "DELETE FROM fuel_deliveries WHERE org_id IN (SELECT id FROM organizations WHERE tenant_id = :tid)",
    "DELETE FROM fuel_tanks WHERE tenant_id = :tid",
    # FMS transactions pin nozzles via RESTRICT
    "DELETE FROM fms_transactions WHERE nozzle_id IN ("
    " SELECT n.id FROM nozzles n"
    " JOIN pumps p ON p.id = n.pump_id"
    " JOIN organizations o ON o.id = p.org_id"
    " WHERE o.tenant_id = :tid)",
    # Org-scoped transaction + maintenance tables
    "DELETE FROM upi_transactions WHERE org_id IN (SELECT id FROM organizations WHERE tenant_id = :tid)",
    "DELETE FROM pos_transactions WHERE org_id IN (SELECT id FROM organizations WHERE tenant_id = :tid)",
    "DELETE FROM pump_logs WHERE org_id IN (SELECT id FROM organizations WHERE tenant_id = :tid)",
    "DELETE FROM pump_downtimes WHERE org_id IN (SELECT id FROM organizations WHERE tenant_id = :tid)",
    # Tenant-scoped aggregates
    "DELETE FROM daily_consolidations WHERE tenant_id = :tid",
    "DELETE FROM audit_logs WHERE tenant_id = :tid",
    # Users block tenant deletion via RESTRICT
    "DELETE FROM users WHERE tenant_id = :tid",
    # Organizations remove remaining pumps/nozzles/shifts/workers via CASCADE
    "DELETE FROM organizations WHERE tenant_id = :tid",
    # Finally, the tenant itself
    "DELETE FROM tenants WHERE id = :tid",
)


@router.delete(
    "/organizations/{tenant_id}",
    response_model=MessageResponse,
)
async def delete_organization(
    tenant_id: uuid.UUID,
    payload: TenantDelete,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> MessageResponse:
    """Permanently delete a tenant and every record scoped to it.

    The caller must echo the tenant's name in ``confirm_name`` to guard
    against accidental deletions. There is no undo.
    """
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    expected = tenant.name.strip()
    if payload.confirm_name.strip() != expected:
        raise HTTPException(
            status_code=400,
            detail=f"Confirmation mismatch. Type the exact tenant name: '{expected}'.",
        )

    removed_name = tenant.name
    tid = str(tenant.id)

    for stmt in _TEARDOWN_SQL:
        await db.execute(text(stmt), {"tid": tid})

    await db.commit()
    await invalidate_tenant_lock(tid)
    return MessageResponse(message=f"Tenant '{removed_name}' permanently deleted.")


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


@router.get("/users", response_model=ProviderUsersResponse)
async def list_users(
    role: str | None = None,
    tenant_id: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> ProviderUsersResponse:
    """List all users across all tenants with optional filters."""
    page = max(1, page)
    page_size = max(1, min(200, page_size))

    stmt = select(User, Tenant.name).join(
        Tenant, Tenant.id == User.tenant_id, isouter=True
    )
    if role:
        stmt = stmt.where(User.role == role.lower())
    if tenant_id:
        try:
            stmt = stmt.where(User.tenant_id == uuid.UUID(tenant_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tenant_id.")
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(func.lower(User.email).like(like))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one() or 0

    stmt = stmt.order_by(User.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    rows = (await db.execute(stmt)).all()

    items = [
        ProviderUserItem(
            id=str(u.id),
            email=u.email,
            role=u.role.value if hasattr(u.role, "value") else str(u.role),
            is_active=u.is_active,
            tenant_id=str(u.tenant_id) if u.tenant_id else None,
            tenant_name=tenant_name,
            last_login=u.last_login,
            created_at=u.created_at,
        )
        for (u, tenant_name) in rows
    ]
    return ProviderUsersResponse(
        items=items, total=int(total), page=page, page_size=page_size
    )


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
