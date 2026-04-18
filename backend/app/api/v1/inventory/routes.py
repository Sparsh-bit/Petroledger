"""PetroLedger — Fuel tank inventory routes.

Endpoints:
    POST /inventory/tanks
    GET  /inventory/tanks                             — list (org-scoped)
    POST /inventory/tanks/{tank_id}/dip-readings
    GET  /inventory/tanks/{tank_id}/dip-readings
    POST /inventory/tanks/{tank_id}/deliveries
    GET  /inventory/tanks/{tank_id}/deliveries
    GET  /inventory/tanks/{tank_id}/stock-summary?start_date=&end_date=
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.core.exceptions import NotFoundError
from app.core.tenant import verify_tenant_match
from app.db.session import get_db
from app.models.fms import FmsTransaction, FmsTxnStatus
from app.models.inventory import DipReading, FuelDelivery, FuelTank
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.shift import Shift
from app.models.user import User, UserRole
from app.utils.pagination import PagedResponse, paginate

router = APIRouter()


# ── Request / Response schemas ──────────────────────────────────────────


class TankCreate(BaseModel):
    org_id: UUID
    tank_number: int = Field(..., ge=1, le=999)
    fuel_type: str = Field(..., min_length=1, max_length=20)
    capacity_litres: Decimal = Field(..., gt=0)
    low_level_threshold: Decimal = Field(default=Decimal("0"), ge=0)


class TankResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    org_id: UUID
    tank_number: int
    fuel_type: str
    capacity_litres: Decimal
    current_level_litres: Decimal
    low_level_threshold: Decimal
    last_dip_reading_at: datetime | None
    is_active: bool


class DipReadingCreate(BaseModel):
    reading_date: date
    reading_litres: Decimal = Field(..., ge=0)
    temperature_celsius: Decimal | None = Field(default=None, ge=-50, le=80)
    notes: str | None = None


class DipReadingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tank_id: UUID
    reading_date: date
    reading_litres: Decimal
    temperature_celsius: Decimal | None
    recorded_by_user_id: UUID | None
    notes: str | None
    created_at: datetime


class DeliveryCreate(BaseModel):
    delivery_date: datetime
    supplier_name: str = Field(..., min_length=1, max_length=255)
    challan_number: str = Field(..., min_length=1, max_length=100)
    invoice_number: str | None = None
    vehicle_number: str | None = None
    volume_ordered_litres: Decimal = Field(..., gt=0)
    volume_received_litres: Decimal = Field(..., gt=0)
    unit_cost_per_litre: Decimal = Field(..., gt=0)


class DeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tank_id: UUID
    delivery_date: datetime
    supplier_name: str
    challan_number: str
    invoice_number: str | None
    vehicle_number: str | None
    volume_ordered_litres: Decimal
    volume_received_litres: Decimal
    unit_cost_per_litre: Decimal
    total_cost: Decimal
    created_at: datetime


class StockSummary(BaseModel):
    tank_id: UUID
    opening_stock: Decimal
    deliveries: Decimal
    sales_volume: Decimal
    closing_stock: Decimal
    theoretical_closing: Decimal
    variance: Decimal


# ── Helpers ─────────────────────────────────────────────────────────────


async def _guard_org(db: AsyncSession, org_id: UUID, user: User) -> Organization:
    org = (
        await db.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one_or_none()
    if org is None:
        raise NotFoundError(resource="Organization", identifier=org_id)
    verify_tenant_match(org.tenant_id, user)
    return org


async def _get_tank(db: AsyncSession, tank_id: UUID, user: User) -> FuelTank:
    tank = (
        await db.execute(select(FuelTank).where(FuelTank.id == tank_id))
    ).scalar_one_or_none()
    if tank is None:
        raise NotFoundError(resource="FuelTank", identifier=tank_id)
    await _guard_org(db, tank.org_id, user)
    return tank


# ── Tanks ───────────────────────────────────────────────────────────────


@router.post(
    "/tanks",
    response_model=TankResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a fuel storage tank",
)
async def create_tank(
    payload: TankCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> TankResponse:
    org = await _guard_org(db, payload.org_id, current_user)
    tank = FuelTank(
        org_id=org.id,
        tenant_id=org.tenant_id,
        tank_number=payload.tank_number,
        fuel_type=payload.fuel_type,
        capacity_litres=payload.capacity_litres,
        current_level_litres=Decimal("0"),
        low_level_threshold=payload.low_level_threshold,
    )
    db.add(tank)
    await db.flush()
    await db.refresh(tank)
    await db.commit()
    return TankResponse.model_validate(tank)


@router.get(
    "/tanks",
    response_model=PagedResponse[TankResponse],
    summary="List fuel tanks for an organization",
)
async def list_tanks(
    org_id: UUID = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PagedResponse[TankResponse]:
    await _guard_org(db, org_id, current_user)
    stmt = (
        select(FuelTank)
        .where(FuelTank.org_id == org_id, FuelTank.is_active == True)  # noqa: E712
        .order_by(FuelTank.tank_number)
    )
    return await paginate(db, stmt, page, page_size, TankResponse)


# ── Dip readings ────────────────────────────────────────────────────────


@router.post(
    "/tanks/{tank_id}/dip-readings",
    response_model=DipReadingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dip_reading(
    tank_id: UUID,
    payload: DipReadingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> DipReadingResponse:
    tank = await _get_tank(db, tank_id, current_user)
    reading = DipReading(
        org_id=tank.org_id,
        tank_id=tank.id,
        reading_date=payload.reading_date,
        reading_litres=payload.reading_litres,
        temperature_celsius=payload.temperature_celsius,
        recorded_by_user_id=current_user.id,
        notes=payload.notes,
    )
    db.add(reading)
    # Dip is the authoritative level — replace current_level with it.
    tank.current_level_litres = payload.reading_litres
    tank.last_dip_reading_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(reading)
    await db.commit()
    return DipReadingResponse.model_validate(reading)


@router.get(
    "/tanks/{tank_id}/dip-readings",
    response_model=PagedResponse[DipReadingResponse],
)
async def list_dip_readings(
    tank_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> PagedResponse[DipReadingResponse]:
    await _get_tank(db, tank_id, current_user)
    stmt = (
        select(DipReading)
        .where(DipReading.tank_id == tank_id)
        .order_by(DipReading.reading_date.desc(), DipReading.created_at.desc())
    )
    return await paginate(db, stmt, page, page_size, DipReadingResponse)


# ── Deliveries ──────────────────────────────────────────────────────────


@router.post(
    "/tanks/{tank_id}/deliveries",
    response_model=DeliveryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_delivery(
    tank_id: UUID,
    payload: DeliveryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> DeliveryResponse:
    tank = await _get_tank(db, tank_id, current_user)
    total_cost = (
        payload.volume_received_litres * payload.unit_cost_per_litre
    ).quantize(Decimal("0.01"))

    delivery = FuelDelivery(
        org_id=tank.org_id,
        tank_id=tank.id,
        delivery_date=payload.delivery_date,
        supplier_name=payload.supplier_name,
        challan_number=payload.challan_number,
        invoice_number=payload.invoice_number,
        vehicle_number=payload.vehicle_number,
        volume_ordered_litres=payload.volume_ordered_litres,
        volume_received_litres=payload.volume_received_litres,
        unit_cost_per_litre=payload.unit_cost_per_litre,
        total_cost=total_cost,
        created_by_user_id=current_user.id,
    )
    db.add(delivery)
    tank.current_level_litres = tank.current_level_litres + payload.volume_received_litres
    await db.flush()
    await db.refresh(delivery)
    await db.commit()
    return DeliveryResponse.model_validate(delivery)


@router.get(
    "/tanks/{tank_id}/deliveries",
    response_model=PagedResponse[DeliveryResponse],
)
async def list_deliveries(
    tank_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> PagedResponse[DeliveryResponse]:
    await _get_tank(db, tank_id, current_user)
    stmt = (
        select(FuelDelivery)
        .where(FuelDelivery.tank_id == tank_id)
        .order_by(FuelDelivery.delivery_date.desc())
    )
    return await paginate(db, stmt, page, page_size, DeliveryResponse)


# ── Stock summary ───────────────────────────────────────────────────────


@router.get(
    "/tanks/{tank_id}/stock-summary",
    response_model=StockSummary,
    summary="Stock reconciliation for a date range",
)
async def stock_summary(
    tank_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> StockSummary:
    """Compute opening / deliveries / sales / closing for *tank_id*.

    - opening_stock       — most recent dip reading ≤ start_date (0 if none)
    - deliveries          — sum of volume_received_litres in [start, end]
    - sales_volume        — sum of FmsTransaction.volume_litres for SALE
                            subtype + COMPLETED, for shifts whose
                            start_time falls in [start, end], where the
                            transaction's product_code matches the tank's fuel
    - closing_stock       — current tank level (source of truth)
    - theoretical_closing — opening + deliveries - sales
    - variance            — theoretical_closing - closing_stock
    """
    tank = await _get_tank(db, tank_id, current_user)

    opening_row = (
        await db.execute(
            select(DipReading.reading_litres)
            .where(DipReading.tank_id == tank_id, DipReading.reading_date <= start_date)
            .order_by(DipReading.reading_date.desc(), DipReading.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    opening = Decimal(str(opening_row)) if opening_row is not None else Decimal("0")

    deliveries_total = Decimal(
        str(
            (
                await db.execute(
                    select(
                        func.coalesce(func.sum(FuelDelivery.volume_received_litres), 0)
                    ).where(
                        FuelDelivery.tank_id == tank_id,
                        FuelDelivery.delivery_date >= start_date,
                        FuelDelivery.delivery_date <= end_date,
                    )
                )
            ).scalar_one()
        )
    )

    # Sales: join FmsTransaction → Shift → Pump filtered by org + fuel match.
    sales_total = Decimal(
        str(
            (
                await db.execute(
                    select(func.coalesce(func.sum(FmsTransaction.volume_litres), 0))
                    .select_from(FmsTransaction)
                    .join(Shift, Shift.id == FmsTransaction.shift_id)
                    .join(Pump, Pump.id == Shift.pump_id)
                    .where(
                        Pump.org_id == tank.org_id,
                        Shift.start_time >= start_date,
                        Shift.start_time <= end_date,
                        FmsTransaction.status == FmsTxnStatus.COMPLETED,
                        FmsTransaction.is_deleted.is_(False),
                        FmsTransaction.subtype == "SALE",
                        FmsTransaction.product_code == tank.fuel_type,
                    )
                )
            ).scalar_one()
        )
    )

    closing = Decimal(str(tank.current_level_litres))
    theoretical = opening + deliveries_total - sales_total
    variance = theoretical - closing

    return StockSummary(
        tank_id=tank.id,
        opening_stock=opening,
        deliveries=deliveries_total,
        sales_volume=sales_total,
        closing_stock=closing,
        theoretical_closing=theoretical,
        variance=variance,
    )
