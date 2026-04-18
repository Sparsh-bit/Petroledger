"""PetroLedger — Schemas for Nozzle Assignments & Anomaly Flags."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.assignments import AnomalyFlagType, AnomalySeverity

# ═══════════════════════════════════════════════════════════════════════
#  NOZZLE ASSIGNMENTS
# ═══════════════════════════════════════════════════════════════════════


class NozzleAssignmentCreate(BaseModel):
    shift_id: UUID
    nozzle_id: UUID
    attendant_id: UUID
    assigned_at: datetime


class NozzleAssignmentRelieve(BaseModel):
    """Payload for relieving an active nozzle assignment."""
    relieved_at: datetime


class NozzleAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shift_id: UUID
    nozzle_id: UUID
    attendant_id: UUID
    assigned_at: datetime
    relieved_at: datetime | None
    assigned_by: UUID | None
    relieved_by: UUID | None
    created_at: datetime

    @property
    def is_active(self) -> bool:
        return self.relieved_at is None


# ═══════════════════════════════════════════════════════════════════════
#  ANOMALY FLAGS
# ═══════════════════════════════════════════════════════════════════════


class AnomalyFlagCreate(BaseModel):
    site_id: UUID
    shift_id: UUID | None = None
    attendant_id: UUID | None = None
    flag_type: AnomalyFlagType
    severity: AnomalySeverity
    description: str = Field(..., min_length=1)
    amount: Decimal | None = Field(None, ge=0)


class AnomalyFlagResolve(BaseModel):
    resolution_note: str = Field(..., min_length=1)


class AnomalyFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    site_id: UUID
    shift_id: UUID | None
    attendant_id: UUID | None
    flag_type: AnomalyFlagType
    severity: AnomalySeverity
    description: str
    amount: Decimal | None
    is_resolved: bool
    resolved_by: UUID | None
    resolved_at: datetime | None
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime
