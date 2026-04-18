"""PetroLedger — Pump & Nozzle Schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.pump import FuelType

# ── Nozzle Schemas ──────────────────────────────────────────────────────


class NozzleCreate(BaseModel):
    nozzle_number: int = Field(..., ge=1)
    fuel_type: FuelType


class NozzleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pump_id: UUID
    nozzle_number: int
    fuel_type: FuelType
    created_at: datetime
    updated_at: datetime


# ── Pump Schemas ────────────────────────────────────────────────────────


class PumpCreate(BaseModel):
    org_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    location: str | None = None
    nozzle_count: int = Field(default=0, ge=0)
    nozzles: list[NozzleCreate] = Field(default_factory=list)


class PumpUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    location: str | None = None
    nozzle_count: int | None = Field(None, ge=0)
    is_active: bool | None = None


class PumpResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    location: str | None = None
    nozzle_count: int
    is_active: bool
    nozzles: list[NozzleResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
