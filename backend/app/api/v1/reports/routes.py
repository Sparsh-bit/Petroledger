"""
PetroLedger — Report Download Endpoints.

GET /api/v1/reports/shift/{shift_id}      → PDF for a single shift
GET /api/v1/reports/daily                  → PDF or Excel daily summary

Role access:
    OWNER / ADMIN  → full access (download)
    MANAGER        → can trigger but cannot download (403 on download)
    WORKER         → no access
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.core.exceptions import NotFoundError, ValidationError
from app.core.tenant import verify_tenant_match
from app.db.session import get_db
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.shift import Shift
from app.models.user import User, UserRole
from app.services.reports.daily_report import DailyReportService
from app.services.reports.shift_report import ShiftReportService

router = APIRouter()


@router.get(
    "/shift/{shift_id}",
    summary="Download shift reconciliation report (PDF)",
    response_class=FileResponse,
)
async def download_shift_report(
    shift_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> FileResponse:
    """Generate and download the PDF reconciliation report for a single shift.

    Raises 404 when the shift is not found.
    Raises 403 when the user is not OWNER or ADMIN.
    """
    # Verify shift belongs to user's tenant
    stmt = (
        select(Organization.tenant_id)
        .join(Pump, Pump.org_id == Organization.id)
        .join(Shift, Shift.pump_id == Pump.id)
        .where(Shift.id == shift_id)
    )
    result = await db.execute(stmt)
    shift_tenant_id = result.scalar_one_or_none()
    if shift_tenant_id is None:
        raise NotFoundError(resource="Shift", identifier=str(shift_id))
    verify_tenant_match(shift_tenant_id, current_user)

    svc = ShiftReportService()
    try:
        path = await svc.generate(shift_id, db)
    except NotFoundError:
        raise

    suffix = path.suffix or ".pdf"
    media = "application/pdf" if suffix == ".pdf" else "text/html"
    return FileResponse(
        path=str(path),
        media_type=media,
        filename=path.name,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@router.get(
    "/daily",
    summary="Download daily summary report (PDF or Excel)",
    response_class=FileResponse,
)
async def download_daily_report(
    site_id: uuid.UUID = Query(..., description="Organisation / site UUID"),
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
    format: str = Query("pdf", description="Output format: pdf or excel"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    _: None = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> FileResponse:
    """Generate and download the daily summary report for a site.

    Supports ``?format=pdf`` (default) or ``?format=excel``.

    Raises 422 when an unsupported format is requested.
    Raises 403 when the user is not OWNER or ADMIN.
    """
    if format not in ("pdf", "excel"):
        raise ValidationError("format must be 'pdf' or 'excel'")

    # Verify site/org belongs to user's tenant
    org_result = await db.execute(
        select(Organization.tenant_id).where(Organization.id == site_id)
    )
    org_tenant_id = org_result.scalar_one_or_none()
    if org_tenant_id is None:
        raise NotFoundError(resource="Organization", identifier=str(site_id))
    verify_tenant_match(org_tenant_id, current_user)

    svc = DailyReportService()

    if format == "excel":
        path = await svc.generate_excel(site_id, report_date, db)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        path = await svc.generate_pdf(site_id, report_date, db)
        suffix = path.suffix or ".pdf"
        media = "application/pdf" if suffix == ".pdf" else "text/html"

    return FileResponse(
        path=str(path),
        media_type=media,
        filename=path.name,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )
