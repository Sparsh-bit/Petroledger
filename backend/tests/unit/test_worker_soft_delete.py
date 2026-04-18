"""Worker soft-delete preserves the DB row and hides it from list queries."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.models.worker import Worker
from tests.fixtures.factories import (
    OrganizationFactory,
    PumpFactory,
    UserFactory,
    WorkerFactory,
)


@pytest.mark.asyncio
async def test_soft_delete_hides_worker_but_keeps_row(
    async_db_session, sample_tenant
):
    org = await OrganizationFactory.create(
        tenant_id=sample_tenant.id,
        name="Soft Delete Org",
        slug="soft-delete-org",
        contact_email="sd@test.com",
    )
    pump = await PumpFactory.create(org_id=org.id)
    user = await UserFactory.create(tenant_id=sample_tenant.id)
    worker = await WorkerFactory.create(
        user_id=user.id,
        pump_id=pump.id,
        employee_code="EMP-SD-001",
        joined_date=date(2026, 1, 1),
    )

    # Soft delete.
    worker.is_deleted = True
    worker.deleted_reason = "Resigned"
    await async_db_session.flush()

    # Not returned by a filtered list query.
    active = (
        await async_db_session.execute(
            select(Worker).where(
                Worker.id == worker.id, Worker.is_deleted == False  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    assert active is None

    # But the row still exists.
    any_ = (
        await async_db_session.execute(
            select(Worker).where(Worker.id == worker.id)
        )
    ).scalar_one_or_none()
    assert any_ is not None
    assert any_.is_deleted is True
    assert any_.deleted_reason == "Resigned"
