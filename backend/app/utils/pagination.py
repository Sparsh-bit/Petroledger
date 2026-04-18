"""
PetroLedger — Pagination Utilities.

Provides a reusable PagedResponse schema and a paginate() helper that
wraps any SQLAlchemy SELECT statement with LIMIT/OFFSET and a COUNT query.

Usage in a route::

    from app.utils.pagination import PagedResponse, paginate

    @router.get("/", response_model=PagedResponse[FmsTransactionResponse])
    async def list_transactions(
        shift_id: UUID = Query(...),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
    ):
        stmt = select(FmsTransaction).where(FmsTransaction.shift_id == shift_id)
        return await paginate(db, stmt, page, page_size, FmsTransactionResponse)
"""

from __future__ import annotations

from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

T = TypeVar("T")


class PagedResponse(BaseModel, Generic[T]):
    """Standard paginated response envelope."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


async def paginate(
    db: AsyncSession,
    stmt: Select,
    page: int,
    page_size: int,
    response_schema: type[T],
) -> PagedResponse[T]:
    """Execute *stmt* with pagination and return a :class:`PagedResponse`.

    Parameters
    ----------
    db:
        Async database session.
    stmt:
        Base SELECT statement (no LIMIT/OFFSET applied yet).
    page:
        1-based page number.
    page_size:
        Number of rows per page (capped at 100).
    response_schema:
        Pydantic schema class to validate each row via ``model_validate``.
    """
    page_size = min(page_size, 100)
    offset = (page - 1) * page_size

    # COUNT query — wrap the base stmt as a subquery
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    # Data query — apply limit + offset
    data_stmt = stmt.limit(page_size).offset(offset)
    rows = (await db.execute(data_stmt)).scalars().all()

    return PagedResponse(
        data=[response_schema.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=ceil(total / page_size) if total > 0 else 1,
    )
