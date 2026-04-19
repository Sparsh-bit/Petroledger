"""PetroLedger — Provider-only Access Request Management Routes."""

from __future__ import annotations

import logging
import secrets
import string
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.provider.routes import (  # noqa: F401
    provision_tenant_workspace,
    require_superadmin,
)
from app.db.session import get_db
from app.models.access_request import AccessRequest, AccessRequestStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.access_request import (
    AccessRequestList,
    AccessRequestResponse,
    AccessRequestStats,
    AccessRequestUpdate,
)

logger = logging.getLogger(__name__)


def _generate_temp_password(length: int = 12) -> str:
    """Readable temp password — mixed case + digits + 1 symbol."""
    alphabet = string.ascii_letters + string.digits
    body = "".join(secrets.choice(alphabet) for _ in range(length - 1))
    return body + secrets.choice("!@#$%&*")

router = APIRouter()


def _serialize(obj: AccessRequest) -> AccessRequestResponse:
    return AccessRequestResponse(
        id=str(obj.id),
        full_name=obj.full_name,
        email=obj.email,
        phone=obj.phone,
        company=obj.company,
        pump_count_range=obj.pump_count_range,
        city=obj.city,
        state=obj.state,
        message=obj.message,
        status=obj.status.value if hasattr(obj.status, "value") else str(obj.status),
        provider_notes=obj.provider_notes,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


@router.get(
    "/access-requests/stats",
    response_model=AccessRequestStats,
    summary="Counts of access requests by status",
)
async def access_request_stats(
    _user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> AccessRequestStats:
    rows = await db.execute(
        select(AccessRequest.status, func.count(AccessRequest.id)).group_by(
            AccessRequest.status
        )
    )
    counts = {s.value: 0 for s in AccessRequestStatus}
    total = 0
    for st, cnt in rows.all():
        key = st.value if hasattr(st, "value") else str(st)
        counts[key] = int(cnt)
        total += int(cnt)
    return AccessRequestStats(
        new=counts.get("NEW", 0),
        contacted=counts.get("CONTACTED", 0),
        approved=counts.get("APPROVED", 0),
        rejected=counts.get("REJECTED", 0),
        total=total,
    )


@router.get(
    "/access-requests",
    response_model=AccessRequestList,
    summary="List access requests (paginated)",
)
async def list_access_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> AccessRequestList:
    stmt = select(AccessRequest)
    count_stmt = select(func.count(AccessRequest.id))

    if status_filter:
        try:
            st_enum = AccessRequestStatus(status_filter.upper())
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status."
            ) from exc
        stmt = stmt.where(AccessRequest.status == st_enum)
        count_stmt = count_stmt.where(AccessRequest.status == st_enum)
    if search:
        like = f"%{search.lower()}%"
        cond = or_(
            func.lower(AccessRequest.email).like(like),
            func.lower(AccessRequest.full_name).like(like),
            func.lower(AccessRequest.company).like(like),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = (
        stmt.order_by(desc(AccessRequest.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return AccessRequestList(
        items=[_serialize(r) for r in rows],
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.get(
    "/access-requests/{request_id}",
    response_model=AccessRequestResponse,
    summary="Access request detail",
)
async def get_access_request(
    request_id: str,
    _user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> AccessRequestResponse:
    try:
        rid = uuid.UUID(request_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid id."
        ) from exc
    row = (
        await db.execute(select(AccessRequest).where(AccessRequest.id == rid))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    return _serialize(row)


@router.patch(
    "/access-requests/{request_id}",
    response_model=AccessRequestResponse,
    summary="Update status / notes for an access request",
)
async def update_access_request(
    request_id: str,
    payload: AccessRequestUpdate,
    _user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
) -> AccessRequestResponse:
    try:
        rid = uuid.UUID(request_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid id."
        ) from exc
    row = (
        await db.execute(select(AccessRequest).where(AccessRequest.id == rid))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")

    new_status: AccessRequestStatus | None = None
    if payload.status is not None:
        try:
            new_status = AccessRequestStatus(payload.status)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status."
            ) from exc
        row.status = new_status
    if payload.provider_notes is not None:
        row.provider_notes = payload.provider_notes.strip() or None

    # Transitioning to APPROVED = provision a full tenant workspace
    # (tenant + organization + first pump + owner user) and email the
    # credentials. Idempotent: if a tenant already exists for this email
    # we skip provisioning and just flip the status.
    if (
        new_status == AccessRequestStatus.APPROVED
        and row.email
    ):
        email = row.email.lower().strip()
        existing = (
            await db.execute(select(Tenant).where(Tenant.owner_email == email))
        ).scalar_one_or_none()
        if existing is None:
            # Commit the status change first so the row reflects intent
            # even if SMTP or provisioning fails partway through.
            await db.commit()
            temp_password = _generate_temp_password()
            try:
                await provision_tenant_workspace(
                    db,
                    tenant_name=row.company or row.full_name,
                    owner_name=row.full_name,
                    owner_email=email,
                    owner_phone=row.phone,
                    password=temp_password,
                    pump_code=None,  # auto-generate
                    subscription_plan="BASIC",
                    monthly_price_inr=0,
                )
            except HTTPException:
                # Already-exists race or similar — logged for the operator,
                # but the status change still sticks.
                logger.exception(
                    "Provisioning failed for approved access request %s", row.id
                )
            # Refetch the row (session was committed inside provision).
            row = (
                await db.execute(
                    select(AccessRequest).where(AccessRequest.id == rid)
                )
            ).scalar_one()
            return _serialize(row)

    await db.commit()
    await db.refresh(row)
    return _serialize(row)
