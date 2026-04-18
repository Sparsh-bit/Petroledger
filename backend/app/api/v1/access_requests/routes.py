"""PetroLedger — Public Access Request Routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.access_request import AccessRequest, AccessRequestStatus
from app.schemas.access_request import (
    AccessRequestCreate,
    AccessRequestSubmitResponse,
)

router = APIRouter()


@router.post(
    "",
    response_model=AccessRequestSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a public access request for the ERP",
)
@limiter.limit("5/hour")
async def submit_access_request(
    request: Request,
    payload: AccessRequestCreate,
    db: AsyncSession = Depends(get_db),
) -> AccessRequestSubmitResponse:
    obj = AccessRequest(
        id=uuid.uuid4(),
        full_name=payload.full_name.strip(),
        email=str(payload.email).lower().strip(),
        phone=payload.phone,
        company=payload.company.strip(),
        pump_count_range=payload.pump_count_range,
        city=payload.city.strip(),
        state=payload.state.strip(),
        message=(payload.message or "").strip() or None,
        status=AccessRequestStatus.NEW,
        ip_address=(request.client.host if request.client else None),
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return AccessRequestSubmitResponse(
        id=str(obj.id),
        status=obj.status.value,
        message="Request received",
    )
