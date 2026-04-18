"""PetroLedger — Schemas for FMS transactions, POS settlements, Fleet, Cash."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.fms import (
    FleetEntryMethod,
    FleetProvider,
    FmsTransactionSubtype,
    FmsTxnStatus,
    PosEntryMethod,
)

# ═══════════════════════════════════════════════════════════════════════
#  FMS TRANSACTIONS
# ═══════════════════════════════════════════════════════════════════════


class FmsTransactionCreate(BaseModel):
    shift_id: UUID
    nozzle_id: UUID
    txn_reference: str = Field(..., max_length=100)
    txn_date: date
    txn_time: time
    volume_litres: Decimal = Field(..., gt=0, decimal_places=3)
    unit_price: Decimal = Field(..., gt=0)
    amount: Decimal = Field(..., gt=0)
    product_code: str | None = Field(None, max_length=10)
    raw_payment_mode: str | None = Field(None, max_length=50)
    status: FmsTxnStatus = FmsTxnStatus.COMPLETED
    subtype: FmsTransactionSubtype = FmsTransactionSubtype.SALE


class FmsTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shift_id: UUID
    nozzle_id: UUID
    txn_reference: str
    txn_date: date
    txn_time: time
    volume_litres: Decimal = Field(..., examples=["45.250"])
    unit_price: Decimal = Field(..., examples=["102.50"])
    amount: Decimal = Field(..., examples=["4638.25"])
    product_code: str | None
    raw_payment_mode: str | None
    status: FmsTxnStatus
    subtype: FmsTransactionSubtype
    is_deleted: bool
    created_at: datetime


class FmsTransactionSoftDelete(BaseModel):
    deleted_reason: str = Field(..., min_length=1)


# ═══════════════════════════════════════════════════════════════════════
#  POS BATCH SETTLEMENTS
# ═══════════════════════════════════════════════════════════════════════


class PosBatchSettlementCreate(BaseModel):
    shift_id: UUID
    terminal_id: str = Field(..., max_length=100)
    batch_number: str | None = Field(None, max_length=50)
    gross_amount: Decimal = Field(..., ge=0)
    visa_amount: Decimal | None = Field(None, ge=0)
    mastercard_amount: Decimal | None = Field(None, ge=0)
    rupay_amount: Decimal | None = Field(None, ge=0)
    amex_amount: Decimal | None = Field(None, ge=0)
    total_transactions: int | None = Field(None, ge=0)
    settlement_date: date | None = None
    entry_method: PosEntryMethod = PosEntryMethod.MANUAL


class PosBatchSettlementUpdate(BaseModel):
    """Partial update — all fields optional."""
    gross_amount: Decimal | None = Field(None, ge=0)
    visa_amount: Decimal | None = Field(None, ge=0)
    mastercard_amount: Decimal | None = Field(None, ge=0)
    rupay_amount: Decimal | None = Field(None, ge=0)
    amex_amount: Decimal | None = Field(None, ge=0)
    total_transactions: int | None = Field(None, ge=0)
    settlement_date: date | None = None
    batch_number: str | None = Field(None, max_length=50)


class PosBatchSettlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shift_id: UUID
    terminal_id: str
    batch_number: str | None
    gross_amount: Decimal = Field(..., examples=["5000.00"])
    visa_amount: Decimal | None = Field(None, examples=["2000.00"])
    mastercard_amount: Decimal | None = Field(None, examples=["1500.00"])
    rupay_amount: Decimal | None = Field(None, examples=["1500.00"])
    amex_amount: Decimal | None = Field(None, examples=["0.00"])
    total_transactions: int | None
    settlement_date: date | None
    entry_method: PosEntryMethod
    is_deleted: bool
    created_at: datetime


class PosBatchSettlementSoftDelete(BaseModel):
    deleted_reason: str = Field(..., min_length=1)


# ═══════════════════════════════════════════════════════════════════════
#  FLEET TRANSACTIONS
# ═══════════════════════════════════════════════════════════════════════


class FleetTransactionCreate(BaseModel):
    shift_id: UUID
    fleet_provider: FleetProvider
    total_transactions: int | None = Field(None, ge=0)
    total_amount: Decimal = Field(..., ge=0)
    entry_method: FleetEntryMethod = FleetEntryMethod.MANUAL
    notes: str | None = None


class FleetTransactionUpdate(BaseModel):
    total_transactions: int | None = Field(None, ge=0)
    total_amount: Decimal | None = Field(None, ge=0)
    notes: str | None = None


class FleetTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shift_id: UUID
    fleet_provider: FleetProvider
    total_transactions: int | None
    total_amount: Decimal = Field(..., examples=["3000.00"])
    entry_method: FleetEntryMethod
    notes: str | None
    is_deleted: bool
    created_at: datetime


class FleetTransactionSoftDelete(BaseModel):
    deleted_reason: str = Field(..., min_length=1)


# ═══════════════════════════════════════════════════════════════════════
#  CASH ENTRIES
# ═══════════════════════════════════════════════════════════════════════


class CashEntryCreate(BaseModel):
    shift_id: UUID
    attendant_id: UUID | None = None
    nozzle_id: UUID | None = None
    physical_cash: Decimal = Field(..., ge=0)
    denomination_2000: int | None = Field(None, ge=0)
    denomination_500: int | None = Field(None, ge=0)
    denomination_200: int | None = Field(None, ge=0)
    denomination_100: int | None = Field(None, ge=0)
    denomination_50: int | None = Field(None, ge=0)
    denomination_20: int | None = Field(None, ge=0)
    denomination_10: int | None = Field(None, ge=0)
    coins: Decimal | None = Field(None, ge=0)


class CashEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shift_id: UUID
    attendant_id: UUID | None
    nozzle_id: UUID | None
    physical_cash: Decimal = Field(..., examples=["11000.00"])
    denomination_2000: int | None
    denomination_500: int | None
    denomination_200: int | None
    denomination_100: int | None
    denomination_50: int | None
    denomination_20: int | None
    denomination_10: int | None
    coins: Decimal | None = Field(None, examples=["50.00"])
    submitted_by: UUID | None
    submitted_at: datetime | None
    is_locked: bool
    is_deleted: bool
    created_at: datetime


class CashEntrySoftDelete(BaseModel):
    deleted_reason: str = Field(..., min_length=1)
