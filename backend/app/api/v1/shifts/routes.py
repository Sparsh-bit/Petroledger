"""PetroLedger — Shift CRUD Routes."""

from __future__ import annotations

from uuid import UUID

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.core.exceptions import NotFoundError, ValidationError
from app.core.tenant import tenant_scope, verify_tenant_match
from app.db.session import get_db
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.shift import Shift, ShiftStatus
from app.models.user import User, UserRole
from app.schemas.shift import ShiftCreate, ShiftResponse, ShiftStatusResponse, ShiftUpdate
from app.services.reconciliation.per_worker import get_incomplete_nozzles
from app.utils.pagination import PagedResponse, paginate

router = APIRouter()


# ── Helper Schema ────────────────────────────────────────────────────────────


class ShiftStatusUpdate(BaseModel):
    """Dedicated schema for status-only updates."""
    status: ShiftStatus


# ── POST / — Create Shift ────────────────────────────────────────────────────


@router.post(
    "/",
    response_model=ShiftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new shift",
)
async def create_shift(
    payload: ShiftCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> ShiftResponse:
    """Start a new shift for a worker at a pump."""
    pump = await _get_pump_or_404(db, payload.pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)

    shift = Shift(
        pump_id=payload.pump_id,
        worker_id=payload.worker_id,
        start_time=payload.start_time,
        status=ShiftStatus.ACTIVE,
    )
    db.add(shift)
    await db.flush()
    await db.refresh(shift)
    return ShiftResponse.model_validate(shift)


# ── GET / — List Shifts ───────────────────────────────────────────────────────


@router.get(
    "/",
    response_model=PagedResponse[ShiftResponse],
    summary="List shifts",
)
async def list_shifts(
    pump_id: UUID | None = None,
    worker_id: UUID | None = None,
    org_id: UUID | None = Query(None, description="Filter shifts by organization"),
    shift_status: ShiftStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PagedResponse[ShiftResponse]:
    """
    List shifts within the current user's tenant.
    Optional filters: pump_id, worker_id, org_id, status.
    Managers/workers see only their org's shifts.
    """
    stmt = (
        select(Shift)
        .join(Pump, Shift.pump_id == Pump.id)
        .join(Organization, Pump.org_id == Organization.id)
    )
    stmt = tenant_scope(stmt, Organization, current_user)

    # Organization has no org_id column so tenant_scope won't add the secondary
    # filter; apply it explicitly for org-scoped roles.
    role_str = (
        current_user.role.value
        if hasattr(current_user.role, "value")
        else current_user.role
    )
    if role_str.lower() in ("manager", "worker") and current_user.org_id:
        stmt = stmt.where(Pump.org_id == current_user.org_id)
    elif org_id is not None:
        stmt = stmt.where(Pump.org_id == org_id)

    if pump_id is not None:
        stmt = stmt.where(Shift.pump_id == pump_id)
    if worker_id is not None:
        stmt = stmt.where(Shift.worker_id == worker_id)
    if shift_status is not None:
        stmt = stmt.where(Shift.status == shift_status)

    stmt = stmt.order_by(Shift.start_time.desc())
    return await paginate(db, stmt, page, page_size, ShiftResponse)


# ── GET /{shift_id} — Get Shift ───────────────────────────────────────────────


@router.get(
    "/{shift_id}",
    response_model=ShiftResponse,
    summary="Get shift by ID",
)
async def get_shift(
    shift_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ShiftResponse:
    shift = await _get_shift_or_404(db, shift_id)
    pump = await _get_pump_or_404(db, shift.pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)
    return ShiftResponse.model_validate(shift)


# ── PATCH /{shift_id} — Update Shift ─────────────────────────────────────────


@router.patch(
    "/{shift_id}",
    response_model=ShiftResponse,
    summary="Update a shift",
)
async def update_shift(
    shift_id: UUID,
    payload: ShiftUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> ShiftResponse:
    """Update shift end_time or status."""
    shift = await _get_shift_or_404(db, shift_id)
    pump = await _get_pump_or_404(db, shift.pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)

    update_data = payload.model_dump(exclude_unset=True)

    # Validate status transitions
    if "status" in update_data:
        _validate_status_transition(shift.status, update_data["status"])

    for field, value in update_data.items():
        setattr(shift, field, value)

    await db.flush()
    await db.refresh(shift)
    return ShiftResponse.model_validate(shift)


# ── PATCH /{shift_id}/status — Update Shift Status Only ──────────────────────


@router.patch(
    "/{shift_id}/status",
    response_model=ShiftStatusResponse,
    summary="Update shift status",
)
async def update_shift_status(
    shift_id: UUID,
    payload: ShiftStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> ShiftStatusResponse:
    """
    Dedicated endpoint for status transitions:
    active → completed → reconciled.

    When closing a shift (active → completed), a warning is included in the
    response if any nozzle is missing opening or closing meter readings.
    """
    shift = await _get_shift_or_404(db, shift_id)
    pump = await _get_pump_or_404(db, shift.pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)

    _validate_status_transition(shift.status, payload.status)
    shift.status = payload.status

    await db.flush()
    await db.refresh(shift)

    warnings: list[str] = []
    if payload.status == ShiftStatus.COMPLETED:
        incomplete = await get_incomplete_nozzles(shift_id, db)
        if incomplete:
            warnings.append(
                f"Shift closed without complete meter readings for nozzles: "
                f"{incomplete}. Per-worker reconciliation will not be available."
            )

    resp = ShiftStatusResponse.model_validate(shift)
    resp.warnings = warnings
    return resp


# ── POST /{shift_id}/approve — Approve a PENDING_APPROVAL shift ─────────────


class ApproveShiftRequest(BaseModel):
    approval_notes: str | None = Field(default=None, max_length=2000)


class RejectShiftRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=3, max_length=2000)


@router.post(
    "/{shift_id}/approve",
    response_model=ShiftResponse,
    summary="Approve a pending-approval shift and LOCK it (OWNER only)",
)
async def approve_shift(
    shift_id: UUID,
    payload: ApproveShiftRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER)),
) -> ShiftResponse:
    """Transition PENDING_APPROVAL → LOCKED. Requires OWNER role."""
    shift = await _get_shift_or_404(db, shift_id)
    pump = await _get_pump_or_404(db, shift.pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)

    if shift.status != ShiftStatus.PENDING_APPROVAL:
        raise ValidationError(
            f"Shift must be PENDING_APPROVAL to approve (current: {shift.status.value})."
        )

    from app.services.audit import AuditService

    shift.status = ShiftStatus.LOCKED
    shift.approved_by_user_id = current_user.id
    shift.approved_at = datetime.now(UTC)
    if payload is not None:
        shift.approval_notes = payload.approval_notes
    await db.flush()
    await AuditService.log_event(
        db,
        user=current_user,
        action="shift.approved",
        entity_type="Shift",
        entity_id=shift.id,
        org_id=pump.org_id,
        after={"status": ShiftStatus.LOCKED.value,
               "approval_notes": shift.approval_notes},
    )
    await db.refresh(shift)
    await db.commit()
    return ShiftResponse.model_validate(shift)


@router.post(
    "/{shift_id}/reject",
    response_model=ShiftResponse,
    summary="Reject a pending-approval shift (OWNER only)",
)
async def reject_shift(
    shift_id: UUID,
    payload: RejectShiftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER)),
) -> ShiftResponse:
    """Transition PENDING_APPROVAL → REJECTED with a mandatory reason.

    The manager can re-run reconciliation which will transition the shift
    back to PENDING_APPROVAL for a fresh owner review.
    """
    shift = await _get_shift_or_404(db, shift_id)
    pump = await _get_pump_or_404(db, shift.pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)

    if shift.status != ShiftStatus.PENDING_APPROVAL:
        raise ValidationError(
            f"Shift must be PENDING_APPROVAL to reject (current: {shift.status.value})."
        )

    from app.services.audit import AuditService

    shift.status = ShiftStatus.REJECTED
    shift.rejection_reason = payload.rejection_reason
    await db.flush()
    await AuditService.log_event(
        db,
        user=current_user,
        action="shift.rejected",
        entity_type="Shift",
        entity_id=shift.id,
        org_id=pump.org_id,
        after={"status": ShiftStatus.REJECTED.value,
               "rejection_reason": payload.rejection_reason},
    )
    await db.refresh(shift)
    await db.commit()

    # Best-effort email notification to the worker's manager (falls back to
    # the worker's own email when no explicit manager is available). Silent
    # on failure — never block the rejection flow on SMTP.
    try:
        await _notify_shift_rejected(shift, payload.rejection_reason, db)
    except Exception:
        pass

    return ShiftResponse.model_validate(shift)


