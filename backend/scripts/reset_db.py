"""Wipe all business data and reseed a single SUPERADMIN user.

Use from the ``backend/`` directory::

    python -m scripts.reset_db

- Truncates every table (respecting FKs via ``TRUNCATE ... CASCADE``) EXCEPT
  Alembic's ``alembic_version`` table so migrations stay applied.
- Then invokes the same flow as ``seed_superadmin`` to recreate the
  platform tenant and the SUPERADMIN operator.

Requires ``SUPERADMIN_EMAIL`` and ``SUPERADMIN_PASSWORD`` env vars.
Destroys data — use only on dev/staging or on a freshly-empty prod DB.
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

sys.path.insert(0, ".")

from app.db.session import async_session_factory
from scripts.seed_superadmin import seed


SKIP_TABLES = {"alembic_version"}


async def reset() -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public'"
            )
        )
        tables = [r[0] for r in result.all() if r[0] not in SKIP_TABLES]
        if not tables:
            print("[reset] No tables to truncate.")
        else:
            quoted = ", ".join(f'"{t}"' for t in tables)
            await db.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
            await db.commit()
            print(f"[reset] Truncated {len(tables)} table(s).")

    await seed()


if __name__ == "__main__":
    asyncio.run(reset())
