"""PetroLedger — Provider Portal Routes (SUPERADMIN only).

Management surface for the platform operator (the company running
PetroLedger). Lists tenants, lock/unlock, adjust subscriptions, KPIs.
"""

from __future__ import annotations

import logging
import re
import secrets
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.core.email import send_email
from app.core.security import hash_password
from app.core.tenant_lock_cache import invalidate_tenant_lock
from app.db.session import get_db
from app.models.feature import TenantFeature, TenantFeatureOverride, TenantPaymentConfig
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.tenant import Tenant
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

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
    owner_phone: str = Field(default="", max_length=20)
    password: str = Field(..., min_length=8, max_length=64)
    pump_code: str | None = Field(default=None, max_length=32)
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

# Pump-code alphabet — excludes 0/O/1/I to keep codes readable when typed.
_PUMP_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug or "tenant"


async def _generate_unique_pump_code(db: AsyncSession) -> str:
    """Produce a unique, human-friendly pump code like PL-ABCD-2345.

    Retries on collision; after a few tries the odds of another collision
    are ~0 (32^8 ≈ 1e12 space), so this loop practically always exits on
    attempt 1.
    """
    for _ in range(8):
        core = "".join(secrets.choice(_PUMP_CODE_ALPHABET) for _ in range(8))
        candidate = f"PL-{core[:4]}-{core[4:]}"
        existing = (
            await db.execute(select(Pump.id).where(Pump.code == candidate))
        ).scalar_one_or_none()
        if existing is None:
            return candidate
    raise HTTPException(
        status_code=500, detail="Could not generate a unique pump code — try again."
    )


def _welcome_email_html(
    *, tenant_name: str, owner_name: str, owner_email: str,
    pump_code: str, password: str,
) -> str:
    return f"""<!doctype html>
<html><body style="font-family:Inter,system-ui,sans-serif;background:#f8fafc;margin:0;padding:24px;color:#0f172a;">
  <table style="max-width:560px;margin:0 auto;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:32px;">
    <tr><td>
      <h1 style="font-size:20px;margin:0 0 8px;">Welcome to PetroLedger, {owner_name}</h1>
      <p style="color:#475569;margin:0 0 20px;font-size:14px;">
        Your <strong>{tenant_name}</strong> workspace is ready. Use the credentials
        below to sign in at the pump staff portal. Share the pump code with
        every admin, manager and worker at this location — they'll all need it
        to log in alongside their own email and password.
      </p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0 20px;">
        <tr><td style="padding:8px 0;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;color:#64748b;">Pump Code</td>
            <td style="padding:8px 0;font-family:JetBrains Mono,ui-monospace,monospace;font-size:15px;font-weight:700;color:#4338ca;text-align:right;">{pump_code}</td></tr>
        <tr><td style="padding:8px 0;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;color:#64748b;border-top:1px solid #f1f5f9;">Email</td>
            <td style="padding:8px 0;font-size:14px;text-align:right;border-top:1px solid #f1f5f9;">{owner_email}</td></tr>
        <tr><td style="padding:8px 0;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;color:#64748b;border-top:1px solid #f1f5f9;">Temporary Password</td>
            <td style="padding:8px 0;font-family:JetBrains Mono,ui-monospace,monospace;font-size:14px;text-align:right;border-top:1px solid #f1f5f9;">{password}</td></tr>
      </table>
      <p style="font-size:13px;color:#b45309;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 12px;margin:0 0 20px;">
        Please change your password after your first sign-in from Settings → Security.
      </p>
      <p style="font-size:12px;color:#94a3b8;margin:24px 0 0;">
        — The PetroLedger Team · support@petroledger.in
      </p>
    </td></tr>
  </table>
</body></html>"""


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


