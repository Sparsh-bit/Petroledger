"""Subscription-plan org limit enforcement."""

from __future__ import annotations

import pytest

from app.core.exceptions import TenantForbiddenError
from app.core.tenant import check_org_limit, get_tenant_org_count
from tests.fixtures.factories import OrganizationFactory


@pytest.mark.asyncio
async def test_org_limit_blocks_over_plan_max(async_db_session, sample_tenant):
    """BASIC plan (max_orgs=1): second org creation must be rejected."""
    sample_tenant.max_orgs = 1
    await async_db_session.flush()

    await OrganizationFactory.create(
        tenant_id=sample_tenant.id,
        name="Org 1",
        slug="org-1",
        contact_email="o1@test.com",
    )

    assert await get_tenant_org_count(sample_tenant.id, async_db_session) == 1

    with pytest.raises(TenantForbiddenError):
        await check_org_limit(sample_tenant, async_db_session)


@pytest.mark.asyncio
async def test_inactive_org_does_not_count(async_db_session, sample_tenant):
    """Deactivating an org should free up a plan slot."""
    sample_tenant.max_orgs = 1
    await async_db_session.flush()

    org = await OrganizationFactory.create(
        tenant_id=sample_tenant.id,
        name="Soon Inactive",
        slug="soon-inactive",
        contact_email="si@test.com",
    )
    org.is_active = False
    await async_db_session.flush()

    # Inactive → count is 0, limit check passes.
    assert await get_tenant_org_count(sample_tenant.id, async_db_session) == 0
    await check_org_limit(sample_tenant, async_db_session)  # must not raise
