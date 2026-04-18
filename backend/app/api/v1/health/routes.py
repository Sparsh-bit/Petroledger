"""PetroLedger — Detailed health endpoint.

Augments the minimal ``/health`` on the FastAPI app with DB + Redis probes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter()


async def _check_redis() -> str:
    settings = get_settings()
    try:
        import redis.asyncio as redis_async

        client = redis_async.from_url(settings.REDIS_URL, socket_connect_timeout=1.0)
        pong = await client.ping()
        await client.aclose()
        return "ok" if pong else "down"
    except Exception:
        return "down"


@router.get("/", summary="Detailed health probe")
async def detailed_health(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    settings = get_settings()
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"

    return {
        "status": "healthy" if db_status == "ok" else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "db": db_status,
        "redis": await _check_redis(),
    }
