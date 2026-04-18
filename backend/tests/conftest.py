"""
PetroLedger — Shared Pytest Fixtures.

Provides:
    - ``event_loop``      — session-scoped async event loop
    - ``test_settings``   — override settings for test environment (SQLite)
    - ``async_db_session`` — async SQLAlchemy session connected to test DB
    - ``test_client``     — HTTPX ``AsyncClient`` wired to the FastAPI app
    - ``sample_org``, ``sample_user`` (owner), ``sample_pump``,
      ``sample_shift`` — DB fixtures using **factory-boy**
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, clear_settings_cache
from app.db.base import Base
from tests.fixtures.factories import (
    OrganizationFactory,
    PumpFactory,
    ShiftFactory,
    TenantFactory,
    UserFactory,
    WorkerFactory,
    set_session,
)

# ── Async event loop ────────────────────────────────────────────────────


@pytest.fixture(autouse=True, scope="session")
def _clear_settings_cache():
    """Evict the lru_cache on get_settings() so pytest-env vars take effect."""
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Test settings ───────────────────────────────────────────────────────

_TEST_ENV = {
    "DATABASE_URL": "sqlite+aiosqlite:///",
    "SECRET_KEY": "test-secret-key-for-jwt",
    "REDIS_URL": "redis://localhost:6379/15",
    "ENVIRONMENT": "dev",
    "SUPERADMIN_EMAIL": "test-superadmin@example.com",
}


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Settings instance with test-safe overrides."""
    return Settings(**_TEST_ENV)  # type: ignore[arg-type]


# ── Async DB session ───────────────────────────────────────────────────

# StaticPool + check_same_thread=False ensures ALL connections share the
# same in-memory SQLite database (otherwise each connection is isolated).
_test_engine = create_async_engine(
    "sqlite+aiosqlite:///",
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
_TestSessionLocal = async_sessionmaker(
    _test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture
async def async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async session backed by a fresh in-memory SQLite DB.
    All tables are created before the test and dropped after.
    The session is also injected into factory-boy factories via
    ``set_session()``.
    """
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _TestSessionLocal() as session:
        set_session(session)
        yield session
        set_session(None)

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── HTTPX test client ──────────────────────────────────────────────────


@pytest_asyncio.fixture
async def test_client(async_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Async test client that overrides the DB dependency with the
    in-memory test session.
    """
    from app.db.session import get_db
    from app.main import app

    async def _override_get_db():
        yield async_db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ── Sample entities (factory-boy) ───────────────────────────────────────


@pytest_asyncio.fixture
async def sample_tenant(async_db_session: AsyncSession):
    """Create a test tenant (required parent for orgs and users)."""
    return await TenantFactory.create(
        name="Test Tenant",
        owner_email="tenant@testfuel.com",
    )


@pytest_asyncio.fixture
async def sample_org(async_db_session: AsyncSession, sample_tenant):
    """Create a test organisation via OrganizationFactory."""
    return await OrganizationFactory.create(
        tenant_id=sample_tenant.id,
        name="Test Fuel Station",
        slug="test-fuel-station",
        contact_email="admin@testfuel.com",
    )


@pytest_asyncio.fixture
async def sample_user(async_db_session: AsyncSession, sample_org, sample_tenant):
    """Create a test owner user linked to the sample org via UserFactory."""
    return await UserFactory.create(
        tenant_id=sample_tenant.id,
        email="owner@testfuel.com",
        role="owner",
        org_id=sample_org.id,
    )


@pytest_asyncio.fixture
async def sample_pump(async_db_session: AsyncSession, sample_org):
    """Create a test pump with 2 nozzles (petrol + diesel) via PumpFactory."""
    return await PumpFactory.create(
        org_id=sample_org.id,
        name="Pump-01",
        location="Bay A",
    )


@pytest_asyncio.fixture
async def sample_shift(async_db_session: AsyncSession, sample_pump, sample_user):
    """Create a test shift linked to the sample pump and a new worker."""
    worker = await WorkerFactory.create(
        user_id=sample_user.id,
        pump_id=sample_pump.id,
        employee_code="EMP001",
    )
    return await ShiftFactory.create(
        pump_id=sample_pump.id,
        worker_id=worker.id,
    )
