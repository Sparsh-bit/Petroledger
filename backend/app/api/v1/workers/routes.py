"""PetroLedger — Worker CRUD Routes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.core.exceptions import AuthorizationError, DuplicateError, NotFoundError
from app.core.tenant import tenant_scope, verify_tenant_match
from app.db.session import get_db
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.user import User, UserRole
from app.models.worker import Worker
from app.schemas.worker import WorkerCreate, WorkerResponse, WorkerUpdate
from app.utils.pagination import PagedResponse, paginate

router = APIRouter()


class DeleteWorkerRequest(BaseModel):
    """Optional soft-delete payload."""
    reason: str | None = Field(default=None, max_length=500)


# ── POST / — Create Worker ───────────────────────────────────────────────────


@router.post(
    "/",
    response_model=WorkerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a worker profile",
)
async def create_worker(
    payload: WorkerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> WorkerResponse:
    """Assign a user as a worker at a specific pump within the same tenant."""
    # Verify pump's org belongs to the current user's tenant
    pump = await _get_pump_or_404(db, payload.pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)

    # Verify the target user belongs to the same tenant
    target_user = await _get_user_or_404(db, payload.user_id)
    if target_user.tenant_id != current_user.tenant_id:
        raise AuthorizationError("Cannot assign a worker from a different tenant")

    # Guard: each user can only have one active worker profile
    existing = await db.execute(
        select(Worker).where(
            Worker.user_id == payload.user_id,
            Worker.is_deleted == False,  # noqa: E712
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise DuplicateError("This user already has an active worker profile")

    worker = Worker(
        user_id=payload.user_id,
        pump_id=payload.pump_id,
        employee_code=payload.employee_code,
        joined_date=payload.joined_date,
    )
    db.add(worker)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise DuplicateError("Worker already exists — duplicate user or employee code")

    await db.refresh(worker)
    return WorkerResponse.model_validate(worker)


# ── GET / — List Workers ──────────────────────────────────────────────────────


@router.get(
    "/",
    response_model=PagedResponse[WorkerResponse],
    summary="List workers",
)
async def list_workers(
    pump_id: UUID | None = None,
    org_id: UUID | None = Query(None, description="Filter workers by organization"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PagedResponse[WorkerResponse]:
    """
    List workers within the current user's tenant.
    Optionally filter by pump_id or org_id. Managers/workers see only their org's workers.
    """
    # Join through Pump → Organization to apply tenant boundary
    stmt = (
        select(Worker)
        .join(Pump, Worker.pump_id == Pump.id)
        .join(Organization, Pump.org_id == Organization.id)
        .where(Worker.is_deleted == False)  # noqa: E712
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
        stmt = stmt.where(Worker.pump_id == pump_id)

    return await paginate(db, stmt, page, page_size, WorkerResponse)


# ── GET /{worker_id} — Get Worker ────────────────────────────────────────────


@router.get(
    "/{worker_id}",
    response_model=WorkerResponse,
    summary="Get worker by ID",
)
async def get_worker(
    worker_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> WorkerResponse:
    worker = await _get_worker_or_404(db, worker_id)
    pump = await _get_pump_or_404(db, worker.pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)
    return WorkerResponse.model_validate(worker)


# ── PATCH /{worker_id} — Update Worker ───────────────────────────────────────


@router.patch(
    "/{worker_id}",
    response_model=WorkerResponse,
    summary="Update a worker",
)
async def update_worker(
    worker_id: UUID,
    payload: WorkerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> WorkerResponse:
    """Update worker details like pump assignment or employee code."""
    worker = await _get_worker_or_404(db, worker_id)
    pump = await _get_pump_or_404(db, worker.pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)

    update_data = payload.model_dump(exclude_unset=True)

    # If reassigning to a different pump, verify new pump is also in the same tenant
    if "pump_id" in update_data:
        new_pump = await _get_pump_or_404(db, update_data["pump_id"])
        new_org = await _get_org_or_404(db, new_pump.org_id)
        verify_tenant_match(new_org.tenant_id, current_user)

    for field, value in update_data.items():
        setattr(worker, field, value)

    await db.flush()
    await db.refresh(worker)
    return WorkerResponse.model_validate(worker)


# ── DELETE /{worker_id} — Delete Worker ──────────────────────────────────────


@router.delete(
    "/{worker_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a worker profile",
)
async def delete_worker(
    worker_id: UUID,
    payload: DeleteWorkerRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> None:
    worker = await _get_worker_or_404(db, worker_id)
    pump = await _get_pump_or_404(db, worker.pump_id)
    org = await _get_org_or_404(db, pump.org_id)
    verify_tenant_match(org.tenant_id, current_user)
    from app.services.audit import AuditService

    worker.is_deleted = True
    worker.deleted_at = datetime.now(timezone.utc)
    worker.deleted_reason = payload.reason if payload else None
    await db.flush()
    await AuditService.log_event(
        db,
        user=current_user,
        action="worker.deleted",
        entity_type="Worker",
        entity_id=worker.id,
        org_id=pump.org_id,
        after={"deleted_reason": worker.deleted_reason},
    )
    await db.commit()


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_worker_or_404(db: AsyncSession, worker_id: UUID) -> Worker:
    result = await db.execute(
        select(Worker).where(Worker.id == worker_id, Worker.is_deleted == False)  # noqa: E712
    )
    worker = result.scalar_one_or_none()
    if worker is None:
        raise NotFoundError(resource="Worker", identifier=worker_id)
    return worker


async def _get_pump_or_404(db: AsyncSession, pump_id: UUID) -> Pump:
    result = await db.execute(
        select(Pump).where(Pump.id == pump_id, Pump.is_deleted == False)  # noqa: E712
    )
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


async def _get_user_or_404(db: AsyncSession, user_id: UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(resource="User", identifier=user_id)
    return user
