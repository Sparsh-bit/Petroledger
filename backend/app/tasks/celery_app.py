"""
PetroLedger — Celery Application Factory.

Configures Celery with Redis broker, JSON serialization,
Asia/Kolkata timezone, and built-in PersistentScheduler.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("petroledger")

# ── Core configuration ──────────────────────────────────────────────────

celery_app.conf.update(
    # Broker / Backend
    broker_url=settings.celery_broker,
    result_backend=settings.REDIS_URL,

    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,  # 1 hour

    # Timezone
    timezone="Asia/Kolkata",
    enable_utc=True,

    # Task behaviour
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Scheduler
    beat_scheduler="celery.beat:PersistentScheduler",
    beat_max_loop_interval=5,
)

# ── Beat schedule ───────────────────────────────────────────────────────

celery_app.conf.beat_schedule = {
    "eod-reconciliation": {
        "task": "app.tasks.reconciliation.run_eod_reconciliation",
        "schedule": crontab(hour=23, minute=45),
        "options": {"timezone": "Asia/Kolkata"},
    },
}

# ── Auto-discover task modules ──────────────────────────────────────────

celery_app.autodiscover_tasks(
    [
        "app.tasks.ingestion",
        "app.tasks.reconciliation",
        "app.tasks.reports",
    ]
)
