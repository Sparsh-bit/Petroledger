"""
PetroLedger — UPI CSV Parser Service.

Parses UPI / bank-statement CSVs from multiple Indian bank formats
and normalises them into a uniform list of :class:`UPIRecord` objects.

Supported formats
-----------------
* **SBI**      — Date, Txn ID, Description, Debit, Credit, Balance
* **HDFC**     — Date, Narration, Chq./Ref.No., Value Dt, Withdrawal Amt,
                 Deposit Amt, Closing Balance
* **ICICI**    — Transaction Date, Transaction Remarks, Amount (INR), Dr/Cr
* **PhonePe**  — Date, Transaction ID, Type, Amount, Status
* **GooglePay** — Date, Description, Amount, Status, Transaction ID
"""

from __future__ import annotations

import io
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
import structlog

from app.core.exceptions import ValidationError

logger = structlog.stdlib.get_logger("petroledger.parsers.upi_csv")

# ── Data classes ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class UPIRecord:
    """A single normalised UPI transaction row."""

    txn_id: str
    amount: Decimal
    timestamp: datetime
    bank: str
    description: str
    raw_row: dict[str, Any]


@dataclass(slots=True)
class ParseResult:
    """Outcome of parsing an entire CSV file."""

    records: list[UPIRecord] = field(default_factory=list)
    total_records: int = 0
    failed_records: int = 0
    errors: list[str] = field(default_factory=list)
    format_detected: str = ""


# ── Format signature maps ──────────────────────────────────────────────

_FORMAT_SIGNATURES: dict[str, set[str]] = {
    "sbi": {"date", "txn id", "description", "debit", "credit", "balance"},
    "hdfc": {
        "date",
        "narration",
        "chq./ref.no.",
        "value dt",
        "withdrawal amt",
        "deposit amt",
        "closing balance",
    },
    "icici": {
        "transaction date",
        "transaction remarks",
        "amount (inr)",
        "dr/cr",
    },
    "phonepe": {"date", "transaction id", "type", "amount", "status"},
    "googlepay": {"date", "description", "amount", "status", "transaction id"},
}


# ── Service ─────────────────────────────────────────────────────────────


