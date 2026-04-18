"""PetroLedger — Meter Reading Schemas."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────────────────


class NozzleReadingInput(BaseModel):
    """One nozzle's ETOT meter values as entered manually or parsed from OCR."""

    nozzle_number: int = Field(..., ge=1, le=20)
    amount_cumulative: Decimal = Field(
        ..., gt=0, description="Cumulative lifetime amount dispensed in ₹"
    )
    volume_cumulative: Decimal = Field(
        ..., gt=0, description="Cumulative lifetime volume dispensed in litres"
    )
    tot_sales_cumulative: int = Field(
        ..., gt=0, description="Cumulative lifetime transaction count"
    )


class MeterReadingManualRequest(BaseModel):
    """JSON body for manual meter reading entry."""

    reading_type: Literal["opening", "closing"]
    nozzle_readings: list[NozzleReadingInput]


# ── Response Schemas ─────────────────────────────────────────────────────────


class NozzleReadingResult(BaseModel):
    """Result for a single nozzle after a reading upload/entry."""

    nozzle_number: int
    nozzle_id: UUID
    worker_id: UUID
    worker_name: str
    amount_cumulative: Decimal
    volume_cumulative: Decimal
    tot_sales_cumulative: int
    shift_sale_computed: bool
    shift_sale_amount: Decimal | None = None
    warnings: list[str] = []


class MeterReadingUploadResponse(BaseModel):
    """Top-level response for upload and manual entry endpoints."""

    shift_id: UUID
    reading_type: str
    processed_nozzles: list[NozzleReadingResult]
    ocr_used: bool
    warnings: list[str] = []


class NozzleShiftSaleDetail(BaseModel):
    """Shift sale breakdown for one nozzle."""

    nozzle_number: int
    nozzle_id: UUID
    worker_id: UUID
    worker_name: str
    shift_sale_amount: Decimal
    shift_sale_volume: Decimal
    shift_transaction_count: int
    is_verified: bool


class ShiftMeterSummary(BaseModel):
    """All meter readings and computed sales for a shift."""

    shift_id: UUID
    total_shift_sale: Decimal
    nozzles: list[NozzleShiftSaleDetail]
    readings_complete: bool
    missing_nozzles: list[int] = []


class WorkerReconciliationResult(BaseModel):
    """Per-nozzle/worker reconciliation result."""

    nozzle_id: UUID
    nozzle_number: int
    worker_id: UUID
    worker_name: str
    shift_sale_amount: Decimal
    upi_received: Decimal
    card_settled: Decimal
    fleet_card: Decimal
    expected_cash: Decimal
    actual_cash: Decimal
    variance: Decimal
    status: Literal["MATCH", "SHORTAGE", "EXCESS"]


class PerWorkerReconciliationResponse(BaseModel):
    """Response from POST /reconciliation/shifts/{id}/run-per-worker."""

    shift_id: UUID
    results: list[WorkerReconciliationResult]
    total_shift_sale: Decimal
    total_variance: Decimal
