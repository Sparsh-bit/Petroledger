"""PetroLedger — Shift Schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.shift import ShiftStatus

# ── Request Schemas ─────────────────────────────────────────────────────


class ShiftCreate(BaseModel):
    pump_id: UUID
    worker_id: UUID
    start_time: datetime


class ShiftUpdate(BaseModel):
    end_time: datetime | None = None
    status: ShiftStatus | None = None


# ── Response Schemas ────────────────────────────────────────────────────


class ShiftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pump_id: UUID
    worker_id: UUID
    start_time: datetime
    end_time: datetime | None = None
    status: ShiftStatus
    approval_notes: str | None = None
    approved_by_user_id: UUID | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class ShiftStatusResponse(ShiftResponse):
    """Extended response for status transitions — includes operational warnings."""

    warnings: list[str] = []
