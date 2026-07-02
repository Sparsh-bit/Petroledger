"""PetroLedger — Worker Schemas."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── Request Schemas ─────────────────────────────────────────────────────


class WorkerCreate(BaseModel):
    user_id: UUID
    pump_id: UUID
    employee_code: str = Field(..., min_length=1, max_length=50)
    joined_date: date


class WorkerUpdate(BaseModel):
    pump_id: UUID | None = None
    employee_code: str | None = Field(None, min_length=1, max_length=50)
    full_name: str | None = Field(None, max_length=150)
    is_active: bool | None = None


# ── Response Schemas ────────────────────────────────────────────────────


class WorkerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    pump_id: UUID
    employee_code: str
    full_name: str | None = None
    joined_date: date
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
