"""PetroLedger — Audit Log query routes.

Read-only access to the immutable audit trail. Restricted to OWNER and
superadmin. Filtering: org_id, entity_type, action, user_id, and
created_at range. Results paginated via the shared `paginate()` helper.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rbac import require_role
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.utils.pagination import PagedResponse, paginate

router = APIRouter()


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action: str
    entity_type: str
    entity_id: UUID
    user_id: UUID
    org_id: UUID
    tenant_id: UUID
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    metadata_: dict[str, Any] | None = None
    ip_address: str | None = None
    created_at: datetime


@router.get(
    "/",
    response_model=PagedResponse[AuditLogResponse],
    summary="List audit-log entries (owner + superadmin only)",
)
async def list_audit_logs(
    org_id: UUID | None = Query(None),
    entity_type: str | None = Query(None),
    action: str | None = Query(None),
    user_id: UUID | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> PagedResponse[AuditLogResponse]:
    """Return audit-log rows for the current tenant, newest-first.

    Hard-scoped to `current_user.tenant_id` — owners/admins cannot escape their tenant.
    """
    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == current_user.tenant_id)
        .order_by(AuditLog.created_at.desc())
    )

    if org_id is not None:
        stmt = stmt.where(AuditLog.org_id == org_id)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if start_date is not None:
        stmt = stmt.where(AuditLog.created_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(AuditLog.created_at <= end_date)

    return await paginate(db, stmt, page, page_size, AuditLogResponse)
