"""
PetroLedger — Alembic Environment Configuration (Async).

Reads DATABASE_URL from ``app.core.config`` and uses
``run_async`` + ``run_sync`` to drive migrations with an
``AsyncEngine``.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings

# Import Base so that Alembic's autogenerate sees all table metadata.
# Each model file registers itself on Base.metadata when imported.
from app.db.base import Base  # noqa: F401
import app.models  # noqa: F401 — importing the package forces registration of all models on Base.metadata

# Alembic Config object — provides access to alembic.ini values.
config = context.config

# Set up Python logging from the ini file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Tell Alembic which metadata to compare against.
target_metadata = Base.metadata

# Inject the real database URL (replaces the ini placeholder).
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))


# ── Offline Mode ────────────────────────────────────────────────────────


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' (SQL-generation) mode.

    Generates SQL statements to stdout without connecting to a database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online Mode (Async) ────────────────────────────────────────────────


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """Synchronous callback executed inside ``run_sync``."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations via ``run_sync``."""
    url = settings.DATABASE_URL
    is_local = any(h in url for h in ("localhost", "127.0.0.1"))
    connect_args: dict = {"ssl": None if is_local else "require"}
    if ":6543" in url:
        connect_args["statement_cache_size"] = 0

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an async engine."""
    asyncio.run(run_async_migrations())


# ── Dispatch ────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
