"""PetroLedger — Redis-cached tenant lock lookup.

The tenant-lock middleware runs on almost every request, so a DB round-trip
per call is wasteful. We cache the ``is_locked`` flag in Redis for 60s,
keyed by ``tenant_locked:{tenant_id}``.

- Cache HIT  → return bool immediately, no DB hit.
- Cache MISS → query DB, cache the result, return.
- Redis unreachable → silently fall back to the DB query.

Provider lock/unlock endpoints call :func:`invalidate_tenant_lock` so the
flip is reflected on the very next request.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.tenant import Tenant

if TYPE_CHECKING:
    import redis as redis_lib

log = structlog.stdlib.get_logger("petroledger.core.tenant_lock_cache")

_KEY_PREFIX = "tenant_locked:"
_TTL_SECONDS = 60

_redis: "redis_lib.Redis | None"
try:
    import redis as _redis_module

    _settings = get_settings()
    _redis = _redis_module.Redis.from_url(
        _settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=0.3,
        socket_timeout=0.3,
    )
except Exception:  # pragma: no cover — missing dep / bad URL
    _redis = None


def _cache_key(tenant_id: str) -> str:
    return f"{_KEY_PREFIX}{tenant_id}"


async def _db_lookup(tenant_id: str) -> bool:
    async with async_session_factory() as session:
        row = await session.execute(
            select(Tenant.is_locked).where(Tenant.id == tenant_id)
        )
        return bool(row.scalar_one_or_none())


def _cache_get(tenant_id: str) -> str | None:
    if _redis is None:
        return None
    try:
        return _redis.get(_cache_key(tenant_id))
    except Exception:
        return None


def _cache_set(tenant_id: str, value: bool) -> None:
    if _redis is None:
        return
    try:
        _redis.setex(_cache_key(tenant_id), _TTL_SECONDS, "1" if value else "0")
    except Exception:
        pass


def _cache_del(tenant_id: str) -> None:
    if _redis is None:
        return
    try:
        _redis.delete(_cache_key(tenant_id))
    except Exception:
        pass


async def is_tenant_locked(tenant_id: str) -> bool:
    """Return True if the tenant is currently locked. Cached for 60s."""
    cached = await asyncio.to_thread(_cache_get, tenant_id)
    if cached is not None:
        return cached == "1"

    locked = await _db_lookup(tenant_id)
    await asyncio.to_thread(_cache_set, tenant_id, locked)
    return locked


async def invalidate_tenant_lock(tenant_id: str) -> None:
    """Evict the cache entry so the next lookup re-reads from the DB."""
    await asyncio.to_thread(_cache_del, tenant_id)
