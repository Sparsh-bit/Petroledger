"""PetroLedger — Nozzle Assignment Routes.

POST   /nozzle-assignments/                  — assign attendant to nozzle
GET    /nozzle-assignments/?shift_id=...     — list all assignments for shift
GET    /nozzle-assignments/{id}              — get single assignment
PATCH  /nozzle-assignments/{id}/relieve      — relieve an active assignment
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.core.exceptions import NotFoundError, ValidationError
from app.core.tenant import tenant_scope, verify_tenant_match
from app.db.session import get_db
from app.models.assignments import NozzleAssignment
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.shift import Shift
from app.models.user import User, UserRole
from app.schemas.assignments import (
    NozzleAssignmentCreate,
    NozzleAssignmentRelieve,
    NozzleAssignmentResponse,
)

router = APIRouter()


@router.get(
    "/my-active",
    summary="List currently-assigned active nozzles for the authenticated worker",
)
async def list_my_active_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[dict]:
    """Return active nozzle assignments for the authenticated worker.

    "Active" means ``relieved_at IS NULL`` and the parent shift is still
    ACTIVE. Each entry includes the nozzle's human-readable metadata so the
    UI can render a select without a second round-trip.
    """
    from app.models.pump import Nozzle
    from app.models.worker import Worker

    worker_row = (
        await db.execute(select(Worker).where(Worker.user_id == current_user.id))
    ).scalar_one_or_none()
    if worker_row is None:
        return []

    stmt = (
        select(NozzleAssignment, Nozzle, Shift)
        .join(Nozzle, NozzleAssignment.nozzle_id == Nozzle.id)
        .join(Shift, NozzleAssignment.shift_id == Shift.id)
        .where(
            NozzleAssignment.attendant_id == worker_row.id,
            NozzleAssignment.relieved_at.is_(None),
            Shift.status == "ACTIVE",
        )
        .order_by(NozzleAssignment.assigned_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "assignment_id": str(a.id),
            "shift_id": str(s.id),
            "nozzle_id": str(n.id),
            "nozzle_number": n.nozzle_number,
            "fuel_type": n.fuel_type.value if hasattr(n.fuel_type, "value") else n.fuel_type,
            "product_name": n.product_name,
            "assigned_at": a.assigned_at.isoformat(),
        }
        for a, n, s in rows
    ]


@router.post(
    "/",
    response_model=NozzleAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign attendant to nozzle",
)
async def create_nozzle_assignment(
    payload: NozzleAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> NozzleAssignmentResponse:
    """Assign an attendant to a nozzle for a shift.

    The database enforces that only one active assignment exists per
    ``(shift_id, nozzle_id)`` at a time via a PostgreSQL partial unique
    index.  Creating a duplicate active assignment will raise a 409.
    """
    await _verify_shift_tenant_access(payload.shift_id, current_user, db)

    row = NozzleAssignment(
        shift_id=payload.shift_id,
        nozzle_id=payload.nozzle_id,
        attendant_id=payload.attendant_id,
        assigned_at=payload.assigned_at,
        assigned_by=current_user.id,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return NozzleAssignmentResponse.model_validate(row)


@router.get(
    "/",
    response_model=list[NozzleAssignmentResponse],
    summary="List nozzle assignments for a shift",
)
async def list_nozzle_assignments(
    shift_id: UUID = Query(..., description="Filter by shift ID"),
    active_only: bool = Query(False, description="Return only active (unrelieved) assignments"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[NozzleAssignmentResponse]:
    stmt = (
        select(NozzleAssignment)
        .join(Shift, NozzleAssignment.shift_id == Shift.id)
        .join(Pump, Shift.pump_id == Pump.id)
        .join(Organization, Pump.org_id == Organization.id)
        .where(NozzleAssignment.shift_id == shift_id)
    )
    stmt = tenant_scope(stmt, Organization, current_user)
    if active_only:
        stmt = stmt.where(NozzleAssignment.relieved_at.is_(None))
    stmt = stmt.order_by(NozzleAssignment.assigned_at)
    rows = (await db.execute(stmt)).scalars().all()
    return [NozzleAssignmentResponse.model_validate(r) for r in rows]


@router.get(
    "/{assignment_id}",
    response_model=NozzleAssignmentResponse,
    summary="Get nozzle assignment by ID",
)
async def get_nozzle_assignment(
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NozzleAssignmentResponse:
    row = await _get_or_404(db, assignment_id)
    await _verify_shift_tenant_access(row.shift_id, current_user, db)
    return NozzleAssignmentResponse.model_validate(row)


@router.patch(
    "/{assignment_id}/relieve",
    response_model=NozzleAssignmentResponse,
    summary="Relieve an active nozzle assignment",
)
async def relieve_nozzle_assignment(
    assignment_id: UUID,
    payload: NozzleAssignmentRelieve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> NozzleAssignmentResponse:
    """Set ``relieved_at`` on an active assignment to close it.

    Raises **422** if the assignment is already relieved.
    """
    row = await _get_or_404(db, assignment_id)
    await _verify_shift_tenant_access(row.shift_id, current_user, db)

    if row.relieved_at is not None:
        raise ValidationError("Assignment is already relieved.")
    row.relieved_at = payload.relieved_at
    row.relieved_by = current_user.id
    await db.flush()
    await db.refresh(row)
    return NozzleAssignmentResponse.model_validate(row)


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _verify_shift_tenant_access(
    shift_id: UUID, current_user: User, db: AsyncSession
) -> Shift:
    """Resolve shift → pump → org and verify the org belongs to the user's tenant."""
    shift_row = (
        await db.execute(select(Shift).where(Shift.id == shift_id))
    ).scalar_one_or_none()
    if shift_row is None:
        raise NotFoundError(resource="Shift", identifier=shift_id)

    pump_row = (
        await db.execute(select(Pump).where(Pump.id == shift_row.pump_id))
    ).scalar_one_or_none()
    if pump_row is None:
        raise NotFoundError(resource="Pump", identifier=shift_row.pump_id)

    org_row = (
        await db.execute(select(Organization).where(Organization.id == pump_row.org_id))
    ).scalar_one_or_none()
    if org_row is None:
        raise NotFoundError(resource="Organization", identifier=pump_row.org_id)

    verify_tenant_match(org_row.tenant_id, current_user)
    return shift_row


async def _get_or_404(db: AsyncSession, assignment_id: UUID) -> NozzleAssignment:
    row = (
        await db.execute(
            select(NozzleAssignment).where(NozzleAssignment.id == assignment_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(resource="NozzleAssignment", identifier=assignment_id)
    return row
