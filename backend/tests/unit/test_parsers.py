"""
PetroLedger — Unit Tests for Parser & Deduplication Services.

All tests are pure unit tests: no database, no network.
External services (pytesseract, boto3) are mocked.

Required tests
--------------
1. test_upi_csv_sbi_format        — SBI CSV → 3 records
2. test_upi_csv_hdfc_format       — HDFC CSV → 3 records
3. test_upi_csv_unknown_format_raises — garbage headers → ValidationError
4. test_pos_ocr_parse_text        — mocked pytesseract → POSRecord fields
5. test_pump_log_json_format      — JSON pump log → volumes calculated
6. test_pump_log_csv_format       — CSV pump log → records parsed
7. test_deduplication_hash_consistency — same input → same hash
8. test_deduplication_detects_duplicate — same record hashed twice = dup
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ValidationError
from app.services.deduplication import DeduplicationService
from app.services.parsers.pos_ocr import POSOCRService, POSRecord
from app.services.parsers.pump_log import PumpLogParserService, PumpLogRecord
from app.services.parsers.upi_csv import UPICSVParserService, UPIRecord

# ═══════════════════════════════════════════════════════════════════════
# UPI CSV Parser
# ═══════════════════════════════════════════════════════════════════════

# Headers must match _FORMAT_SIGNATURES exactly (case-insensitive):
#   sbi:  {date, txn id, description, debit, credit, balance}
#   hdfc: {date, narration, chq./ref.no., value dt, withdrawal amt, deposit amt, closing balance}

_SBI_CSV = (
    "Date,Txn ID,Description,Debit,Credit,Balance\n"
    "05/03/2026,TXN001,UPI/123456789/Payment,,1500.50,50000.00\n"
    "05/03/2026,TXN002,UPI/987654321/Fuel,,2500.00,47500.00\n"
    "04/03/2026,TXN003,UPI/111111111/Diesel,,800.75,46699.25\n"
)

_HDFC_CSV = (
    "Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt,Deposit Amt,Closing Balance\n"
    "05/03/2026,UPI-FUEL-PAY,REF001,05/03/2026,,3000.00,120000.00\n"
    "05/03/2026,UPI-DIESEL,REF002,05/03/2026,,1200.50,121200.50\n"
    "04/03/2026,UPI-PETROL,REF003,04/03/2026,,900.00,122100.50\n"
)


def test_upi_csv_sbi_format():
    """Parse a hardcoded SBI CSV string, assert 3 records extracted."""
    parser = UPICSVParserService()
    result = parser.parse(_SBI_CSV.encode(), "sbi_statement.csv")

    assert result.format_detected == "sbi"
    assert result.total_records == 3
    assert len(result.records) == 3
    assert result.records[0].txn_id == "TXN001"
    assert result.records[0].amount == Decimal("1500.50")
    assert result.records[0].bank == "SBI"
    assert result.records[1].amount == Decimal("2500.00")
    assert result.records[2].amount == Decimal("800.75")


def test_upi_csv_hdfc_format():
    """Parse HDFC-format CSV, assert 3 records extracted."""
    parser = UPICSVParserService()
    result = parser.parse(_HDFC_CSV.encode(), "hdfc_statement.csv")

    assert result.format_detected == "hdfc"
    assert result.total_records == 3
    assert len(result.records) == 3
    assert result.records[0].txn_id == "REF001"
    assert result.records[0].amount == Decimal("3000.00")
    assert result.records[0].bank == "HDFC"


def test_upi_csv_unknown_format_raises():
    """Unrecognised CSV headers → ValidationError raised."""
    garbage = b"ColA,ColB,ColC\n1,2,3\n"
    parser = UPICSVParserService()

    with pytest.raises(ValidationError, match="Unrecognised CSV format"):
        parser.parse(garbage, "unknown.csv")


# ═══════════════════════════════════════════════════════════════════════
# POS OCR Parser
# ═══════════════════════════════════════════════════════════════════════

_MOCK_OCR_TEXT = (
    "SETTLEMENT SLIP\n"
    "TERMINAL ID: 30012345\n"
    "MERCHANT ID: 900012345678\n"
    "DATE: 05/03/26  TIME: 14:30\n"
    "TOTAL: Rs. 4,500.00\n"
    "APPROVAL CODE: A12345\n"
    "CARD: XXXX XXXX XXXX 9876\n"
)


def test_pos_ocr_parse_text():
    """Mock pytesseract, assert POSRecord fields extracted correctly."""
    import builtins
    import io

    from PIL import Image

    # Create a minimal valid PNG in memory
    img = Image.new("RGB", (100, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    # pytesseract is imported lazily inside _extract_tesseract;
    # intercept the import to return our mock
    mock_pytesseract = MagicMock()
    mock_pytesseract.image_to_string.return_value = _MOCK_OCR_TEXT

    real_import = builtins.__import__

    def _custom_import(name, *args, **kwargs):
        if name == "pytesseract":
            return mock_pytesseract
        return real_import(name, *args, **kwargs)

    with patch.object(builtins, "__import__", side_effect=_custom_import):
        ocr = POSOCRService()
        result = ocr.parse(img_bytes, "slip.png")

    assert result.success is True
    assert result.record is not None
    assert result.record.terminal_id == "30012345"
    assert result.record.merchant_id == "900012345678"
    assert result.record.amount == Decimal("4500.00")
    assert result.record.approval_code == "A12345"
    assert result.record.card_last_4 == "9876"
    assert result.confidence > 0


# ═══════════════════════════════════════════════════════════════════════
# Pump Log Parser
# ═══════════════════════════════════════════════════════════════════════

_PUMP_LOG_JSON = """[
  {
    "nozzle_number": 1,
    "fuel_type": "petrol",
    "start_reading": 12345.67,
    "end_reading": 12389.45,
    "timestamp": "2026-03-05T08:00:00"
  },
  {
    "nozzle_number": 2,
    "fuel_type": "diesel",
    "start_reading": 9000.00,
    "end_reading": 9100.50,
    "timestamp": "2026-03-05T08:30:00"
  }
]"""

_PUMP_LOG_CSV = (
    "nozzle_number,fuel_type,start_reading,end_reading,timestamp\n"
    "1,petrol,5000.00,5050.75,2026-03-05T09:00:00\n"
    "2,diesel,3000.00,3120.30,2026-03-05T09:30:00\n"
)


def test_pump_log_json_format():
    """Parse JSON pump log, assert volumes calculated."""
    parser = PumpLogParserService()
    result = parser.parse(_PUMP_LOG_JSON.encode(), "log.json")

    assert result.total_records == 2
    assert len(result.records) == 2

    rec1 = result.records[0]
    assert rec1.nozzle_number == 1
    assert rec1.fuel_type == "petrol"
    assert float(rec1.volume_dispensed) == pytest.approx(43.78, abs=0.01)
    assert rec1.start_reading == Decimal("12345.67")
    assert rec1.end_reading == Decimal("12389.45")

    rec2 = result.records[1]
    assert rec2.fuel_type == "diesel"
    assert float(rec2.volume_dispensed) == pytest.approx(100.50, abs=0.01)


def test_pump_log_csv_format():
    """Parse CSV pump log, assert records parsed."""
    parser = PumpLogParserService()
    result = parser.parse(_PUMP_LOG_CSV.encode(), "log.csv")

    assert result.total_records == 2
    assert len(result.records) == 2
    assert result.records[0].fuel_type == "petrol"
    assert result.records[1].fuel_type == "diesel"
    assert float(result.records[0].volume_dispensed) == pytest.approx(50.75, abs=0.01)


# ═══════════════════════════════════════════════════════════════════════
# Deduplication Service
# ═══════════════════════════════════════════════════════════════════════


def _make_upi_record(txn_id: str = "TXN001") -> UPIRecord:
    """Helper to build a UPIRecord for dedup tests."""
    return UPIRecord(
        txn_id=txn_id,
        amount=Decimal("1500.50"),
        timestamp=datetime(2026, 3, 5, 10, 30),
        bank="SBI",
        description="Fuel payment",
        raw_row={},
    )


def test_deduplication_hash_consistency():
    """Same input always produces the same SHA-256 hash."""
    svc = DeduplicationService()
    rec = _make_upi_record()

    h1 = svc.generate_upi_hash(rec)
    h2 = svc.generate_upi_hash(rec)

    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest length


def test_deduplication_detects_duplicate():
    """Same record hashed twice → duplicate detected via set membership."""
    svc = DeduplicationService()
    rec = _make_upi_record()

    # Simulate intra-batch dedup with a seen-hashes set
    seen: set[str] = set()
    h = svc.generate_upi_hash(rec)
    seen.add(h)

    # Hash the same record again → detected as duplicate
    h_again = svc.generate_upi_hash(rec)
    assert h_again in seen
