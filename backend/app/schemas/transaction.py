"""PetroLedger — Transaction Pydantic Schemas (UPI, POS, PumpLog)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UPITransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shift_id: UUID
    amount: Decimal
    upi_ref: str
    bank: str | None
    timestamp: datetime
    payer_upi: str | None
    match_status: str | None
    created_at: datetime
