"""Seed the PetroLedger platform SUPERADMIN user.

Run from the ``backend/`` directory::

    python -m scripts.seed_superadmin

Creates (idempotently):
  - A "PetroLedger Platform" tenant with ACTIVE subscription, unlocked.
  - A SUPERADMIN user with email/password from env
    (``SUPERADMIN_EMAIL`` and ``SUPERADMIN_PASSWORD``).

Safe to re-run: existing rows are left untouched.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

sys.path.insert(0, ".")

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.tenant import Tenant
from app.models.user import User, UserRole

PLATFORM_TENANT_NAME = "PetroLedger Platform"
PLATFORM_OWNER_NAME = "Platform Operator"
PLATFORM_OWNER_PHONE = "0000000000"


async def seed() -> None:
    settings = get_settings()
    email = settings.SUPERADMIN_EMAIL
    password = settings.SUPERADMIN_PASSWORD

    if not email:
        raise SystemExit("[seed] SUPERADMIN_EMAIL is not set.")
    if not password:
        raise SystemExit(
            "[seed] SUPERADMIN_PASSWORD is not set. Export it in the environment "
            "before running this seed script."
        )

    async with async_session_factory() as db:
        # ── Platform tenant ───────────────────────────────────────────────
        tenant = (
            await db.execute(
                select(Tenant).where(Tenant.owner_email == email)
            )
        ).scalar_one_or_none()

        if tenant is None:
            tenant = Tenant(
                name=PLATFORM_TENANT_NAME,
                owner_name=PLATFORM_OWNER_NAME,
                owner_email=email,
                owner_phone=PLATFORM_OWNER_PHONE,
                subscription_plan="ENTERPRISE",
                max_orgs=999,
                is_active=True,
                is_locked=False,
                subscription_status="ACTIVE",
                monthly_price_inr=0,
            )
            db.add(tenant)
            await db.flush()
            print(f"[seed] Created tenant '{PLATFORM_TENANT_NAME}' id={tenant.id}")
        else:
            print(f"[seed] Reusing platform tenant id={tenant.id}")

        # ── Superadmin user ───────────────────────────────────────────────
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

        if user is not None:
            print(f"[seed] User '{email}' already exists — skipping.")
            await db.commit()
            return

        user = User(
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.SUPERADMIN,
            tenant_id=tenant.id,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        print(f"[seed] Created SUPERADMIN user '{email}' id={user.id}")
        print("[seed] Done. You can now log in to the provider portal.")


if __name__ == "__main__":
    asyncio.run(seed())