class UPICSVParserService:
    """
    Multi-format UPI CSV parser.

    Usage::

        svc = UPICSVParserService()
        result = svc.parse(file_bytes, "sbi_march_2026.csv")
    """

    # ── Public API ──────────────────────────────────────────────────

    @staticmethod
    def detect_format(headers: list[str]) -> str:
        """
        Match a list of CSV column headers to a known bank format.

        Parameters
        ----------
        headers:
            Raw header strings from the first row of the CSV.

        Returns
        -------
        str
            One of ``"sbi"``, ``"hdfc"``, ``"icici"``, ``"phonepe"``,
            ``"googlepay"``.

        Raises
        ------
        ValidationError
            If the headers do not match any known format.
        """
        normalised = {h.strip().lower() for h in headers}

        # Match from most-specific (most columns) to least-specific
        for fmt, required in sorted(
            _FORMAT_SIGNATURES.items(), key=lambda kv: -len(kv[1])
        ):
            if required.issubset(normalised):
                return fmt

        raise ValidationError(
            message=(
                "Unrecognised CSV format. Could not match headers to any "
                "supported bank format (SBI, HDFC, ICICI, PhonePe, GooglePay). "
                f"Received headers: {headers}"
            ),
            detail={"headers": headers, "supported_formats": list(_FORMAT_SIGNATURES.keys())},
        )

    def parse(self, file_content: bytes, filename: str) -> ParseResult:
        """
        Parse raw CSV bytes into normalised :class:`UPIRecord` objects.

        Tries UTF-8 first and falls back to Latin-1 for older bank exports.
        """
        result = ParseResult()

        # ── Decode ──────────────────────────────────────────────────
        text = self._decode(file_content)

        # ── Read CSV via pandas ─────────────────────────────────────
        try:
            df = pd.read_csv(
                io.StringIO(text),
                skipinitialspace=True,
                dtype=str,
                keep_default_na=False,
            )
        except Exception as exc:
            raise ValidationError(
                message=f"Failed to read CSV file '{filename}': {exc}",
            ) from exc

        if df.empty:
            raise ValidationError(
                message=f"CSV file '{filename}' is empty or has no data rows.",
            )

        # Strip whitespace from column names and all cell values
        df.columns = [c.strip() for c in df.columns]
        df = df.map(lambda v: v.strip() if isinstance(v, str) else v)

        # ── Detect format ───────────────────────────────────────────
        fmt = self.detect_format(list(df.columns))
        result.format_detected = fmt
        logger.info(
            "csv_format_detected",
            format=fmt,
            filename=filename,
            columns=list(df.columns),
        )

        # ── Dispatch to bank-specific parser ────────────────────────
        parser_map = {
            "sbi": self._parse_sbi,
            "hdfc": self._parse_hdfc,
            "icici": self._parse_icici,
            "phonepe": self._parse_phonepe,
            "googlepay": self._parse_googlepay,
        }
        records, errors = parser_map[fmt](df)

        result.records = records
        result.total_records = len(df)
        result.failed_records = len(errors)
        result.errors = errors

        logger.info(
            "csv_parse_complete",
            filename=filename,
            format=fmt,
            total=result.total_records,
            parsed=len(records),
            failed=result.failed_records,
        )
        return result

    # ── Bank-specific parsers ───────────────────────────────────────

    def _parse_sbi(self, df: pd.DataFrame) -> tuple[list[UPIRecord], list[str]]:
        """
        SBI columns: Date, Txn ID, Description, Debit, Credit, Balance.

        Credit column = incoming UPI; Debit column = outgoing.
        We take whichever is non-zero as the amount.
        """
        records: list[UPIRecord] = []
        errors: list[str] = []

        for idx, row in df.iterrows():
            try:
                credit = self._normalize_amount(row.get("Credit", ""))
                debit = self._normalize_amount(row.get("Debit", ""))
                amount = credit if credit else debit
                if not amount:
                    continue  # skip zero / null rows

                records.append(
                    UPIRecord(
                        txn_id=row.get("Txn ID", "") or str(uuid.uuid4()),
                        amount=amount,
                        timestamp=self._normalize_date(row.get("Date", "")),
                        bank="SBI",
                        description=row.get("Description", ""),
                        raw_row=dict(row),
                    )
                )
            except Exception as exc:
                errors.append(f"Row {idx}: {exc}")

        return records, errors

    def _parse_hdfc(self, df: pd.DataFrame) -> tuple[list[UPIRecord], list[str]]:
        """
        HDFC columns: Date, Narration, Chq./Ref.No., Value Dt,
                      Withdrawal Amt, Deposit Amt, Closing Balance.
        """
        records: list[UPIRecord] = []
        errors: list[str] = []

        for idx, row in df.iterrows():
            try:
                deposit = self._normalize_amount(row.get("Deposit Amt", ""))
                withdrawal = self._normalize_amount(row.get("Withdrawal Amt", ""))
                amount = deposit if deposit else withdrawal
                if not amount:
                    continue

                records.append(
                    UPIRecord(
                        txn_id=row.get("Chq./Ref.No.", "") or str(uuid.uuid4()),
                        amount=amount,
                        timestamp=self._normalize_date(row.get("Date", "")),
                        bank="HDFC",
                        description=row.get("Narration", ""),
                        raw_row=dict(row),
                    )
                )
            except Exception as exc:
                errors.append(f"Row {idx}: {exc}")

        return records, errors

    def _parse_icici(self, df: pd.DataFrame) -> tuple[list[UPIRecord], list[str]]:
        """
        ICICI columns: Transaction Date, Transaction Remarks,
                       Amount (INR), Dr/Cr.
        """
        records: list[UPIRecord] = []
        errors: list[str] = []

        for idx, row in df.iterrows():
            try:
                amount = self._normalize_amount(row.get("Amount (INR)", ""))
                if not amount:
                    continue

                # Extract ref from remarks when possible (UPI/xxx/yyy)
                remarks = row.get("Transaction Remarks", "")
                txn_id = self._extract_ref_from_remarks(remarks) or str(uuid.uuid4())

                records.append(
                    UPIRecord(
                        txn_id=txn_id,
                        amount=amount,
                        timestamp=self._normalize_date(
                            row.get("Transaction Date", "")
                        ),
                        bank="ICICI",
                        description=remarks,
                        raw_row=dict(row),
                    )
                )
            except Exception as exc:
                errors.append(f"Row {idx}: {exc}")

        return records, errors

    def _parse_phonepe(self, df: pd.DataFrame) -> tuple[list[UPIRecord], list[str]]:
        """
        PhonePe columns: Date, Transaction ID, Type, Amount, Status.
        """
        records: list[UPIRecord] = []
        errors: list[str] = []

        for idx, row in df.iterrows():
            try:
                # Only include successful transactions
                status = (row.get("Status", "") or "").lower()
                if status and status not in ("success", "completed", "paid"):
                    continue

                amount = self._normalize_amount(row.get("Amount", ""))
                if not amount:
                    continue

                records.append(
                    UPIRecord(
                        txn_id=row.get("Transaction ID", "") or str(uuid.uuid4()),
                        amount=amount,
                        timestamp=self._normalize_date(row.get("Date", "")),
                        bank="PhonePe",
                        description=row.get("Type", ""),
                        raw_row=dict(row),
                    )
                )
            except Exception as exc:
                errors.append(f"Row {idx}: {exc}")

        return records, errors

    def _parse_googlepay(
        self, df: pd.DataFrame
    ) -> tuple[list[UPIRecord], list[str]]:
        """
        GooglePay columns: Date, Description, Amount, Status, Transaction ID.
        """
        records: list[UPIRecord] = []
        errors: list[str] = []

        for idx, row in df.iterrows():
            try:
                status = (row.get("Status", "") or "").lower()
                if status and status not in ("completed", "success", "paid"):
                    continue

                amount = self._normalize_amount(row.get("Amount", ""))
                if not amount:
                    continue

                records.append(
                    UPIRecord(
                        txn_id=row.get("Transaction ID", "") or str(uuid.uuid4()),
                        amount=amount,
                        timestamp=self._normalize_date(row.get("Date", "")),
                        bank="GooglePay",
                        description=row.get("Description", ""),
                        raw_row=dict(row),
                    )
                )
            except Exception as exc:
                errors.append(f"Row {idx}: {exc}")

        return records, errors

    # ── Normalisation helpers ───────────────────────────────────────

    @staticmethod
    def _normalize_amount(value: Any) -> Decimal:
        """
        Convert a raw cell value to a positive :class:`Decimal`.

        Handles Indian formats: ``"1,23,456.78"``, ``"₹ 500.00"``,
        ``"- 200.00"`` (treated as ``200.00``).

        Returns ``Decimal("0")`` if the value is empty or unparseable.
        """
        if value is None:
            return Decimal("0")

        raw = str(value).strip()
        if not raw:
            return Decimal("0")

        # Strip currency symbols and whitespace
        raw = re.sub(r"[₹$\s]", "", raw)
        # Remove commas (Indian / international grouping)
        raw = raw.replace(",", "")
        # Strip leading minus / plus — we always store absolute amounts
        raw = raw.lstrip("-+")

        if not raw:
            return Decimal("0")

        try:
            amt = Decimal(raw)
            return abs(amt)
        except InvalidOperation:
            return Decimal("0")

    @staticmethod
    def _normalize_date(value: Any) -> datetime:
        """
        Parse a date string into a :class:`datetime`.

        Tries common Indian bank date patterns in order:
        ``dd/mm/yyyy``, ``dd-mm-yyyy``, ``yyyy-mm-dd``,
        ``dd/mm/yy``, ``dd-mm-yy``, and ISO 8601.
        """
        raw = str(value).strip()
        if not raw:
            raise ValueError("Empty date value")

        formats = [
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d-%m-%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%y",
            "%d-%m-%y",
            "%d %b %Y",      # 05 Mar 2026
            "%d %B %Y",      # 05 March 2026
        ]

        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue

        # Final fallback: let pandas try
        try:
            return pd.to_datetime(raw).to_pydatetime()
        except Exception as exc:
            raise ValueError(
                f"Could not parse date '{raw}' with any known format"
            ) from exc

    @staticmethod
    def _extract_ref_from_remarks(remarks: str) -> str | None:
        """Pull a UPI reference ID from narration text like ``UPI/123456789/...``."""
        match = re.search(r"(?:UPI|IMPS|NEFT)[/\-](\S+?)(?:[/\-]|$)", remarks, re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _decode(content: bytes) -> str:
        """Decode bytes to string, trying UTF-8 then Latin-1."""
        try:
            return content.decode("utf-8-sig")  # handles BOM
        except UnicodeDecodeError:
            return content.decode("latin-1")
