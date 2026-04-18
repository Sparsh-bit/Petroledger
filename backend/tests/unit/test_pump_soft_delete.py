"""Pump soft-delete preserves the row and hides it from filtered queries."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.pump import Pump
from tests.fixtures.factories import OrganizationFactory, PumpFactory


@pytest.mark.asyncio
async def test_soft_delete_hides_pump_but_keeps_row(
    async_db_session, sample_tenant
):
    org = await OrganizationFactory.create(
        tenant_id=sample_tenant.id,
        name="Pump SD Org",
        slug="pump-sd-org",
        contact_email="pump-sd@test.com",
    )
    pump = await PumpFactory.create(org_id=org.id)

    pump.is_deleted = True
    pump.deleted_reason = "Decommissioned"
    await async_db_session.flush()

    active = (
        await async_db_session.execute(
            select(Pump).where(
                Pump.id == pump.id, Pump.is_deleted == False  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    assert active is None

    any_ = (
        await async_db_session.execute(select(Pump).where(Pump.id == pump.id))
    ).scalar_one_or_none()
    assert any_ is not None
    assert any_.is_deleted is True
    assert any_.deleted_reason == "Decommissioned"
