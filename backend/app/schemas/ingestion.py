"""PetroLedger — Data-Ingestion Pydantic Schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestionJobResponse(BaseModel):
    """Returned immediately when a file upload is queued."""

    job_id: str = Field(..., description="Unique job tracking ID")
    status: str = Field(default="queued", description="Current job status")
    message: str = Field(..., description="Human-readable status message")

    model_config = {"json_schema_extra": {"examples": [
        {"job_id": "abc-123", "status": "queued", "message": "UPI CSV queued for processing"},
    ]}}


class IngestionResult(BaseModel):
    """Summary embedded in the completed job status."""

    total_records: int = Field(default=0)
    processed_records: int = Field(default=0)
    failed_records: int = Field(default=0)
    duplicates_skipped: int = Field(default=0)


class JobStatusResponse(BaseModel):
    """Full job status retrieved from Redis."""

    job_id: str
    status: str = Field(
        ..., description="queued | processing | completed | failed"
    )
    progress: int = Field(
        default=0, ge=0, le=100, description="Percentage 0-100"
    )
    result: IngestionResult | None = Field(
        default=None, description="Present when status=completed"
    )
    error: str | None = Field(
        default=None, description="Present when status=failed"
    )
    created_at: str | None = Field(
        default=None, description="ISO timestamp when job was queued"
    )
