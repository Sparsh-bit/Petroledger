"""PetroLedger — Staff User Management Routes.

Owner/Admin-invoked user creation within a tenant. The role-creation matrix
is enforced in :class:`app.services.auth.AuthService`:

    owner  -> admin, manager, worker
    admin  -> manager, worker
    manager/worker -> forbidden (403)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserResponse
from app.services.auth import AuthService

router = APIRouter()


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)
    role: UserRole
    org_id: uuid.UUID | None = None


class UserListItem(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    is_active: bool
    org_id: uuid.UUID | None
    last_login: datetime | None
    created_at: datetime


class PagedUsers(BaseModel):
    items: list[UserListItem]
    total: int
    page: int
    page_size: int


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a staff user within the current tenant",
)
async def create_user(
    payload: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """Create a staff user. Only owner/admin actors are permitted.

    The created user inherits ``tenant_id`` from the actor; passing
    ``org_id`` binds the user to a specific organisation.
    """
    if current_user.role not in (UserRole.OWNER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins may create staff users.",
        )

    service = AuthService(db)
    user = await service.create_staff_user(
        actor=current_user,
        email=str(payload.email),
        password=payload.password,
        role=payload.role,
        org_id=payload.org_id,
    )
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.get(
    "/",
    response_model=PagedUsers,
    summary="List staff users in the current tenant",
)
async def list_users(
    role: UserRole | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PagedUsers:
    """List users within the current actor's tenant."""
    if current_user.role not in (UserRole.OWNER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins may list users.",
        )

    page = max(1, page)
    page_size = max(1, min(200, page_size))

    stmt = select(User).where(User.tenant_id == current_user.tenant_id)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(func.lower(User.email).like(like))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one() or 0

    stmt = (
        stmt.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        UserListItem(
            id=u.id,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            org_id=u.org_id,
            last_login=u.last_login,
            created_at=u.created_at,
        )
        for u in rows
    ]
    return PagedUsers(items=items, total=int(total), page=page, page_size=page_size)


@router.patch(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Deactivate a user in the current tenant",
)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    if current_user.role not in (UserRole.OWNER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins may deactivate users.",
        )
    user = (
        await db.execute(
            select(User).where(
                User.id == user_id,
                User.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_user.id:
        raise HTTPException(
            status_code=400, detail="You cannot deactivate your own account."
        )
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}/reactivate",
    response_model=UserResponse,
    summary="Reactivate a user in the current tenant",
)
async def reactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    if current_user.role not in (UserRole.OWNER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins may reactivate users.",
        )
    user = (
        await db.execute(
            select(User).where(
                User.id == user_id,
                User.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)
