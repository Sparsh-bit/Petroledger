"""
PetroLedger — Data-Ingestion API Routes.

File-upload endpoints that validate, queue Celery tasks, and return
job tracking IDs.  A status endpoint reads progress from Redis.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import redis
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.core.rate_limit import limiter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rbac import require_role
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.tenant import verify_tenant_match
from app.db.session import get_db
from app.models.organization import Organization
from app.models.pump import Pump
from app.models.shift import Shift
from app.models.user import User, UserRole
from app.schemas.ingestion import (
    IngestionJobResponse,
    IngestionResult,
    JobStatusResponse,
)
from app.services.storage import S3Service
from app.tasks.ingestion import (
    process_pos_slip,
    process_pump_log,
    process_upi_csv,
)

router = APIRouter()

settings = get_settings()
_redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
_s3 = S3Service()

# ── Constants ───────────────────────────────────────────────────────────

_MAX_CSV_SIZE = 10 * 1024 * 1024   # 10 MB
_MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
_MAX_LOG_SIZE = 10 * 1024 * 1024   # 10 MB

_CSV_EXTENSIONS = {".csv"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
_LOG_EXTENSIONS = {".json", ".csv", ".txt"}

_JOB_KEY = "petroledger:job:{job_id}"

_MANAGER_ROLES = (UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)


# ── Helpers ─────────────────────────────────────────────────────────────


async def _verify_shift_tenant(
    shift_uuid: uuid.UUID, user: User, db: AsyncSession
) -> None:
    """Raise 404 if shift doesn't exist; raise 404 if it belongs to a different tenant."""
    stmt = (
        select(Organization.tenant_id)
        .join(Pump, Pump.org_id == Organization.id)
        .join(Shift, Shift.pump_id == Pump.id)
        .where(Shift.id == shift_uuid)
    )
    result = await db.execute(stmt)
    shift_tenant_id = result.scalar_one_or_none()
    if shift_tenant_id is None:
        raise NotFoundError(resource="Shift", identifier=str(shift_uuid))
    verify_tenant_match(shift_tenant_id, user)


def _get_ext(filename: str) -> str:
    """Return lowercased file extension including the dot."""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


async def _read_file(upload: UploadFile, max_size: int) -> bytes:
    """Read upload file bytes and enforce max size."""
    content = await upload.read()
    if len(content) > max_size:
        max_mb = max_size / (1024 * 1024)
        raise ValidationError(
            message=f"File too large. Maximum allowed size is {max_mb:.0f} MB.",
        )
    return content