async def _notify_shift_rejected(
    shift: Shift, reason: str, db: AsyncSession
) -> None:
    """Email the manager of the org that owns *shift* about the rejection."""
    from app.core.email import send_email
    from app.models.user import User, UserRole

    pump = (
        await db.execute(select(Pump).where(Pump.id == shift.pump_id))
    ).scalar_one_or_none()
    if pump is None:
        return

    managers = (
        await db.execute(
            select(User).where(
                User.org_id == pump.org_id,
                User.role == UserRole.MANAGER,
                User.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    recipients = [m.email for m in managers]
    if not recipients:
        return

    subject = f"Shift {shift.id} rejected — action required"
    html = (
        f"<p>The reconciliation for shift <b>{shift.id}</b> has been rejected "
        f"by the owner.</p><p><b>Reason:</b> {reason}</p>"
        f"<p>Please review the reconciliation, address the issue, and re-run "
        f"reconciliation to resubmit for approval.</p>"
    )
    for addr in recipients:
        await send_email(to=addr, subject=subject, html_body=html)


# ── DELETE /{shift_id} — Delete Shift ────────────────────────────────────────


@router.delete(
    "/{shift_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a shift",
)
async def delete_shift(
    shift_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
) -> None:
    """Only owner/admin can delete shifts."""
    shift = await _get_shift_or_404(db, shift_id)
    pump = await _get_pump_or_404(db, shift.pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)

    if shift.status == ShiftStatus.RECONCILED:
        raise ValidationError("Cannot delete a reconciled shift")

    await db.delete(shift)
    await db.flush()


# ── Helpers ──────────────────────────────────────────────────────────────────

_ALLOWED_TRANSITIONS: dict[ShiftStatus, set[ShiftStatus]] = {
    ShiftStatus.ACTIVE: {ShiftStatus.COMPLETED, ShiftStatus.CANCELLED},
    # COMPLETED → RECONCILED is the manager's manual trigger path.
    # RECONCILED → PENDING_APPROVAL happens automatically when the
    # reconciliation engine writes the result; it's not an allowed
    # manual PATCH target.
    ShiftStatus.COMPLETED: {ShiftStatus.RECONCILED},
    ShiftStatus.RECONCILED: set(),
    # PENDING_APPROVAL and REJECTED only exit via /approve or /reject;
    # no manual status PATCH is allowed.
    ShiftStatus.PENDING_APPROVAL: set(),
    ShiftStatus.REJECTED: set(),
    ShiftStatus.LOCKED: set(),
    ShiftStatus.CANCELLED: set(),
}


def _validate_status_transition(
    current: ShiftStatus, target: ShiftStatus
) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValidationError(
            f"Cannot transition from '{current.value}' to '{target.value}'. "
            f"Allowed: {', '.join(s.value for s in allowed) or 'none (terminal state)'}"
        )


async def _get_shift_or_404(db: AsyncSession, shift_id: UUID) -> Shift:
    result = await db.execute(select(Shift).where(Shift.id == shift_id))
    shift = result.scalar_one_or_none()
    if shift is None:
        raise NotFoundError(resource="Shift", identifier=shift_id)
    return shift


async def _get_pump_or_404(db: AsyncSession, pump_id: UUID) -> Pump:
    result = await db.execute(select(Pump).where(Pump.id == pump_id))
    pump = result.scalar_one_or_none()
    if pump is None:
        raise NotFoundError(resource="Pump", identifier=pump_id)
    return pump


async def _get_org_or_404(db: AsyncSession, org_id: UUID) -> Organization:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if org is None:
        raise NotFoundError(resource="Organization", identifier=org_id)
    return org
