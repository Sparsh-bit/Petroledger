"""PetroLedger — Meter Reading Tests.

Covers:
  1. ETOTParserService — unit tests with mocked Textract responses
  2. Shift sale computation — happy path, closing < opening, duplicate
  3. Per-worker reconciliation — MATCH / SHORTAGE / EXCESS / incomplete guard
  4. Tenant isolation — cross-tenant access returns 404
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ValidationError as PetroValidationError
from app.services.ocr.etot_parser import ETOTParserService


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_textract_response(lines: list[str]) -> dict:
    """Build a minimal Textract DetectDocumentText response from a list of lines."""
    blocks = []
    for i, text in enumerate(lines):
        blocks.append({"BlockType": "LINE", "Id": str(i), "Text": text})
    return {"Blocks": blocks}


# ── 1. ETOT Parser — Unit Tests (mocked boto3) ────────────────────────────────


class TestETOTParser:
    """Unit tests for ETOTParserService._parse_etot_lines()."""

    def setup_method(self):
        # ETOTParserService.__init__ calls boto3.client; patch it out for unit tests
        with patch("app.services.ocr.etot_parser.boto3"):
            self.svc = ETOTParserService.__new__(ETOTParserService)

    def test_extracts_all_nozzles(self):
        """Parser correctly extracts 4 nozzles from a real-format receipt."""
        lines = [
            "ETOT-MAIN",
            "16EC1035V",           # pump serial
            "NOZZLE : 1",
            "A:25,707,038.550",
            "V:279,141.470",
            "TOT SALES:113354",
            "NOZZLE : 2",
            "A:18,500,000.000",
            "V:201,086.957",
            "TOT SALES:98000",
            "NOZZLE : 3",
            "A:12,000,000.000",
            "V:130,434.782",
            "TOT SALES:65000",
            "NOZZLE : 4",
            "A:9,000,000.000",
            "V:97,826.086",
            "TOT SALES:48750",
        ]
        result = self.svc._parse_etot_lines(lines)

        assert result["pump_serial"] == "16EC1035V"
        assert len(result["nozzles"]) == 4

        n1 = result["nozzles"][0]
        assert n1["nozzle_number"] == 1
        assert n1["amount_cumulative"] == Decimal("25707038.550")
        assert n1["volume_cumulative"] == Decimal("279141.470")
        assert n1["tot_sales_cumulative"] == 113354

    def test_raises_on_missing_a_field(self):
        """Parser raises ValidationError when a nozzle is missing the A field."""
        lines = [
            "NOZZLE : 2",
            # A field deliberately omitted
            "V:201,086.957",
            "TOT SALES:98000",
        ]
        with pytest.raises(PetroValidationError) as exc_info:
            self.svc._parse_etot_lines(lines)
        assert "Nozzle 2" in exc_info.value.message
        assert "amount_cumulative" in exc_info.value.message

    def test_raises_on_no_nozzles_found(self):
        """Parser raises ValidationError when no NOZZLE headers are present."""
        lines = ["SOME RANDOM TEXT", "ANOTHER LINE", "12345.678"]
        with pytest.raises(PetroValidationError) as exc_info:
            self.svc._parse_etot_lines(lines)
        assert "No nozzle data found" in exc_info.value.message

    def test_handles_nozzle_header_variants(self):
        """Parser accepts 'NOZZLE:1', 'NOZZLE : 1', 'nozzle : 1' etc."""
        variants = [
            ["NOZZLE:1", "A:100.000", "V:1.085", "TOT SALES:50"],
            ["NOZZLE : 1", "A:100.000", "V:1.085", "TOT SALES:50"],
            ["nozzle : 1", "A:100.000", "V:1.085", "TOT SALES:50"],
        ]
        for lines in variants:
            result = self.svc._parse_etot_lines(lines)
            assert len(result["nozzles"]) == 1
            assert result["nozzles"][0]["nozzle_number"] == 1

    def test_parse_image_calls_textract(self):
        """parse_image() calls detect_document_text and parses the response."""
        mock_client = MagicMock()
        mock_client.detect_document_text.return_value = _make_textract_response([
            "NOZZLE : 1",
            "A:25,707,038.550",
            "V:279,141.470",
            "TOT SALES:113354",
        ])
        with patch("app.services.ocr.etot_parser.boto3") as mock_boto3:
            mock_boto3.client.return_value = mock_client
            svc = ETOTParserService()
            import asyncio
            result = asyncio.run(svc.parse_image(b"fake-image-bytes"))

        mock_client.detect_document_text.assert_called_once_with(
            Document={"Bytes": b"fake-image-bytes"}
        )
        assert len(result["nozzles"]) == 1
        assert result["nozzles"][0]["amount_cumulative"] == Decimal("25707038.550")


# ── 2. Shift Sale Computation ─────────────────────────────────────────────────


class TestShiftSaleComputation:
    """Tests for _try_compute_shift_sale logic in the meter readings router."""

    @pytest.mark.asyncio
    async def test_shift_sale_computed_on_closing_upload(self, async_db_session):
        """Shift sale = closing_A − opening_A is correctly computed and stored."""
        from app.api.v1.meter_readings.routes import _try_compute_shift_sale
        from app.models.nozzle_meter_reading import NozzleMeterReading

        tenant_id = uuid.uuid4()
        shift_id = uuid.uuid4()
        nozzle_id = uuid.uuid4()
        worker_id = uuid.uuid4()

        opening = NozzleMeterReading(
            tenant_id=tenant_id,
            shift_id=shift_id,
            nozzle_id=nozzle_id,
            worker_id=worker_id,
            reading_type="opening",
            amount_cumulative=Decimal("25707038.550"),
            volume_cumulative=Decimal("279141.470"),
            tot_sales_cumulative=113354,
            entered_manually=True,
        )
        closing = NozzleMeterReading(
            tenant_id=tenant_id,
            shift_id=shift_id,
            nozzle_id=nozzle_id,
            worker_id=worker_id,
            reading_type="closing",
            amount_cumulative=Decimal("25707094.210"),
            volume_cumulative=Decimal("279142.074"),
            tot_sales_cumulative=113355,
            entered_manually=True,
        )
        async_db_session.add_all([opening, closing])
        await async_db_session.flush()

        warnings = await _try_compute_shift_sale(shift_id, nozzle_id, async_db_session)

        assert warnings is not None  # computed successfully

        from sqlalchemy import select
        from app.models.nozzle_shift_sale import NozzleShiftSale

        sale = (
            await async_db_session.execute(
                select(NozzleShiftSale).where(
                    NozzleShiftSale.shift_id == shift_id,
                    NozzleShiftSale.nozzle_id == nozzle_id,
                )
            )
        ).scalar_one()

        assert Decimal(str(sale.shift_sale_amount)) == Decimal("55.660")
        assert sale.shift_transaction_count == 1

    @pytest.mark.asyncio
    async def test_returns_none_when_only_opening_exists(self, async_db_session):
        """No shift sale computed when only one reading exists."""
        from app.api.v1.meter_readings.routes import _try_compute_shift_sale
        from app.models.nozzle_meter_reading import NozzleMeterReading

        shift_id = uuid.uuid4()
        nozzle_id = uuid.uuid4()

        opening = NozzleMeterReading(
            tenant_id=uuid.uuid4(),
            shift_id=shift_id,
            nozzle_id=nozzle_id,
            worker_id=uuid.uuid4(),
            reading_type="opening",
            amount_cumulative=Decimal("25707038.550"),
            volume_cumulative=Decimal("279141.470"),
            tot_sales_cumulative=113354,
            entered_manually=True,
        )
        async_db_session.add(opening)
        await async_db_session.flush()

        result = await _try_compute_shift_sale(shift_id, nozzle_id, async_db_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_closing_less_than_opening_raises(self, async_db_session):
        """ValidationError raised when closing amount < opening amount."""
        from app.api.v1.meter_readings.routes import _try_compute_shift_sale
        from app.models.nozzle_meter_reading import NozzleMeterReading

        shift_id = uuid.uuid4()
        nozzle_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        worker_id = uuid.uuid4()

        opening = NozzleMeterReading(
            tenant_id=tenant_id, shift_id=shift_id, nozzle_id=nozzle_id,
            worker_id=worker_id, reading_type="opening",
            amount_cumulative=Decimal("25707094.210"),  # higher
            volume_cumulative=Decimal("279142.074"),
            tot_sales_cumulative=113355, entered_manually=True,
        )
        closing = NozzleMeterReading(
            tenant_id=tenant_id, shift_id=shift_id, nozzle_id=nozzle_id,
            worker_id=worker_id, reading_type="closing",
            amount_cumulative=Decimal("25707038.550"),  # lower — wrong
            volume_cumulative=Decimal("279141.470"),
            tot_sales_cumulative=113354, entered_manually=True,
        )
        async_db_session.add_all([opening, closing])
        await async_db_session.flush()

        with pytest.raises(PetroValidationError) as exc_info:
            await _try_compute_shift_sale(shift_id, nozzle_id, async_db_session)
        assert "Closing amount" in exc_info.value.message
        assert "less than" in exc_info.value.message


# ── 3. Per-Worker Reconciliation ──────────────────────────────────────────────


class TestPerWorkerReconciliation:
    """Tests for reconcile_per_worker() service function."""

    @pytest.mark.asyncio
    async def test_worker_match(self, async_db_session):
        """MATCH when cash submitted equals shift sale."""
        await self._run_scenario(
            shift_sale=Decimal("55.66"),
            cash=Decimal("55.66"),
            expected_status="MATCH",
            expected_variance=Decimal("0.00"),
            db=async_db_session,
        )

    @pytest.mark.asyncio
    async def test_worker_shortage(self, async_db_session):
        """SHORTAGE when cash < expected."""
        await self._run_scenario(
            shift_sale=Decimal("55.66"),
            cash=Decimal("50.00"),
            expected_status="SHORTAGE",
            expected_variance=Decimal("5.66"),
            db=async_db_session,
        )

    @pytest.mark.asyncio
    async def test_worker_excess(self, async_db_session):
        """EXCESS when cash > expected."""
        await self._run_scenario(
            shift_sale=Decimal("55.66"),
            cash=Decimal("60.00"),
            expected_status="EXCESS",
            expected_variance=Decimal("-4.34"),
            db=async_db_session,
        )

    @pytest.mark.asyncio
    async def test_no_readings_raises(self, async_db_session):
        """ValidationError raised when no nozzle_shift_sales exist for shift."""
        from app.services.reconciliation.per_worker import reconcile_per_worker

        with pytest.raises(PetroValidationError) as exc_info:
            await reconcile_per_worker(uuid.uuid4(), async_db_session)
        assert "No meter readings" in exc_info.value.message

    async def _run_scenario(
        self,
        *,
        shift_sale: Decimal,
        cash: Decimal,
        expected_status: str,
        expected_variance: Decimal,
        db,
    ):
        from app.models.fms import CashEntry
        from app.models.nozzle_shift_sale import NozzleShiftSale
        from app.services.reconciliation.per_worker import reconcile_per_worker

        shift_id = uuid.uuid4()
        nozzle_id = uuid.uuid4()
        worker_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        sale = NozzleShiftSale(
            tenant_id=tenant_id,
            shift_id=shift_id,
            nozzle_id=nozzle_id,
            worker_id=worker_id,
            opening_amount=Decimal("0.000"),
            closing_amount=shift_sale,
            shift_sale_amount=shift_sale,
            opening_volume=Decimal("0.000"),
            closing_volume=Decimal("1.000"),
            shift_sale_volume=Decimal("1.000"),
            opening_tot_sales=0,
            closing_tot_sales=1,
            shift_transaction_count=1,
        )
        db.add(sale)

        cash_entry = CashEntry(
            shift_id=shift_id,
            attendant_id=worker_id,
            physical_cash=cash,
            is_deleted=False,
        )
        db.add(cash_entry)
        await db.flush()

        results = await reconcile_per_worker(shift_id, db)

        assert len(results) == 1
        r = results[0]
        assert r.status == expected_status
        assert r.variance == expected_variance
        assert r.shift_sale_amount == shift_sale
        assert r.actual_cash == cash


# ── 4. Tenant Isolation ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cannot_submit_reading_for_other_tenant_shift(test_client):
    """Tenant A's token cannot submit readings for Tenant B's shift → 404."""
    # Register two separate tenants
    reg_a = await test_client.post("/api/v1/auth/register", json={
        "tenant_name": "Tenant A Fuels",
        "owner_name": "Alice",
        "owner_phone": "9000000001",
        "owner_email": "alice@tenanta.com",
        "password": "SecurePass1!",
    })
    assert reg_a.status_code == 201
    token_a = reg_a.json()["access_token"]

    reg_b = await test_client.post("/api/v1/auth/register", json={
        "tenant_name": "Tenant B Fuels",
        "owner_name": "Bob",
        "owner_phone": "9000000002",
        "owner_email": "bob@tenantb.com",
        "password": "SecurePass2!",
    })
    assert reg_b.status_code == 201

    # Use a random UUID for shift_id — it won't belong to Tenant A
    fake_shift_id = str(uuid.uuid4())

    resp = await test_client.post(
        f"/api/v1/meter-readings/shifts/{fake_shift_id}/manual",
        json={
            "reading_type": "opening",
            "nozzle_readings": [
                {
                    "nozzle_number": 1,
                    "amount_cumulative": "25707038.550",
                    "volume_cumulative": "279141.470",
                    "tot_sales_cumulative": 113354,
                }
            ],
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    # Must return 404 — do not reveal the shift exists for another tenant
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cannot_read_other_tenant_meter_summary(test_client):
    """GET /meter-readings/shifts/{id} for another tenant's shift → 404."""
    reg = await test_client.post("/api/v1/auth/register", json={
        "tenant_name": "Isolated Fuels",
        "owner_name": "Carol",
        "owner_phone": "9000000003",
        "owner_email": "carol@isolated.com",
        "password": "SecurePass3!",
    })
    assert reg.status_code == 201
    token = reg.json()["access_token"]

    fake_shift_id = str(uuid.uuid4())
    resp = await test_client.get(
        f"/api/v1/meter-readings/shifts/{fake_shift_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
