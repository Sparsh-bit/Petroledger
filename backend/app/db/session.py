"""
PetroLedger — Async SQLAlchemy Session Management.

Creates the async engine and session factory from ``DATABASE_URL``
and exposes a ``get_db()`` FastAPI dependency.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# ── Async Engine ────────────────────────────────────────────────────────
_engine_kwargs: dict = {"echo": settings.is_development, "pool_pre_ping": True}

if "sqlite" not in settings.DATABASE_URL:
    is_local = any(h in settings.DATABASE_URL for h in ("localhost", "127.0.0.1"))
    ssl_mode = None if is_local else "require"

    is_pooler = any(p in settings.DATABASE_URL for p in (":6543", ":5432"))
    
    _engine_kwargs.update(
        pool_size=10 if not is_pooler else 20,
        max_overflow=20 if not is_pooler else 0,
        pool_recycle=3600,
        connect_args={
            "ssl": ssl_mode,
            "statement_cache_size": 0 if is_pooler else 100,
            "timeout": 60,
            "command_timeout": 60,
        },
    )

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# ── Session Factory ─────────────────────────────────────────────────────
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── FastAPI Dependency ──────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, ensuring cleanup on exit."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
