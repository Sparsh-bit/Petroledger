"""PetroLedger — Superadmin / Developer Portal Routes.

All endpoints here bypass tenant isolation and are restricted to the
SUPERADMIN_EMAIL account only.  They provide full cross-tenant CRUD
for platform management.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.superadmin import get_superadmin
from app.core.exceptions import NotFoundError
from app.core.security import hash_password
from app.db.session import get_db
from app.models.assignments import AnomalyFlag
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.reconciliation import ReconciliationResult
from app.models.shift import Shift, ShiftStatus
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.worker import Worker
from app.utils.pagination import PagedResponse, paginate

router = APIRouter()

# ── Pydantic helpers ──────────────────────────────────────────────────────────


class TenantOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    name: str
    owner_name: str
    owner_email: str
    owner_phone: str
    subscription_plan: str
    max_orgs: int
    is_active: bool
    created_at: Any
    updated_at: Any


class TenantUpdate(BaseModel):
    name: str | None = None
    subscription_plan: str | None = None
    max_orgs: int | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    email: str
    phone: str | None
    role: str
    tenant_id: str
    org_id: str | None
    is_active: bool
    created_at: Any
    updated_at: Any


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


class OrgOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    name: str
    tenant_id: str
    contact_email: str
    omc_type: str
    is_active: bool
    created_at: Any
    updated_at: Any


class OrgUpdate(BaseModel):
    name: str | None = None
    contact_email: str | None = None
    is_active: bool | None = None


class PumpOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    name: str
    org_id: str
    location: str | None
    nozzle_count: int
    is_active: bool
    created_at: Any
    updated_at: Any


class ShiftOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    pump_id: str
    worker_id: str | None
    slot: str
    shift_date: Any
    start_time: Any
    end_time: Any | None
    status: str
    created_at: Any


class WorkerOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    user_id: str
    pump_id: str
    employee_code: str | None
    is_active: bool
    created_at: Any


class ReconOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    shift_id: str
    status: str
    variance_type: str | None
    expected_cash: Any | None
    actual_cash: Any | None
    variance: Any | None
    confidence_score: int | None
    created_at: Any


class AnomalyOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    site_id: str
    shift_id: str | None
    flag_type: str
    severity: str
    description: str
    is_resolved: bool
    created_at: Any


class StatsOut(BaseModel):
    tenants: int
    users: int
    organizations: int
    pumps: int
    shifts_total: int
    shifts_active: int
    workers: int
    reconciliations: int
    anomalies_open: int


# ── GET /superadmin/stats ─────────────────────────────────────────────────────


@router.get("/stats", response_model=StatsOut, summary="Platform-wide statistics")
async def get_stats(
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> StatsOut:
    tenants = (await db.execute(select(func.count()).select_from(Tenant))).scalar_one()
    users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    orgs = (await db.execute(select(func.count()).select_from(Organization))).scalar_one()
    pumps = (await db.execute(select(func.count()).select_from(Pump))).scalar_one()
    shifts_total = (await db.execute(select(func.count()).select_from(Shift))).scalar_one()
    shifts_active = (await db.execute(
        select(func.count()).select_from(Shift).where(Shift.status == ShiftStatus.ACTIVE)
    )).scalar_one()
    workers = (await db.execute(select(func.count()).select_from(Worker))).scalar_one()
    recons = (await db.execute(select(func.count()).select_from(ReconciliationResult))).scalar_one()
    anomalies = (await db.execute(
        select(func.count()).select_from(AnomalyFlag).where(AnomalyFlag.is_resolved == False)  # noqa: E712
    )).scalar_one()
    return StatsOut(
        tenants=tenants,
        users=users,
        organizations=orgs,
        pumps=pumps,
        shifts_total=shifts_total,
        shifts_active=shifts_active,
        workers=workers,
        reconciliations=recons,
        anomalies_open=anomalies,
    )


# ── TENANTS ───────────────────────────────────────────────────────────────────


@router.get("/tenants", response_model=PagedResponse[TenantOut], summary="List all tenants")
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[TenantOut]:
    q = select(Tenant).order_by(Tenant.created_at.desc())
    return await paginate(db, q, page, page_size, TenantOut)


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
async def get_tenant(
    tenant_id: uuid.UUID,
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> TenantOut:
    row = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not row:
        raise NotFoundError("Tenant not found")
    return TenantOut.model_validate(row)


@router.patch("/tenants/{tenant_id}", response_model=TenantOut)
async def update_tenant(
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> TenantOut:
    row = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not row:
        raise NotFoundError("Tenant not found")
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(row, field, val)
    await db.flush()
    await db.refresh(row)
    await db.commit()
    return TenantOut.model_validate(row)


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: uuid.UUID,
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not row:
        raise NotFoundError("Tenant not found")
    await db.delete(row)
    await db.commit()


# ── USERS ─────────────────────────────────────────────────────────────────────


@router.get("/users", response_model=PagedResponse[UserOut], summary="List all users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: uuid.UUID | None = Query(None),
    role: str | None = Query(None),
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[UserOut]:
    q = select(User).order_by(User.created_at.desc())
    if tenant_id:
        q = q.where(User.tenant_id == tenant_id)
    if role:
        q = q.where(User.role == role)
    return await paginate(db, q, page, page_size, UserOut)


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    row = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not row:
        raise NotFoundError("User not found")
    return UserOut.model_validate(row)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    row = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not row:
        raise NotFoundError("User not found")
    data = payload.model_dump(exclude_none=True)
    if "password" in data:
        row.hashed_password = hash_password(data.pop("password"))
    for field, val in data.items():
        setattr(row, field, val)
    await db.flush()
    await db.refresh(row)
    await db.commit()
    return UserOut.model_validate(row)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not row:
        raise NotFoundError("User not found")
    await db.delete(row)
    await db.commit()


# ── ORGANIZATIONS ─────────────────────────────────────────────────────────────


@router.get("/organizations", response_model=PagedResponse[OrgOut], summary="List all organizations")
async def list_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: uuid.UUID | None = Query(None),
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[OrgOut]:
    q = select(Organization).order_by(Organization.created_at.desc())
    if tenant_id:
        q = q.where(Organization.tenant_id == tenant_id)
    return await paginate(db, q, page, page_size, OrgOut)


@router.patch("/organizations/{org_id}", response_model=OrgOut)
async def update_organization(
    org_id: uuid.UUID,
    payload: OrgUpdate,
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> OrgOut:
    row = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not row:
        raise NotFoundError("Organization not found")
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(row, field, val)
    await db.flush()
    await db.refresh(row)
    await db.commit()
    return OrgOut.model_validate(row)


@router.delete("/organizations/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: uuid.UUID,
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if not row:
        raise NotFoundError("Organization not found")
    await db.delete(row)
    await db.commit()


# ── PUMPS ─────────────────────────────────────────────────────────────────────


@router.get("/pumps", response_model=PagedResponse[PumpOut], summary="List all pumps")
async def list_pumps(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    org_id: uuid.UUID | None = Query(None),
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[PumpOut]:
    q = select(Pump).order_by(Pump.created_at.desc())
    if org_id:
        q = q.where(Pump.org_id == org_id)
    return await paginate(db, q, page, page_size, PumpOut)


@router.delete("/pumps/{pump_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pump(
    pump_id: uuid.UUID,
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = (await db.execute(select(Pump).where(Pump.id == pump_id))).scalar_one_or_none()
    if not row:
        raise NotFoundError("Pump not found")
    await db.delete(row)
    await db.commit()


# ── SHIFTS ────────────────────────────────────────────────────────────────────


@router.get("/shifts", response_model=PagedResponse[ShiftOut], summary="List all shifts")
async def list_shifts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    pump_id: uuid.UUID | None = Query(None),
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[ShiftOut]:
    q = select(Shift).order_by(Shift.created_at.desc())
    if status:
        q = q.where(Shift.status == status)
    if pump_id:
        q = q.where(Shift.pump_id == pump_id)
    return await paginate(db, q, page, page_size, ShiftOut)


@router.patch("/shifts/{shift_id}/status", response_model=ShiftOut)
async def update_shift_status(
    shift_id: uuid.UUID,
    body: dict[str, str],
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> ShiftOut:
    row = (await db.execute(select(Shift).where(Shift.id == shift_id))).scalar_one_or_none()
    if not row:
        raise NotFoundError("Shift not found")
    row.status = body.get("status", row.status)
    await db.flush()
    await db.refresh(row)
    await db.commit()
    return ShiftOut.model_validate(row)


# ── WORKERS ───────────────────────────────────────────────────────────────────


@router.get("/workers", response_model=PagedResponse[WorkerOut], summary="List all workers")
async def list_workers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    pump_id: uuid.UUID | None = Query(None),
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[WorkerOut]:
    q = select(Worker).order_by(Worker.created_at.desc())
    if pump_id:
        q = q.where(Worker.pump_id == pump_id)
    return await paginate(db, q, page, page_size, WorkerOut)


# ── RECONCILIATION ────────────────────────────────────────────────────────────


@router.get("/reconciliation", response_model=PagedResponse[ReconOut], summary="List all reconciliation results")
async def list_reconciliation(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    recon_status: str | None = Query(None, alias="status"),
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[ReconOut]:
    q = select(ReconciliationResult).order_by(ReconciliationResult.created_at.desc())
    if recon_status:
        q = q.where(ReconciliationResult.status == recon_status)
    return await paginate(db, q, page, page_size, ReconOut)


# ── ANOMALY FLAGS ─────────────────────────────────────────────────────────────


@router.get("/anomaly-flags", response_model=PagedResponse[AnomalyOut], summary="List all anomaly flags")
async def list_anomaly_flags(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_resolved: bool | None = Query(None),
    severity: str | None = Query(None),
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[AnomalyOut]:
    q = select(AnomalyFlag).order_by(AnomalyFlag.created_at.desc())
    if is_resolved is not None:
        q = q.where(AnomalyFlag.is_resolved == is_resolved)
    if severity:
        q = q.where(AnomalyFlag.severity == severity)
    return await paginate(db, q, page, page_size, AnomalyOut)


@router.patch("/anomaly-flags/{flag_id}/resolve", response_model=AnomalyOut)
async def resolve_anomaly(
    flag_id: uuid.UUID,
    _: User = Depends(get_superadmin),
    db: AsyncSession = Depends(get_db),
) -> AnomalyOut:
    row = (await db.execute(select(AnomalyFlag).where(AnomalyFlag.id == flag_id))).scalar_one_or_none()
    if not row:
        raise NotFoundError("Anomaly flag not found")
    row.is_resolved = True
    await db.flush()
    await db.refresh(row)
    await db.commit()
    return AnomalyOut.model_validate(row)
