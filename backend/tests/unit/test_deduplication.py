"""Tests for tenant-scoped transaction deduplication.

Guarantees that `content_hash` collisions between two different orgs do
not falsely flag a transaction as a duplicate (and, conversely, that
collisions within the same org are flagged).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models.transaction import UPITransaction
from app.services.deduplication import DeduplicationService
from tests.fixtures.factories import (
    OrganizationFactory,
    PumpFactory,
    ShiftFactory,
)


@pytest.mark.asyncio
async def test_upi_duplicate_scoped_per_org(async_db_session, sample_tenant):
    """Same content_hash in org_A must not mark org_B's insert as duplicate."""
    svc = DeduplicationService()

    org_a = await OrganizationFactory.create(
        tenant_id=sample_tenant.id, name="Org A", slug="org-a",
        contact_email="a@test.com",
    )
    org_b = await OrganizationFactory.create(
        tenant_id=sample_tenant.id, name="Org B", slug="org-b",
        contact_email="b@test.com",
    )
    pump_a = await PumpFactory.create(org_id=org_a.id)
    shift_a = await ShiftFactory.create(pump_id=pump_a.id)

    content_hash = "a" * 64
    txn = UPITransaction(
        id=uuid.uuid4(),
        org_id=org_a.id,
        shift_id=shift_a.id,
        amount=Decimal("100.00"),
        upi_ref="TXN1",
        bank="HDFC",
        timestamp=datetime.now(timezone.utc),
        content_hash=content_hash,
    )
    async_db_session.add(txn)
    await async_db_session.flush()

    # Org A sees the duplicate.
    assert await svc.check_upi_duplicate(
        async_db_session, content_hash, org_a.id
    ) is True

    # Org B does NOT — the hash belongs to a different org.
    assert await svc.check_upi_duplicate(
        async_db_session, content_hash, org_b.id
    ) is False