def _queue_job(job_id: str, s3_key: str) -> None:
    """Initialise the Redis hash for a new job."""
    key = _JOB_KEY.format(job_id=job_id)
    _redis.hset(
        key,
        mapping={
            "status": "queued",
            "progress": "0",
            "result": "",
            "error": "",
            "s3_key": s3_key,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    _redis.expire(key, 86_400)  # 24 h TTL


# ── 1. POST /upi-csv ───────────────────────────────────────────────────


@router.post(
    "/upi-csv",
    response_model=IngestionJobResponse,
    summary="Upload UPI bank CSV",
    status_code=202,
)
@limiter.limit("30/hour")
async def upload_upi_csv(
    request: Request,
    file: UploadFile = File(...),
    shift_id: str = Form(...),
    user: User = Depends(require_role(*_MANAGER_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobResponse:
    """
    Accept a UPI bank-statement CSV, validate it, and queue a
    background Celery task for parsing and insertion.
    """
    # Validate extension
    ext = _get_ext(file.filename or "")
    if ext not in _CSV_EXTENSIONS:
        raise ValidationError(
            message=f"Invalid file type '{ext}'. Only .csv files are accepted.",
        )

    # Validate UUID and tenant ownership
    try:
        shift_uuid = uuid.UUID(shift_id)
    except ValueError as exc:
        raise ValidationError(message=f"Invalid shift_id: {exc}") from exc
    await _verify_shift_tenant(shift_uuid, user, db)

    # Read and validate size
    content = await _read_file(file, _MAX_CSV_SIZE)

    # Upload to S3 then queue Celery task
    job_id = str(uuid.uuid4())
    s3_key = f"ingestion/{job_id}/{file.filename or 'upload.csv'}"
    await _s3.upload_file_async(content, s3_key)
    _queue_job(job_id, s3_key)

    process_upi_csv.delay(job_id, s3_key, shift_id, file.filename or "upload.csv")

    return IngestionJobResponse(
        job_id=job_id,
        status="queued",
        message=f"UPI CSV '{file.filename}' queued for processing.",
    )


# ── 2. POST /pos-slip ──────────────────────────────────────────────────


@router.post(
    "/pos-slip",
    response_model=IngestionJobResponse,
    summary="Upload POS settlement slip image",
    status_code=202,
)
@limiter.limit("30/hour")
async def upload_pos_slip(
    request: Request,
    file: UploadFile = File(...),
    shift_id: str = Form(...),
    user: User = Depends(require_role(*_MANAGER_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobResponse:
    """Accept a POS slip image (JPG/PNG/PDF), queue OCR + parsing."""

    ext = _get_ext(file.filename or "")
    if ext not in _IMAGE_EXTENSIONS:
        raise ValidationError(
            message=(
                f"Invalid file type '{ext}'. "
                f"Accepted: {', '.join(sorted(_IMAGE_EXTENSIONS))}."
            ),
        )

    try:
        shift_uuid = uuid.UUID(shift_id)
    except ValueError as exc:
        raise ValidationError(message=f"Invalid shift_id: {exc}") from exc
    await _verify_shift_tenant(shift_uuid, user, db)

    content = await _read_file(file, _MAX_IMAGE_SIZE)

    job_id = str(uuid.uuid4())
    s3_key = f"ingestion/{job_id}/{file.filename or 'slip.jpg'}"
    await _s3.upload_file_async(content, s3_key)
    _queue_job(job_id, s3_key)

    process_pos_slip.delay(job_id, s3_key, shift_id, file.filename or "slip.jpg")

    return IngestionJobResponse(
        job_id=job_id,
        status="queued",
        message=f"POS slip '{file.filename}' queued for OCR processing.",
    )


# ── 3. POST /pump-logs ─────────────────────────────────────────────────


@router.post(
    "/pump-logs",
    response_model=IngestionJobResponse,
    summary="Upload pump dispenser log file",
    status_code=202,
)
@limiter.limit("30/hour")
async def upload_pump_logs(
    request: Request,
    file: UploadFile = File(...),
    shift_id: str = Form(...),
    pump_id: str = Form(...),
    user: User = Depends(require_role(*_MANAGER_ROLES)),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobResponse:
    """Accept a pump log (JSON/CSV/TXT), queue parsing."""

    ext = _get_ext(file.filename or "")
    if ext not in _LOG_EXTENSIONS:
        raise ValidationError(
            message=(
                f"Invalid file type '{ext}'. "
                f"Accepted: {', '.join(sorted(_LOG_EXTENSIONS))}."
            ),
        )

    try:
        shift_uuid = uuid.UUID(shift_id)
    except ValueError as exc:
        raise ValidationError(message=f"Invalid shift_id: {exc}") from exc
    try:
        pump_uuid = uuid.UUID(pump_id)
    except ValueError as exc:
        raise ValidationError(message=f"Invalid pump_id: {exc}") from exc

    await _verify_shift_tenant(shift_uuid, user, db)

    # Verify pump belongs to the same tenant
    pump_stmt = (
        select(Organization.tenant_id)
        .join(Pump, Pump.org_id == Organization.id)
        .where(Pump.id == pump_uuid)
    )
    pump_result = await db.execute(pump_stmt)
    pump_tenant_id = pump_result.scalar_one_or_none()
    if pump_tenant_id is None:
        raise NotFoundError(resource="Pump", identifier=str(pump_uuid))
    verify_tenant_match(pump_tenant_id, user)

    content = await _read_file(file, _MAX_LOG_SIZE)

    job_id = str(uuid.uuid4())
    s3_key = f"ingestion/{job_id}/{file.filename or 'log.txt'}"
    await _s3.upload_file_async(content, s3_key)
    _queue_job(job_id, s3_key)

    process_pump_log.delay(
        job_id, s3_key, shift_id, pump_id, file.filename or "log.txt"
    )

    return IngestionJobResponse(
        job_id=job_id,
        status="queued",
        message=f"Pump log '{file.filename}' queued for processing.",
    )


# ── 4. GET /status/{job_id} ────────────────────────────────────────────


@router.get(
    "/status/{job_id}",
    response_model=JobStatusResponse,
    summary="Check ingestion job status",
)
async def get_job_status(
    job_id: str,
    user: User = Depends(require_role(*_MANAGER_ROLES)),
) -> JobStatusResponse:
    """Read job progress from Redis."""

    key = _JOB_KEY.format(job_id=job_id)
    data = _redis.hgetall(key)

    if not data:
        raise ValidationError(
            message=f"Job '{job_id}' not found or has expired.",
        )

    # Parse result JSON if present
    result = None
    raw_result = data.get("result", "")
    if raw_result:
        try:
            result = IngestionResult(**json.loads(raw_result))
        except Exception:
            result = None

    return JobStatusResponse(
        job_id=job_id,
        status=data.get("status", "unknown"),
        progress=int(data.get("progress", 0)),
        result=result,
        error=data.get("error") or None,
        created_at=data.get("created_at"),
    )
