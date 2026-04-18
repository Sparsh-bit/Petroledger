"""
PetroLedger — Factory-Boy Factories for Test Fixtures.

Provides async-compatible factories for all core ORM models.

factory-boy has no native async support, so we use a module-level
session holder and a custom ``_create`` classmethod that delegates
to ``session.add()`` / ``await session.flush()``.

Usage in conftest::

    from tests.fixtures.factories import set_session, OrganizationFactory
    set_session(async_db_session)
    org = await OrganizationFactory.create()
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import factory

from app.models.organization import Organization
from app.models.pump import FuelType, Nozzle, Pump
from app.models.shift import Shift, ShiftStatus
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.worker import Worker

# ── Async session holder ────────────────────────────────────────────────

_session = None


def set_session(session) -> None:
    """Inject the current async test session for factory ``_create`` calls."""
    global _session
    _session = session


def get_session():
    """Return the active test session (raises if not set)."""
    if _session is None:
        raise RuntimeError(
            "Factory session not set. Call set_session(db) in your fixture."
        )
    return _session


# ── Base async factory ──────────────────────────────────────────────────


class AsyncFactory(factory.Factory):
    """
    Base factory that persists objects via the async SQLAlchemy session.

    All subclasses must call ``await XxxFactory.create(...)`` instead of
    the synchronous ``XxxFactory()``.
    """

    class Meta:
        abstract = True

    @classmethod
    async def create(cls, **kwargs):
        """Build the object, add to session, flush, and return."""
        obj = cls.build(**kwargs)
        session = get_session()
        session.add(obj)
        await session.flush()
        return obj

    @classmethod
    async def create_batch(cls, size: int, **kwargs):
        """Create *size* instances."""
        return [await cls.create(**kwargs) for _ in range(size)]


# ── Tenant ──────────────────────────────────────────────────────────────


class TenantFactory(AsyncFactory):
    class Meta:
        model = Tenant

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"Test Tenant #{n}")
    owner_name = factory.Sequence(lambda n: f"Owner {n}")
    owner_phone = "9876543210"
    owner_email = factory.Sequence(lambda n: f"tenant{n}@testfuel.com")
    subscription_plan = "BASIC"
    max_orgs = 5
    is_active = True


# ── Organization ────────────────────────────────────────────────────────


class OrganizationFactory(AsyncFactory):
    class Meta:
        model = Organization

    id = factory.LazyFunction(uuid.uuid4)
    tenant_id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"Fuel Station #{n}")
    slug = factory.Sequence(lambda n: f"fuel-station-{n}")
    contact_email = factory.Sequence(lambda n: f"admin{n}@testfuel.com")
    is_active = True


# ── User ────────────────────────────────────────────────────────────────


class UserFactory(AsyncFactory):
    class Meta:
        model = User

    id = factory.LazyFunction(uuid.uuid4)
    tenant_id = factory.LazyFunction(uuid.uuid4)
    email = factory.Sequence(lambda n: f"user{n}@testfuel.com")
    phone = None
    hashed_password = (
        "$2b$12$dummyhashfortesting000000000000000000000000000000"
    )
    role = UserRole.OWNER
    org_id = factory.LazyAttribute(lambda o: uuid.uuid4())
    is_active = True


# ── Pump ────────────────────────────────────────────────────────────────


class PumpFactory(AsyncFactory):
    class Meta:
        model = Pump

    id = factory.LazyFunction(uuid.uuid4)
    org_id = factory.LazyAttribute(lambda o: uuid.uuid4())
    name = factory.Sequence(lambda n: f"Pump-{n:02d}")
    location = "Bay A"
    nozzle_count = 2
    is_active = True

    @classmethod
    async def create(cls, *, with_nozzles: bool = True, **kwargs):
        """Create pump and optionally add petrol + diesel nozzles."""
        pump = cls.build(**kwargs)
        session = get_session()
        session.add(pump)
        await session.flush()

        if with_nozzles:
            for i, ft in enumerate([FuelType.PETROL, FuelType.DIESEL], start=1):
                nozzle = Nozzle(
                    id=uuid.uuid4(),
                    pump_id=pump.id,
                    nozzle_number=i,
                    fuel_type=ft,
                )
                session.add(nozzle)
            await session.flush()

        return pump


# ── Worker ──────────────────────────────────────────────────────────────


class WorkerFactory(AsyncFactory):
    class Meta:
        model = Worker

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyAttribute(lambda o: uuid.uuid4())
    pump_id = factory.LazyAttribute(lambda o: uuid.uuid4())
    employee_code = factory.Sequence(lambda n: f"EMP{n:03d}")
    joined_date = date(2025, 1, 1)


# ── Shift ───────────────────────────────────────────────────────────────


class ShiftFactory(AsyncFactory):
    class Meta:
        model = Shift

    id = factory.LazyFunction(uuid.uuid4)
    pump_id = factory.LazyAttribute(lambda o: uuid.uuid4())
    worker_id = factory.LazyAttribute(lambda o: uuid.uuid4())
    start_time = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    end_time = None
    status = ShiftStatus.ACTIVE
