"""
PetroLedger — Report Generation Celery Tasks.

Async/sync bridge: same asyncio.run() + fresh engine pattern as reconciliation.py.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date

import structlog
from celery import shared_task
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

log = structlog.stdlib.get_logger("petroledger.tasks.reports")
settings = get_settings()


def _make_session_factory() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    return engine, async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


# ═══════════════════════════════════════════════════════════════════════
#  TASK 1 — generate_shift_report
# ═══════════════════════════════════════════════════════════════════════


@shared_task(bind=True, name="reports.generate_shift_report", max_retries=2)
def generate_shift_report(self, shift_id: str) -> dict:
    """Generate a PDF shift report and return the file path.

    Parameters
    ----------
    shift_id:
        UUID string of the shift to report on.
    """
    log.info("shift_report_task_started", shift_id=shift_id)
    try:
        path = asyncio.run(_generate_shift_async(shift_id))
        log.info("shift_report_task_complete", shift_id=shift_id, path=path)
        return {"shift_id": shift_id, "path": path, "status": "completed"}
    except Exception as exc:
        log.exception("shift_report_task_failed", shift_id=shift_id)
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries)) from exc


async def _generate_shift_async(shift_id: str) -> str:
    from app.services.reports.shift_report import ShiftReportService

    _engine, session_factory = _make_session_factory()
    try:
        async with session_factory() as db:
            svc = ShiftReportService()
            path = await svc.generate(uuid.UUID(shift_id), db)
            return str(path)
    finally:
        await _engine.dispose()


# ═══════════════════════════════════════════════════════════════════════
#  TASK 2 — generate_daily_report
# ═══════════════════════════════════════════════════════════════════════


@shared_task(bind=True, name="reports.generate_daily_report", max_retries=2)
def generate_daily_report(self, site_id: str, report_date_iso: str) -> dict:
    """Generate a PDF + Excel daily summary report.

    Parameters
    ----------
    site_id:
        UUID string of the organisation / site.
    report_date_iso:
        Date in ISO format ``YYYY-MM-DD``.
    """
    log.info(
        "daily_report_task_started", site_id=site_id, report_date=report_date_iso
    )
    try:
        result = asyncio.run(_generate_daily_async(site_id, report_date_iso))
        log.info(
            "daily_report_task_complete",
            site_id=site_id,
            pdf=result["pdf_path"],
            excel=result["excel_path"],
        )
        return result
    except Exception as exc:
        log.exception(
            "daily_report_task_failed", site_id=site_id, date=report_date_iso
        )
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries)) from exc


async def _generate_daily_async(site_id: str, report_date_iso: str) -> dict:
    from app.services.reports.daily_report import DailyReportService

    report_date = date.fromisoformat(report_date_iso)
    _engine, session_factory = _make_session_factory()
    try:
        async with session_factory() as db:
            svc = DailyReportService()
            pdf_path = await svc.generate_pdf(uuid.UUID(site_id), report_date, db)
            excel_path = await svc.generate_excel(uuid.UUID(site_id), report_date, db)
    finally:
        await _engine.dispose()
    return {
        "site_id": site_id,
        "report_date": report_date_iso,
        "pdf_path": str(pdf_path),
        "excel_path": str(excel_path),
        "status": "completed",
    }