async def provision_tenant_workspace(
    db: AsyncSession,
    *,
    tenant_name: str,
    owner_name: str,
    owner_email: str,
    owner_phone: str,
    password: str,
    pump_code: str | None = None,
    org_name: str | None = None,
    pump_name: str | None = None,
    subscription_plan: str = "BASIC",
    monthly_price_inr: int = 0,
) -> tuple[Tenant, str]:
    """Shared provisioning path — used by both the direct provider-portal
    "Create Tenant" flow and the access-request approval flow.

    Creates tenant + owner user + first organization + first pump in one
    transaction and returns ``(tenant, pump_code)``. The pump code is the
    per-tenant login key that every user types alongside email+password.
    Sends a welcome email with the credentials; email failure is logged
    and swallowed (never rolls back the workspace).
    """
    email = owner_email.lower().strip()

    # Uniqueness checks — email (users + tenants).
    if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Email '{email}' is already registered.")
    if (
        await db.execute(select(Tenant).where(Tenant.owner_email == email))
    ).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"A tenant with email '{email}' already exists.")

    if pump_code and pump_code.strip():
        final_code = pump_code.strip().upper()
        if (
            await db.execute(select(Pump).where(Pump.code == final_code))
        ).scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409, detail=f"Pump code '{final_code}' is already in use."
            )
    else:
        final_code = await _generate_unique_pump_code(db)

    tenant = Tenant(
        name=tenant_name,
        owner_name=owner_name,
        owner_phone=owner_phone,
        owner_email=email,
        subscription_plan=subscription_plan,
        max_orgs=999 if subscription_plan == "ENTERPRISE" else (5 if subscription_plan == "PRO" else 1),
        monthly_price_inr=monthly_price_inr,
        is_active=True,
    )
    db.add(tenant)
    await db.flush()

    slug = await _unique_slug(db, _slugify(org_name or tenant_name))
    org = Organization(
        name=org_name or tenant_name,
        slug=slug,
        contact_email=email,
        tenant_id=tenant.id,
        is_active=True,
    )
    db.add(org)
    await db.flush()

    pump = Pump(
        org_id=org.id,
        name=pump_name or f"{tenant_name} Pump",
        code=final_code,
        nozzle_count=0,
        is_active=True,
    )
    db.add(pump)

    owner = User(
        email=email,
        phone=owner_phone,
        hashed_password=hash_password(password),
        role=UserRole.OWNER,
        tenant_id=tenant.id,
        org_id=None,
        is_active=True,
    )
    db.add(owner)

    await db.commit()
    await db.refresh(tenant)

    try:
        await send_email(
            to=email,
            subject=f"Your PetroLedger workspace is ready — pump code {final_code}",
            html_body=_welcome_email_html(
                tenant_name=tenant_name,
                owner_name=owner_name,
                owner_email=email,
                pump_code=final_code,
                password=password,
            ),
        )
    except Exception:
        logger.exception(
            "Welcome email failed for tenant=%s email=%s", tenant.id, email
        )

    return tenant, final_code


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
    """Create a tenant + owner + first org + first pump in one transaction.

    Thin wrapper around ``provision_tenant_workspace`` — same helper is
    re-used by the access-request approval flow so we have one canonical
    provisioning path across the app.
    """
    tenant, _code = await provision_tenant_workspace(
        db,
        tenant_name=payload.tenant_name,
        owner_name=payload.owner_name,
        owner_email=payload.owner_email,
        owner_phone=payload.owner_phone,
        password=payload.password,
        pump_code=payload.pump_code,
        org_name=payload.org_name,
        pump_name=payload.pump_name,
        subscription_plan=payload.subscription_plan,
        monthly_price_inr=payload.monthly_price_inr,
    )
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
    if payload.confirm_name.strip().casefold() != expected.casefold():
        raise HTTPException(
            status_code=400,
            detail=f"Confirmation mismatch. Type the tenant name: '{expected}'.",
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


# ── Features ─────────────────────────────────────────────────────────────


class FeatureItem(BaseModel):
    id: int
    key: str
    name: str
    module: str
    is_core: bool
    plan_enabled: bool
    override_enabled: bool | None
    effective: bool
    source: str  # "core" | "plan" | "override" | "none"


class FeatureOverridePayload(BaseModel):
    enabled: bool
    reason: str | None = None


async def _get_tenant_or_404(tenant_id: uuid.UUID, db: AsyncSession) -> Tenant:
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return t


@router.get("/organizations/{tenant_id}/features", response_model=list[FeatureItem])
async def list_tenant_features(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> list[FeatureItem]:
    """Return all features annotated with plan-default and per-tenant override state."""
    tenant = await _get_tenant_or_404(tenant_id, db)
    features = (await db.execute(select(TenantFeature).order_by(TenantFeature.id))).scalars().all()
    overrides_rows = (
        await db.execute(
            select(TenantFeatureOverride).where(TenantFeatureOverride.tenant_id == tenant_id)
        )
    ).scalars().all()
    overrides = {o.feature_id: o for o in overrides_rows}
    plan = tenant.subscription_plan.upper()

    items: list[FeatureItem] = []
    for f in features:
        plan_enabled = plan in [p.strip() for p in f.included_in_plans.split(",") if p.strip()]
        override = overrides.get(f.id)
        override_enabled = override.is_enabled if override else None

        if f.is_core:
            effective = True
            source = "core"
        elif override is not None:
            effective = override.is_enabled
            source = "override"
        elif plan_enabled:
            effective = True
            source = "plan"
        else:
            effective = False
            source = "none"

        items.append(
            FeatureItem(
                id=f.id,
                key=f.key,
                name=f.name,
                module=f.module,
                is_core=f.is_core,
                plan_enabled=plan_enabled,
                override_enabled=override_enabled,
                effective=effective,
                source=source,
            )
        )
    return items


@router.put(
    "/organizations/{tenant_id}/features/{feature_id}",
    response_model=FeatureItem,
)
async def set_feature_override(
    tenant_id: uuid.UUID,
    feature_id: int,
    payload: FeatureOverridePayload,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> FeatureItem:
    """Force-enable or force-disable a feature for a specific tenant."""
    tenant = await _get_tenant_or_404(tenant_id, db)
    feature = (
        await db.execute(select(TenantFeature).where(TenantFeature.id == feature_id))
    ).scalar_one_or_none()
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    if feature.is_core:
        raise HTTPException(status_code=400, detail="Core features cannot be overridden.")

    existing = (
        await db.execute(
            select(TenantFeatureOverride).where(
                TenantFeatureOverride.tenant_id == tenant_id,
                TenantFeatureOverride.feature_id == feature_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.is_enabled = payload.enabled
        existing.reason = payload.reason
    else:
        db.add(
            TenantFeatureOverride(
                tenant_id=tenant_id,
                feature_id=feature_id,
                is_enabled=payload.enabled,
                reason=payload.reason,
            )
        )
    await db.commit()

    # Return updated item
    plan = tenant.subscription_plan.upper()
    plan_enabled = plan in [p.strip() for p in feature.included_in_plans.split(",") if p.strip()]
    return FeatureItem(
        id=feature.id,
        key=feature.key,
        name=feature.name,
        module=feature.module,
        is_core=feature.is_core,
        plan_enabled=plan_enabled,
        override_enabled=payload.enabled,
        effective=payload.enabled,
        source="override",
    )


@router.delete(
    "/organizations/{tenant_id}/features/{feature_id}",
    response_model=MessageResponse,
)
async def clear_feature_override(
    tenant_id: uuid.UUID,
    feature_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> MessageResponse:
    """Remove a per-tenant override, reverting the feature to its plan default."""
    await _get_tenant_or_404(tenant_id, db)
    existing = (
        await db.execute(
            select(TenantFeatureOverride).where(
                TenantFeatureOverride.tenant_id == tenant_id,
                TenantFeatureOverride.feature_id == feature_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="No override found for this feature.")
    await db.delete(existing)
    await db.commit()
    return MessageResponse(message="Override cleared — feature reverted to plan default.")


# ── Payment Config ────────────────────────────────────────────────────────


class PaymentConfigResponse(BaseModel):
    configured: bool
    gateway: str
    key_id_masked: str | None
    has_webhook_secret: bool
    is_enabled: bool


class PaymentConfigPayload(BaseModel):
    gateway: str = Field(default="razorpay", pattern="^(razorpay|paytm)$")
    key_id: str = Field(..., min_length=4, max_length=255)
    key_secret: str = Field(..., min_length=4, max_length=512)
    webhook_secret: str | None = Field(default=None, max_length=512)


def _mask(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]


@router.get(
    "/organizations/{tenant_id}/payment-config",
    response_model=PaymentConfigResponse,
)
async def get_payment_config(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> PaymentConfigResponse:
    await _get_tenant_or_404(tenant_id, db)
    cfg = (
        await db.execute(
            select(TenantPaymentConfig).where(TenantPaymentConfig.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if cfg is None:
        return PaymentConfigResponse(
            configured=False,
            gateway="razorpay",
            key_id_masked=None,
            has_webhook_secret=False,
            is_enabled=False,
        )
    return PaymentConfigResponse(
        configured=True,
        gateway=cfg.gateway,
        key_id_masked=_mask(cfg.key_id),
        has_webhook_secret=bool(cfg.webhook_secret),
        is_enabled=cfg.is_enabled,
    )


@router.post(
    "/organizations/{tenant_id}/payment-config",
    response_model=PaymentConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_payment_config(
    tenant_id: uuid.UUID,
    payload: PaymentConfigPayload,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> PaymentConfigResponse:
    """Create or replace the payment gateway config for a tenant."""
    await _get_tenant_or_404(tenant_id, db)
    existing = (
        await db.execute(
            select(TenantPaymentConfig).where(TenantPaymentConfig.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()

    if existing:
        existing.gateway = payload.gateway
        existing.key_id = payload.key_id
        existing.key_secret = payload.key_secret
        existing.webhook_secret = payload.webhook_secret
        existing.is_enabled = True
    else:
        db.add(
            TenantPaymentConfig(
                tenant_id=tenant_id,
                gateway=payload.gateway,
                key_id=payload.key_id,
                key_secret=payload.key_secret,
                webhook_secret=payload.webhook_secret,
                is_enabled=True,
            )
        )
    await db.commit()
    return PaymentConfigResponse(
        configured=True,
        gateway=payload.gateway,
        key_id_masked=_mask(payload.key_id),
        has_webhook_secret=bool(payload.webhook_secret),
        is_enabled=True,
    )


@router.delete(
    "/organizations/{tenant_id}/payment-config",
    response_model=MessageResponse,
)
async def delete_payment_config(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> MessageResponse:
    await _get_tenant_or_404(tenant_id, db)
    cfg = (
        await db.execute(
            select(TenantPaymentConfig).where(TenantPaymentConfig.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="No payment config found.")
    await db.delete(cfg)
    await db.commit()
    return MessageResponse(message="Payment configuration removed.")


@router.put(
    "/organizations/{tenant_id}/payment-config/toggle",
    response_model=PaymentConfigResponse,
)
async def toggle_payment_config(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
) -> PaymentConfigResponse:
    """Toggle the payment gateway on or off without removing credentials."""
    await _get_tenant_or_404(tenant_id, db)
    cfg = (
        await db.execute(
            select(TenantPaymentConfig).where(TenantPaymentConfig.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="No payment config found. Save one first.")
    cfg.is_enabled = not cfg.is_enabled
    await db.commit()
    await db.refresh(cfg)
    return PaymentConfigResponse(
        configured=True,
        gateway=cfg.gateway,
        key_id_masked=_mask(cfg.key_id),
        has_webhook_secret=bool(cfg.webhook_secret),
        is_enabled=cfg.is_enabled,
    )
