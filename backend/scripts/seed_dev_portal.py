#!/usr/bin/env python3
"""
Seed the database with developer portal credentials.
Usage: uv run python -m scripts.seed_dev_portal
"""

import asyncio
import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_dev_portal")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.tenant import Tenant


async def seed_dev_portal():
    settings = get_settings()

    superadmin_password = settings.SUPERADMIN_PASSWORD or os.environ.get("SUPERADMIN_PASSWORD", "")
    if not superadmin_password:
        logger.warning("SUPERADMIN_PASSWORD not set. Using default: Concilio@2026")
        superadmin_password = "Concilio@2026"

    url = settings.DATABASE_URL
    logger.info(f"Targeting Database URL: {url.split('@')[-1]}")
    
    is_local = any(h in url for h in ("localhost", "127.0.0.1"))
    ssl_mode = None if is_local else "require"
    
    # Very generous timeouts for remote Supabase connections
    connect_args: dict = {
        "ssl": ssl_mode,
        "timeout": 120,                
        "command_timeout": 120,        
        "server_settings": {
            "statement_timeout": "120000",
        },
    }
    
    # Critical for PgBouncer/Supabase Pooler
    if ":6543" in url or ":5432" in url:
        logger.info("Enabling pooler compatibility mode (statement_cache_size=0)")
        connect_args["statement_cache_size"] = 0

    engine = create_async_engine(
        url,
        echo=True,
        poolclass=NullPool,
        connect_args=connect_args,
    )

    try:
        logger.info("Attempting to verify connection...")
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✓ Database connection verified")
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        await engine.dispose()
        raise

    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_factory() as session:
        try:
            logger.info("Checking for 'Concilio Solutions' tenant...")
            result = await session.execute(
                select(Tenant).where(Tenant.name == "Concilio Solutions")
            )
            tenant = result.scalar_one_or_none()

            if not tenant:
                logger.info("📦 Creating dev tenant 'Concilio Solutions'...")
                tenant = Tenant(
                    name="Concilio Solutions",
                    owner_name="Developer",
                    owner_phone="+910000000000",
                    owner_email=settings.SUPERADMIN_EMAIL,
                    subscription_plan="BASIC",
                    max_orgs=5,
                    is_active=True,
                )
                session.add(tenant)
                await session.flush()
            else:
                logger.info("✓ Dev tenant already exists")

            logger.info(f"Checking for user: {settings.SUPERADMIN_EMAIL}")
            result = await session.execute(
                select(User).where(User.email == settings.SUPERADMIN_EMAIL)
            )
            user = result.scalar_one_or_none()

            if not user:
                logger.info("👤 Creating dev portal user...")
                user = User(
                    email=settings.SUPERADMIN_EMAIL,
                    phone="+910000000000",
                    hashed_password=hash_password(superadmin_password),
                    role=UserRole.ADMIN,
                    tenant_id=tenant.id,
                    org_id=None,
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                logger.info(f"   ✅ User created: {settings.SUPERADMIN_EMAIL}")
            else:
                logger.info("✓ User exists. Updating password...")
                user.hashed_password = hash_password(superadmin_password)
                await session.flush()

            await session.commit()
            logger.info("✅ All changes committed successfully!")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Transaction failed: {e}")
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_dev_portal())
