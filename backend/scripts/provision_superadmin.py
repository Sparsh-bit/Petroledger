"""Nuke users + tenants, then create ONE SUPERADMIN from command-line args.

Usage (from ``backend/``):

    python -m scripts.provision_superadmin <email> <password>

Destroys all user/tenant data. Use only when you want a completely fresh DB.
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

sys.path.insert(0, ".")

from app.core.security import hash_password
from app.db.session import engine as async_engine
from app.db.session import async_session_factory
from app.models.tenant import Tenant
from app.models.user import User, UserRole


async def provision(email: str, password: str) -> None:
    # Step 1 — ensure the Postgres enum has every role the Python model knows.
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction, so open a
    # dedicated AUTOCOMMIT connection.
    async with async_engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        for value in ("superadmin", "provider", "owner", "admin", "manager", "worker"):
            await conn.execute(
                text(f"ALTER TYPE user_role ADD VALUE IF NOT EXISTS '{value}'")
            )
        print("[provision] Ensured user_role enum values present.")

    async with async_session_factory() as db:
        # Wipe every table except alembic_version
        res = await db.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        )
        tables = [r[0] for r in res.all() if r[0] != "alembic_version"]
        if tables:
            quoted = ", ".join(f'"{t}"' for t in tables)
            await db.execute(
                text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
            )
            print(f"[provision] Truncated {len(tables)} table(s).")

        tenant = Tenant(
            name="PetroLedger Platform",
            owner_name="Platform Operator",
            owner_email=email,
            owner_phone="0000000000",
            subscription_plan="ENTERPRISE",
            max_orgs=999,
            is_active=True,
            is_locked=False,
            subscription_status="ACTIVE",
            monthly_price_inr=0,
        )
        db.add(tenant)
        await db.flush()

        user = User(
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.SUPERADMIN,
            tenant_id=tenant.id,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        print(f"[provision] Created SUPERADMIN '{email}' (tenant {tenant.id}).")
        print("[provision] Login at /provider with the email + password above.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m scripts.provision_superadmin <email> <password>")
    asyncio.run(provision(sys.argv[1], sys.argv[2]))
