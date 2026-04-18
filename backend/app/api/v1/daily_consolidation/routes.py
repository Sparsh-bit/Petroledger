"""PetroLedger — Daily consolidation query routes.

Read-only access to the per-(org, day) rollups computed by the EOD
sweep (and opportunistically when a shift moves to LOCKED).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rbac import require_role
from app.core.tenant import verify_tenant_match
from app.db.session import get_db
from app.models.daily_consolidation import DailyConsolidation, DailyConsolidationStatus
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.utils.pagination import PagedResponse, paginate

router = APIRouter()


class DailyConsolidationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    tenant_id: UUID
    date: date
    total_fms_amount: Decimal
    total_upi_amount: Decimal
    total_card_amount: Decimal
    total_fleet_amount: Decimal
    total_cash_collected: Decimal
    net_variance: Decimal
    s1_shift_id: UUID | None
    s2_shift_id: UUID | None
    s3_shift_id: UUID | None
    anomaly_count: int
    confidence_avg: Decimal | None
    status: DailyConsolidationStatus
    computed_at: datetime | None


@router.get(
    "/organizations/{org_id}/daily-consolidation",
    response_model=PagedResponse[DailyConsolidationResponse],
    summary="List daily consolidations for an organization (OWNER + ADMIN only)",
)
async def list_daily_consolidations(
    org_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> PagedResponse[DailyConsolidationResponse]:
    """Return daily consolidations for *org_id* within the date range."""
    # Tenant boundary: ensure the target org belongs to the caller's tenant.
    org = (
        await db.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one_or_none()
    if org is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(resource="Organization", identifier=org_id)
    verify_tenant_match(org.tenant_id, current_user)

    stmt = (
        select(DailyConsolidation)
        .where(
            DailyConsolidation.org_id == org_id,
            DailyConsolidation.date >= start_date,
            DailyConsolidation.date <= end_date,
        )
        .order_by(DailyConsolidation.date.desc())
    )
    return await paginate(db, stmt, page, page_size, DailyConsolidationResponse)
