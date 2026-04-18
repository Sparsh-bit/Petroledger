"""
Integration tests for the reconciliation API endpoints.

Tests hit real endpoints via HTTPX AsyncClient against an in-memory SQLite
database (see conftest.py fixtures).  We seed the DB with Shift + transaction
data, then call the reconciliation API and assert on the response.

Note: SQLite does not support PostgreSQL-specific syntax (e.g. ON CONFLICT).
Tests that exercise bulk_insert (deduplication) are skipped on SQLite.

IMPORTANT: All JWT tokens must use ``sample_user.id`` as the ``sub`` claim.
``get_current_active_user`` performs a live DB lookup — random UUIDs return 401.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fms import CashEntry, FmsTransaction, FmsTxnStatus
from app.models.reconciliation import ReconciliationResult, ReconciliationStatus
from app.models.shift import Shift, ShiftStatus


# ── Helpers ──────────────────────────────────────────────────────────────


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token_for(user) -> str:
    """Create a valid JWT for an existing DB user."""
    from app.core.security import create_access_token
    # UserRole is a StrEnum; SQLite may return a plain str — str() covers both
    return create_access_token({"sub": str(user.id), "role": str(user.role)})


async def _create_completed_shift(
    db: AsyncSession,
    pump_id: uuid.UUID,
    worker_id: uuid.UUID,
) -> Shift:
    """Insert a COMPLETED shift (engine requires non-ACTIVE state)."""
    shift = Shift(
        id=uuid.uuid4(),
        pump_id=pump_id,
        worker_id=worker_id,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        status=ShiftStatus.COMPLETED,
    )
    db.add(shift)
    await db.flush()
    return shift


async def _add_fms_transaction(
    db: AsyncSession,
    shift_id: uuid.UUID,
    nozzle_id: uuid.UUID,
    amount: Decimal,
    volume: Decimal = Decimal("100"),
) -> FmsTransaction:
    txn = FmsTransaction(
        id=uuid.uuid4(),
        shift_id=shift_id,
        nozzle_id=nozzle_id,
        txn_reference=f"REF-{uuid.uuid4().hex[:8]}",
        txn_date=datetime.now(timezone.utc).date(),
        txn_time=datetime.now(timezone.utc).time(),
        volume_litres=volume,
        unit_price=Decimal("100"),
        amount=amount,
        product_code="MS",
        raw_payment_mode="CASH",
        status=FmsTxnStatus.COMPLETED,
        content_hash=uuid.uuid4().hex,
        is_deleted=False,
    )
    db.add(txn)
    await db.flush()
    return txn


async def _add_cash_entry(
    db: AsyncSession,
    shift_id: uuid.UUID,
    physical_cash: Decimal,
) -> CashEntry:
    entry = CashEntry(
        id=uuid.uuid4(),
        shift_id=shift_id,
        physical_cash=physical_cash,
        submitted_by=uuid.uuid4(),
        submitted_at=datetime.now(timezone.utc),
        is_locked=False,
        is_deleted=False,
    )
    db.add(entry)
    await db.flush()
    return entry


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestReconciliationAPI:

    async def test_get_result_not_found(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_shift,
        sample_user,
    ):
        """GET /reconciliation/shifts/{id} returns 404 when not yet reconciled."""
        response = await test_client.get(
            f"/api/v1/reconciliation/shifts/{sample_shift.id}",
            headers=_auth_headers(_token_for(sample_user)),
        )
        assert response.status_code == 404

    async def test_reconcile_active_shift_fails(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_shift,
        sample_user,
    ):
        """POST run on an ACTIVE shift returns 422 — must be COMPLETED first."""
        # sample_shift is ACTIVE by default
        response = await test_client.post(
            f"/api/v1/reconciliation/shifts/{sample_shift.id}/run",
            json={"shift_id": str(sample_shift.id), "actual_cash": "5000.00"},
            headers=_auth_headers(_token_for(sample_user)),
        )
        assert response.status_code == 422

    async def test_reconcile_completed_shift_perfect_match(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_pump,
        sample_shift,
        sample_user,
    ):
        """
        Reconcile a COMPLETED shift with FMS=10000, no digital, cash=10000.
        Expected: variance=0, status=COMPLETED.
        """
        from sqlalchemy import select

        # Advance shift to COMPLETED
        shift = (
            await async_db_session.execute(
                select(Shift).where(Shift.id == sample_shift.id)
            )
        ).scalar_one()
        shift.status = ShiftStatus.COMPLETED
        shift.end_time = datetime.now(timezone.utc)
        await async_db_session.flush()

        # Add nozzle (PumpFactory creates with 2 nozzles)
        from app.models.pump import Nozzle
        nozzle = (
            await async_db_session.execute(
                select(Nozzle).where(Nozzle.pump_id == sample_pump.id).limit(1)
            )
        ).scalar_one_or_none()

        if nozzle is None:
            pytest.skip("No nozzle found — factory did not create nozzles")

        # FMS total = 10,000
        await _add_fms_transaction(
            async_db_session, shift.id, nozzle.id, Decimal("10000")
        )
        # Cash submitted = 10,000 (no digital payments)
        actual_cash = Decimal("10000.00")

        response = await test_client.post(
            f"/api/v1/reconciliation/shifts/{shift.id}/run",
            json={
                "shift_id": str(shift.id),
                "actual_cash": str(actual_cash),
            },
            headers=_auth_headers(_token_for(sample_user)),
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert Decimal(data["variance"]) == Decimal("0")
        assert data["status"] in ("completed", "COMPLETED")

    async def test_reconcile_completed_shift_shortage(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_pump,
        sample_shift,
        sample_user,
    ):
        """
        Reconcile with FMS=10000, no digital, cash=9500 → shortage of 500.
        """
        from sqlalchemy import select

        shift = (
            await async_db_session.execute(
                select(Shift).where(Shift.id == sample_shift.id)
            )
        ).scalar_one()
        shift.status = ShiftStatus.COMPLETED
        shift.end_time = datetime.now(timezone.utc)
        await async_db_session.flush()

        from app.models.pump import Nozzle
        nozzle = (
            await async_db_session.execute(
                select(Nozzle).where(Nozzle.pump_id == sample_pump.id).limit(1)
            )
        ).scalar_one_or_none()
        if nozzle is None:
            pytest.skip("No nozzle found")

        await _add_fms_transaction(
            async_db_session, shift.id, nozzle.id, Decimal("10000")
        )

        response = await test_client.post(
            f"/api/v1/reconciliation/shifts/{shift.id}/run",
            json={
                "shift_id": str(shift.id),
                "actual_cash": "9500.00",
            },
            headers=_auth_headers(_token_for(sample_user)),
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert Decimal(data["variance"]) == Decimal("500")

    async def test_get_result_after_reconcile(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_pump,
        sample_shift,
        sample_user,
    ):
        """GET after a successful reconciliation returns the stored result."""
        from sqlalchemy import select

        shift = (
            await async_db_session.execute(
                select(Shift).where(Shift.id == sample_shift.id)
            )
        ).scalar_one()
        shift.status = ShiftStatus.COMPLETED
        shift.end_time = datetime.now(timezone.utc)
        await async_db_session.flush()

        from app.models.pump import Nozzle
        nozzle = (
            await async_db_session.execute(
                select(Nozzle).where(Nozzle.pump_id == sample_pump.id).limit(1)
            )
        ).scalar_one_or_none()
        if nozzle is None:
            pytest.skip("No nozzle found")

        await _add_fms_transaction(
            async_db_session, shift.id, nozzle.id, Decimal("5000")
        )

        token = _token_for(sample_user)

        # Reconcile
        run_resp = await test_client.post(
            f"/api/v1/reconciliation/shifts/{shift.id}/run",
            json={"shift_id": str(shift.id), "actual_cash": "5000.00"},
            headers=_auth_headers(token),
        )
        assert run_resp.status_code == 200, run_resp.text

        # Now GET
        get_resp = await test_client.get(
            f"/api/v1/reconciliation/shifts/{shift.id}",
            headers=_auth_headers(token),
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["shift_id"] == str(shift.id)
        assert "variance" in data

    async def test_reconcile_requires_auth(
        self,
        test_client: AsyncClient,
        sample_shift,
    ):
        """POST without a token returns 401 (HTTPBearer rejects unauthenticated)."""
        response = await test_client.post(
            f"/api/v1/reconciliation/shifts/{sample_shift.id}/run",
            json={"shift_id": str(sample_shift.id), "actual_cash": "1000.00"},
        )
        assert response.status_code in (401, 403)

    async def test_worker_cannot_run_reconciliation(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_shift,
        sample_tenant,
        sample_org,
    ):
        """A WORKER role cannot trigger reconciliation (OWNER/ADMIN/MANAGER only)."""
        from app.models.user import UserRole
        from tests.fixtures.factories import UserFactory

        worker_user = await UserFactory.create(
            tenant_id=sample_tenant.id,
            role=UserRole.WORKER,
            org_id=sample_org.id,
        )
        token = _token_for(worker_user)

        response = await test_client.post(
            f"/api/v1/reconciliation/shifts/{sample_shift.id}/run",
            json={"shift_id": str(sample_shift.id), "actual_cash": "1000.00"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 403
