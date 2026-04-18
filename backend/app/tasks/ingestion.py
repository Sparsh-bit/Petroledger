"""
PetroLedger — Data-Ingestion Celery Tasks.

Full pipeline for each task:

    1. Decode base64 file → raw bytes.
    2. Parse via the appropriate service.
    3. Deduplicate (intra-batch + DB) via ``DeduplicationService.filter_duplicates()``.
    4. Normalise into ORM instances via ``NormalizationService``.
    5. Bulk-insert with ``ON CONFLICT DO NOTHING``.
    6. Write an audit-trail entry via ``AuditService``.
    7. Update Redis job status at each step (queued → processing → completed | failed).

All tasks use ``asyncio.run()`` to bridge the sync Celery worker to async
SQLAlchemy / service code.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import redis
import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings

log = structlog.stdlib.get_logger("petroledger.tasks.ingestion")
settings = get_settings()

_redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

# ── Transient exceptions eligible for auto-retry ────────────────────────

_TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
    redis.ConnectionError,
    redis.TimeoutError,
)


# ── Redis helpers ───────────────────────────────────────────────────────

_JOB_KEY = "petroledger:job:{job_id}"


def _set_job_status(
    job_id: str,
    status: str,
    *,
    progress: int = 0,
    result: dict | None = None,
    error: str = "",
) -> None:
    """Persist job progress to a Redis hash (TTL 24 h)."""
    key = _JOB_KEY.format(job_id=job_id)
    mapping: dict[str, str] = {
        "status": status,
        "progress": str(progress),
        "error": error,
    }
    if result is not None:
        mapping["result"] = json.dumps(result)
    _redis.hset(key, mapping=mapping)
    _redis.expire(key, 86_400)


def _result_dict(
    total: int = 0,
    processed: int = 0,
    failed: int = 0,
    duplicates: int = 0,
) -> dict[str, int]:
    return {
        "total_records": total,
        "processed_records": processed,
        "failed_records": failed,
        "duplicates_skipped": duplicates,
    }


# ── Shared async helpers ────────────────────────────────────────────────


async def _get_org_id_from_shift(db: AsyncSession, shift_id: uuid.UUID) -> uuid.UUID:
    """Resolve shift → pump → org_id."""
    from app.models.pump import Pump
    from app.models.shift import Shift

    stmt = (
        select(Pump.org_id)
        .join(Shift, Shift.pump_id == Pump.id)
        .where(Shift.id == shift_id)
    )
    result = await db.execute(stmt)
    org_id = result.scalar_one_or_none()
    if org_id is None:
        raise ValueError(f"Shift {shift_id} not found or has no pump")
    return org_id


async def _get_tenant_id_from_org(db: AsyncSession, org_id: uuid.UUID) -> uuid.UUID:
    """Resolve org_id → tenant_id for audit scoping."""
    from app.models.organization import Organization

    stmt = select(Organization.tenant_id).where(Organization.id == org_id)
    result = await db.execute(stmt)
    tenant_id = result.scalar_one_or_none()
    if tenant_id is None:
        raise ValueError(f"Organization {org_id} not found")
    return tenant_id


def _backoff(retries: int) -> int:
    """Exponential backoff: 30s, 60s, 120s."""
    return 30 * (2 ** retries)


_SYSTEM_USER = uuid.UUID("00000000-0000-0000-0000-000000000000")
_NIL_ORG = uuid.UUID("00000000-0000-0000-0000-000000000000")
_NIL_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _write_failure_audit(
    job_id: str,
    action: str,
    shift_id: str,
    filename: str,
    error: str,
    extra: dict | None = None,
) -> None:
    """Best-effort audit entry for failure paths. Never raises."""
    from app.services.audit import AuditService

    async def _run() -> None:
        engine = create_async_engine(settings.DATABASE_URL, pool_size=1)
        try:
            async with AsyncSession(engine) as db:
                sid = uuid.UUID(shift_id)
                try:
                    org_id = await _get_org_id_from_shift(db, sid)
                    tenant_id = await _get_tenant_id_from_org(db, org_id)
                except Exception:
                    org_id = _NIL_ORG
                    tenant_id = _NIL_TENANT
                await AuditService.log(
                    db,
                    action=action,
                    entity_type="shift",
                    entity_id=sid,
                    user_id=_SYSTEM_USER,
                    org_id=org_id,
                    tenant_id=tenant_id,
                    before=None,
                    after={"status": "failed", "filename": filename, "error": error, **(extra or {})},
                    metadata={"job_id": job_id},
                )
                await db.commit()
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    except Exception:
        log.warning("audit.failure_write_error", job_id=job_id)


# ── UPI CSV ─────────────────────────────────────────────────────────────


@shared_task(bind=True, name="ingestion.process_upi_csv", max_retries=3)
def process_upi_csv(
    self,
    job_id: str,
    s3_key: str,
    shift_id: str,
    filename: str = "upload.csv",
) -> dict:
    """Parse a UPI bank-statement CSV, deduplicate, normalise, persist, audit."""
    from app.services.storage import S3Service

    _s3 = S3Service()

    log.info("upi_csv.start", job_id=job_id, filename=filename)
    _set_job_status(job_id, "processing", progress=10)

    try:
        # ── 1. Download from S3 ─────────────────────────────────────
        file_bytes = _s3.download_file(s3_key)
        log.debug("upi_csv.downloaded", job_id=job_id, size=len(file_bytes))

        # ── 2. Parse ────────────────────────────────────────────────
        from app.services.parsers.upi_csv import UPICSVParserService

        parser = UPICSVParserService()
        parse_result = parser.parse(file_bytes, filename)
        log.info(
            "upi_csv.parsed",
            job_id=job_id,
            total=parse_result.total_records,
            records=len(parse_result.records),
            errors=parse_result.failed_records,
        )
        _set_job_status(job_id, "processing", progress=40)

        # ── 3–8. Dedup → Normalise → Insert → Audit (all async) ────
        from app.services.audit import AuditService
        from app.services.deduplication import DeduplicationService
        from app.services.normalization import NormalizationService

        dedup = DeduplicationService()
        norm = NormalizationService()
        sid = uuid.UUID(shift_id)

        async def _pipeline() -> tuple[int, int, uuid.UUID]:
            engine = create_async_engine(settings.DATABASE_URL, pool_size=3)
            try:
                async with AsyncSession(engine) as db:
                    # Resolve org_id for dedup scoping and audit
                    org_id = await _get_org_id_from_shift(db, sid)

                    # ── 5. Deduplicate (intra-batch + DB) ───────────
                    new_records, dups = await dedup.filter_duplicates(
                        records=parse_result.records,
                        hash_fn=dedup.generate_upi_hash,
                        check_fn=dedup.check_upi_duplicate,
                        db=db,
                        org_id=org_id,
                    )
                    dup_count = len(dups)
                    log.info(
                        "upi_csv.dedup_done",
                        job_id=job_id,
                        new=len(new_records),
                        duplicates=dup_count,
                    )
                    _set_job_status(job_id, "processing", progress=60)

                    # ── 7. Normalise ────────────────────────────────
                    models = await norm.normalize_upi_records(
                        new_records, sid, db, org_id
                    )

                    # ── 8. Bulk insert ──────────────────────────────
                    inserted = await norm.bulk_insert(db, models)
                    log.info(
                        "upi_csv.inserted",
                        job_id=job_id,
                        attempted=len(models),
                        inserted=inserted,
                    )
                    _set_job_status(job_id, "processing", progress=90)

                    # ── 10. Audit ───────────────────────────────────
                    # We need a user_id for audit — use a system UUID
                    # since tasks run in background without user context
                    system_user = uuid.UUID("00000000-0000-0000-0000-000000000000")
                    await AuditService.log(
                        db,
                        action="upi_upload",
                        entity_type="shift",
                        entity_id=sid,
                        user_id=system_user,
                        org_id=org_id,
                        tenant_id=await _get_tenant_id_from_org(db, org_id),
                        before=None,
                        after={
                            "filename": filename,
                            "total_records": parse_result.total_records,
                            "inserted": inserted,
                            "duplicates_skipped": dup_count,
                        },
                        metadata={"job_id": job_id},
                    )

                    await db.commit()
                    return inserted, dup_count, org_id
            finally:
                await engine.dispose()

        inserted, dup_count, _ = asyncio.run(_pipeline())

        # ── 11. Mark completed ──────────────────────────────────────
        result = _result_dict(
            total=parse_result.total_records,
            processed=inserted,
            failed=parse_result.failed_records,
            duplicates=dup_count,
        )
        _set_job_status(job_id, "completed", progress=100, result=result)
        _s3.delete_file(s3_key)
        log.info("upi_csv.completed", job_id=job_id, **result)
        return {"job_id": job_id, "status": "completed", **result}

    except _TRANSIENT_EXCEPTIONS as exc:
        _set_job_status(job_id, "failed", error=str(exc))
        log.warning(
            "upi_csv.transient_error",
            job_id=job_id,
            error=str(exc),
            retry=self.request.retries,
        )
        if self.request.retries >= self.max_retries:
            _s3.delete_file(s3_key)
            _write_failure_audit(job_id, "upi_upload", shift_id, filename, str(exc))
        raise self.retry(exc=exc, countdown=_backoff(self.request.retries)) from exc

    except Exception as exc:
        _set_job_status(job_id, "failed", error=str(exc))
        _s3.delete_file(s3_key)
        _write_failure_audit(job_id, "upi_upload", shift_id, filename, str(exc))
        log.exception("upi_csv.failed", job_id=job_id)
        return {"job_id": job_id, "status": "failed", "error": str(exc)}


# ── POS Slip (image) ───────────────────────────────────────────────────


@shared_task(bind=True, name="ingestion.process_pos_slip", max_retries=3)
def process_pos_slip(
    self,
    job_id: str,
    s3_key: str,
    shift_id: str,
    filename: str = "slip.jpg",
) -> dict:
    """Extract data from a POS slip image via OCR, normalise, persist, audit."""
    from app.services.storage import S3Service

    _s3 = S3Service()

    log.info("pos_slip.start", job_id=job_id, filename=filename)
    _set_job_status(job_id, "processing", progress=10)

    try:
        # ── 1. Download from S3 ─────────────────────────────────────
        file_bytes = _s3.download_file(s3_key)
        log.debug("pos_slip.downloaded", job_id=job_id, size=len(file_bytes))

        # ── 2. OCR + Parse ──────────────────────────────────────────
        from app.services.parsers.pos_ocr import POSOCRService

        ocr = POSOCRService()
        parse_result = ocr.parse(file_bytes, filename)
        _set_job_status(job_id, "processing", progress=40)

        if not parse_result.success or parse_result.record is None:
            errors = "; ".join(parse_result.errors) or "OCR extraction failed"
            log.warning(
                "pos_slip.ocr_failed",
                job_id=job_id,
                confidence=parse_result.confidence,
                errors=errors,
            )
            _set_job_status(
                job_id,
                "failed",
                error=f"Low confidence ({parse_result.confidence:.2f}): {errors}",
            )
            _s3.delete_file(s3_key)
            _write_failure_audit(
                job_id, "pos_upload", shift_id, filename, errors,
                {"confidence": parse_result.confidence},
            )
            return {"job_id": job_id, "status": "failed", "error": errors}

        log.info(
            "pos_slip.parsed",
            job_id=job_id,
            confidence=parse_result.confidence,
            amount=str(parse_result.record.amount),
        )

        # ── 3–8. Dedup → Normalise → Insert → Audit ────────────────
        from app.services.audit import AuditService
        from app.services.deduplication import DeduplicationService
        from app.services.normalization import NormalizationService

        dedup = DeduplicationService()
        norm = NormalizationService()
        sid = uuid.UUID(shift_id)

        async def _pipeline() -> tuple[int, int]:
            engine = create_async_engine(settings.DATABASE_URL, pool_size=3)
            try:
                async with AsyncSession(engine) as db:
                    org_id = await _get_org_id_from_shift(db, sid)

                    # ── Deduplicate ─────────────────────────────────
                    new_records, dups = await dedup.filter_duplicates(
                        records=[parse_result.record],
                        hash_fn=dedup.generate_pos_hash,
                        check_fn=dedup.check_pos_duplicate,
                        db=db,
                        org_id=org_id,
                    )
                    dup_count = len(dups)
                    _set_job_status(job_id, "processing", progress=60)

                    if not new_records:
                        log.info("pos_slip.duplicate", job_id=job_id)
                        return 0, 1

                    # ── Normalise ───────────────────────────────────
                    models = await norm.normalize_pos_records(
                        new_records, sid, db, org_id
                    )

                    # ── Bulk insert ─────────────────────────────────
                    inserted = await norm.bulk_insert(db, models)
                    _set_job_status(job_id, "processing", progress=90)

                    # ── Audit ───────────────────────────────────────
                    system_user = uuid.UUID("00000000-0000-0000-0000-000000000000")
                    await AuditService.log(
                        db,
                        action="pos_upload",
                        entity_type="shift",
                        entity_id=sid,
                        user_id=system_user,
                        org_id=org_id,
                        tenant_id=await _get_tenant_id_from_org(db, org_id),
                        before=None,
                        after={
                            "filename": filename,
                            "confidence": parse_result.confidence,
                            "amount": str(parse_result.record.amount),
                            "inserted": inserted,
                        },
                        metadata={"job_id": job_id},
                    )

                    await db.commit()
                    return inserted, dup_count
            finally:
                await engine.dispose()

        inserted, dup_count = asyncio.run(_pipeline())

        result = _result_dict(total=1, processed=inserted, failed=0, duplicates=dup_count)
        _set_job_status(job_id, "completed", progress=100, result=result)
        _s3.delete_file(s3_key)
        log.info("pos_slip.completed", job_id=job_id, **result)
        return {"job_id": job_id, "status": "completed", **result}

    except _TRANSIENT_EXCEPTIONS as exc:
        _set_job_status(job_id, "failed", error=str(exc))
        log.warning(
            "pos_slip.transient_error",
            job_id=job_id,
            error=str(exc),
            retry=self.request.retries,
        )
        if self.request.retries >= self.max_retries:
            _s3.delete_file(s3_key)
            _write_failure_audit(job_id, "pos_upload", shift_id, filename, str(exc))
        raise self.retry(exc=exc, countdown=_backoff(self.request.retries)) from exc

    except Exception as exc:
        _set_job_status(job_id, "failed", error=str(exc))
        _s3.delete_file(s3_key)
        _write_failure_audit(job_id, "pos_upload", shift_id, filename, str(exc))
        log.exception("pos_slip.failed", job_id=job_id)
        return {"job_id": job_id, "status": "failed", "error": str(exc)}


# ── Pump Log ────────────────────────────────────────────────────────────


@shared_task(bind=True, name="ingestion.process_pump_log", max_retries=3)
def process_pump_log(
    self,
    job_id: str,
    s3_key: str,
    shift_id: str,
    pump_id: str,
    filename: str = "log.txt",
) -> dict:
    """Parse a pump meter-reading log file, deduplicate, normalise, persist, audit."""
    from app.services.storage import S3Service

    _s3 = S3Service()

    log.info("pump_log.start", job_id=job_id, filename=filename, pump_id=pump_id)
    _set_job_status(job_id, "processing", progress=10)

    try:
        # ── 1. Download from S3 ─────────────────────────────────────
        file_bytes = _s3.download_file(s3_key)
        log.debug("pump_log.downloaded", job_id=job_id, size=len(file_bytes))

        # ── 2. Parse ────────────────────────────────────────────────
        from app.services.parsers.pump_log import PumpLogParserService

        parser = PumpLogParserService()
        parse_result = parser.parse(file_bytes, filename)
        log.info(
            "pump_log.parsed",
            job_id=job_id,
            total=parse_result.total_records,
            records=len(parse_result.records),
            errors=parse_result.failed_records,
        )
        _set_job_status(job_id, "processing", progress=40)

        # ── 3–8. Dedup → Normalise → Insert → Audit ────────────────
        from app.services.audit import AuditService
        from app.services.deduplication import DeduplicationService
        from app.services.normalization import NormalizationService

        dedup = DeduplicationService()
        norm = NormalizationService()
        sid = uuid.UUID(shift_id)
        pid = uuid.UUID(pump_id)

        async def _pipeline() -> tuple[int, int]:
            engine = create_async_engine(settings.DATABASE_URL, pool_size=3)
            try:
                async with AsyncSession(engine) as db:
                    org_id = await _get_org_id_from_shift(db, sid)

                    # ── Deduplicate ─────────────────────────────────
                    new_records, dups = await dedup.filter_duplicates(
                        records=parse_result.records,
                        hash_fn=dedup.generate_pump_hash,
                        check_fn=dedup.check_pump_duplicate,
                        db=db,
                        org_id=org_id,
                    )
                    dup_count = len(dups)
                    log.info(
                        "pump_log.dedup_done",
                        job_id=job_id,
                        new=len(new_records),
                        duplicates=dup_count,
                    )
                    _set_job_status(job_id, "processing", progress=60)

                    # ── Normalise ───────────────────────────────────
                    models = await norm.normalize_pump_logs(
                        new_records, sid, pid, db, org_id
                    )

                    # ── Bulk insert ─────────────────────────────────
                    inserted = await norm.bulk_insert(db, models)
                    log.info(
                        "pump_log.inserted",
                        job_id=job_id,
                        attempted=len(models),
                        inserted=inserted,
                    )
                    _set_job_status(job_id, "processing", progress=90)

                    # ── Audit ───────────────────────────────────────
                    system_user = uuid.UUID("00000000-0000-0000-0000-000000000000")
                    await AuditService.log(
                        db,
                        action="pump_log_upload",
                        entity_type="shift",
                        entity_id=sid,
                        user_id=system_user,
                        org_id=org_id,
                        tenant_id=await _get_tenant_id_from_org(db, org_id),
                        before=None,
                        after={
                            "filename": filename,
                            "pump_id": pump_id,
                            "total_records": parse_result.total_records,
                            "inserted": inserted,
                            "duplicates_skipped": dup_count,
                        },
                        metadata={"job_id": job_id},
                    )

                    await db.commit()
                    return inserted, dup_count
            finally:
                await engine.dispose()

        inserted, dup_count = asyncio.run(_pipeline())

        result = _result_dict(
            total=parse_result.total_records,
            processed=inserted,
            failed=parse_result.failed_records,
            duplicates=dup_count,
        )
        _set_job_status(job_id, "completed", progress=100, result=result)
        _s3.delete_file(s3_key)
        log.info("pump_log.completed", job_id=job_id, **result)
        return {"job_id": job_id, "status": "completed", **result}

    except _TRANSIENT_EXCEPTIONS as exc:
        _set_job_status(job_id, "failed", error=str(exc))
        log.warning(
            "pump_log.transient_error",
            job_id=job_id,
            error=str(exc),
            retry=self.request.retries,
        )
        if self.request.retries >= self.max_retries:
            _s3.delete_file(s3_key)
            _write_failure_audit(job_id, "pump_log_upload", shift_id, filename, str(exc))
        raise self.retry(exc=exc, countdown=_backoff(self.request.retries)) from exc

    except Exception as exc:
        _set_job_status(job_id, "failed", error=str(exc))
        _s3.delete_file(s3_key)
        _write_failure_audit(job_id, "pump_log_upload", shift_id, filename, str(exc))
        log.exception("pump_log.failed", job_id=job_id)
        return {"job_id": job_id, "status": "failed", "error": str(exc)}
