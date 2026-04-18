"""PetroLedger — Reconciliation Schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.reconciliation import ReconciliationStatus

# ── Supporting Schemas ──────────────────────────────────────────────────


class AnomalyDetail(BaseModel):
    """Describes a single anomaly detected during reconciliation."""

    type: str = Field(..., description="Anomaly category, e.g. 'missing_upi', 'amount_mismatch'")
    description: str
    severity: str = Field(..., description="low | medium | high | critical")
    amount: Decimal | None = Field(None, description="Monetary impact, if applicable", examples=["500.00"])
    related_transaction_id: UUID | None = None


class ConfidenceBreakdown(BaseModel):
    """Per-component confidence scores that compose the overall score.

    Each component is scored 0–100 and combined via a weighted average
    into ``overall_score``.  When the overall score falls below the
    review threshold (70) the ``requires_review`` flag is set and
    ``review_reasons`` lists the weak areas.
    """

    overall_score: int = Field(..., ge=0, le=100)
    data_completeness: int = Field(..., ge=0, le=100)
    variance_score: int = Field(..., ge=0, le=100)
    anomaly_score: int = Field(..., ge=0, le=100)
    historical_score: int = Field(..., ge=0, le=100)
    requires_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)


# ── Request Schemas ─────────────────────────────────────────────────────


class ReconciliationRequest(BaseModel):
    shift_id: UUID
    actual_cash: Decimal = Field(..., ge=0, description="Cash amount physically counted")


# ── Response Schemas ────────────────────────────────────────────────────


class ReconciliationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shift_id: UUID
    expected_cash: Decimal = Field(..., examples=["11000.00"])
    actual_cash: Decimal = Field(..., examples=["11000.00"])
    variance: Decimal = Field(..., examples=["0.00"])
    confidence_score: Decimal | None = Field(None, examples=["85.00"])
    confidence_breakdown: ConfidenceBreakdown | None = None
    status: ReconciliationStatus
    anomalies: list[AnomalyDetail] = Field(default_factory=list)
    grade_breakdown: dict[str, dict[str, str]] | None = Field(
        default=None,
        description=(
            "Per-fuel-grade totals keyed by product code (MS/HSD/SPD97/CNG). "
            "Values: volume_litres, amount, unit_price as strings to preserve "
            "Decimal precision."
        ),
    )
    variance_reason: str | None = None
    variance_notes: str | None = None
    reason_set_by_user_id: UUID | None = None
    reason_set_at: datetime | None = None
    created_at: datetime
