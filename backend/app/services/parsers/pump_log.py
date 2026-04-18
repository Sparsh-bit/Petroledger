"""
PetroLedger — Pump Meter / Dispenser Log Parser Service.

Parses pump hardware log files in three formats:

1. **JSON** — array of objects or newline-delimited JSON.
2. **CSV**  — ``nozzle_number, start_reading, end_reading, date, time, fuel_type``.
3. **Flat text** — fixed-width or ``KEY:VALUE`` pairs
   (e.g. ``NZL:01 START:12345.67 END:12389.45 DATE:05/03/2026 FUEL:PET``).

Each parsed row is validated against business rules and normalised into
a :class:`PumpLogRecord`.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog

from app.core.exceptions import ValidationError

logger = structlog.stdlib.get_logger("petroledger.parsers.pump_log")

# ── Constants ───────────────────────────────────────────────────────────

_IST = timezone(timedelta(hours=5, minutes=30))

# Maximum single-fill volume (litres)
_MAX_VOLUME_LITRES = Decimal("2000")
# Volume above this is flagged as suspicious but still accepted
_SUSPICIOUS_VOLUME_LITRES = Decimal("500")
# Records older than this many days are flagged
_MAX_AGE_DAYS = 7

# Fuel-type normalisation map
_FUEL_ALIASES: dict[str, str] = {
    "pet": "petrol",
    "petrol": "petrol",
    "p": "petrol",
    "ms": "petrol",        # Motor Spirit
    "die": "diesel",
    "diesel": "diesel",
    "d": "diesel",
    "hsd": "diesel",       # High-Speed Diesel
    "cng": "cng",
    "c": "cng",
}

# ── Data classes ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PumpLogRecord:
    """A single normalised pump dispenser log entry."""

    nozzle_number: int
    start_reading: Decimal
    end_reading: Decimal
    volume_dispensed: Decimal
    fuel_type: str
    timestamp: datetime
    raw_data: dict[str, Any]


@dataclass(slots=True)
class PumpLogParseResult:
    """Outcome of parsing a pump log file."""

    records: list[PumpLogRecord] = field(default_factory=list)
    total_records: int = 0
    failed_records: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    format_detected: str = ""


# ── Text-line regex ─────────────────────────────────────────────────────

_RE_TEXT_LINE = re.compile(
    r"NZL\s*[:\-]?\s*(\d+)\s+"
    r"START\s*[:\-]?\s*([\d.]+)\s+"
    r"END\s*[:\-]?\s*([\d.]+)\s+"
    r"DATE\s*[:\-]?\s*([\d/\-]+)"
    r"(?:\s+TIME\s*[:\-]?\s*([\d:]+))?"
    r"(?:\s+FUEL\s*[:\-]?\s*(\w+))?",
    re.IGNORECASE,
)


# ── Service ─────────────────────────────────────────────────────────────


class PumpLogParserService:
    """
    Multi-format pump dispenser log parser.

    Usage::

        svc = PumpLogParserService()
        result = svc.parse(file_bytes, "pump_log_march.csv")
    """

    # ── Public API ──────────────────────────────────────────────────

    @staticmethod
    def detect_format(content: bytes) -> str:
        """
        Detect the format of a pump log file.

        Returns
        -------
        str
            ``"json"``, ``"csv"``, or ``"text"``.

        Raises
        ------
        ValidationError
            If the content is empty.
        """
        text = content.decode("utf-8", errors="replace").strip()
        if not text:
            raise ValidationError(message="Pump log file is empty.")

        # JSON: starts with [ or {
        first_char = text.lstrip()[0] if text.lstrip() else ""
        if first_char in ("{", "["):
            return "json"

        # CSV: first line looks like a header with commas
        first_line = text.split("\n", 1)[0]
        if "," in first_line and any(
            kw in first_line.lower()
            for kw in ("nozzle", "start_reading", "end_reading", "reading")
        ):
            return "csv"

        # Text: contains KEY:VALUE patterns
        if re.search(r"NZL\s*[:\-]", text, re.IGNORECASE):
            return "text"

        # Last-resort: if it has commas + looks numeric, treat as CSV
        if "," in first_line:
            return "csv"

        # Give up
        raise ValidationError(
            message=(
                "Cannot detect pump log format. Expected JSON, CSV, or "
                "fixed-width text (NZL:xx START:xx END:xx …)."
            ),
        )

    def parse(self, file_content: bytes, filename: str) -> PumpLogParseResult:
        """
        Parse raw file bytes into validated :class:`PumpLogRecord` objects.
        """
        result = PumpLogParseResult()

        fmt = self.detect_format(file_content)
        result.format_detected = fmt
        logger.info("pump_log_format_detected", format=fmt, filename=filename)

        # ── Dispatch ────────────────────────────────────────────────
        parser_map = {
            "json": self._parse_json,
            "csv": self._parse_csv,
            "text": self._parse_text,
        }

        raw_records: list[PumpLogRecord] = []
        try:
            raw_records = parser_map[fmt](file_content)
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(
                message=f"Failed to parse pump log '{filename}': {exc}",
            ) from exc

        result.total_records = len(raw_records)

        # ── Validate each record ────────────────────────────────────
        for i, rec in enumerate(raw_records):
            issues = self._validate_reading(rec)
            if any(
                "end_reading must be" in e or "volume exceeds" in e
                for e in issues
            ):
                result.failed_records += 1
                result.errors.extend(f"Record {i}: {e}" for e in issues)
            else:
                result.records.append(rec)
                # Attach warnings (e.g. suspicious volume)
                for w in issues:
                    result.warnings.append(f"Record {i}: {w}")

        logger.info(
            "pump_log_parse_complete",
            filename=filename,
            format=fmt,
            total=result.total_records,
            valid=len(result.records),
            failed=result.failed_records,
        )
        return result

    # ── Format-specific parsers ─────────────────────────────────────

    def _parse_json(self, content: bytes) -> list[PumpLogRecord]:
        """Parse JSON array or newline-delimited JSON."""
        text = content.decode("utf-8", errors="replace").strip()

        # Try as a JSON array first, then as NDJSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try newline-delimited JSON
            data = []
            for line in text.splitlines():
                line = line.strip()
                if line:
                    data.append(json.loads(line))

        if isinstance(data, dict):
            data = [data]

        records: list[PumpLogRecord] = []
        for obj in data:
            nozzle = int(obj.get("nozzle_id") or obj.get("nozzle_number", 0))
            start = self._to_decimal(obj.get("start_reading", "0"))
            end = self._to_decimal(obj.get("end_reading", "0"))
            fuel = self._normalize_fuel(obj.get("fuel_type", ""))
            ts = self._parse_timestamp(obj.get("timestamp", ""))

            records.append(
                PumpLogRecord(
                    nozzle_number=nozzle,
                    start_reading=start,
                    end_reading=end,
                    volume_dispensed=self._calculate_volume(start, end),
                    fuel_type=fuel,
                    timestamp=ts,
                    raw_data=obj,
                )
            )
        return records

    def _parse_csv(self, content: bytes) -> list[PumpLogRecord]:
        """Parse CSV with header row."""
        text = content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text), skipinitialspace=True)

        records: list[PumpLogRecord] = []
        for row in reader:
            # Normalise keys to lowercase + strip
            row = {k.strip().lower(): v.strip() for k, v in row.items()}

            nozzle = int(row.get("nozzle_number", 0) or 0)
            start = self._to_decimal(row.get("start_reading", "0"))
            end = self._to_decimal(row.get("end_reading", "0"))
            fuel = self._normalize_fuel(row.get("fuel_type", ""))

            # Combine date + time columns if both exist
            date_str = row.get("date", "")
            time_str = row.get("time", "")
            ts_raw = f"{date_str} {time_str}".strip() if date_str else ""
            ts = self._parse_timestamp(ts_raw)

            records.append(
                PumpLogRecord(
                    nozzle_number=nozzle,
                    start_reading=start,
                    end_reading=end,
                    volume_dispensed=self._calculate_volume(start, end),
                    fuel_type=fuel,
                    timestamp=ts,
                    raw_data=dict(row),
                )
            )
        return records

    def _parse_text(self, content: bytes) -> list[PumpLogRecord]:
        """Parse fixed-width / KEY:VALUE text lines."""
        text = content.decode("utf-8", errors="replace")
        records: list[PumpLogRecord] = []

        for match in _RE_TEXT_LINE.finditer(text):
            nozzle = int(match.group(1))
            start = self._to_decimal(match.group(2))
            end = self._to_decimal(match.group(3))
            date_str = match.group(4) or ""
            time_str = match.group(5) or ""
            fuel = self._normalize_fuel(match.group(6) or "")

            ts_raw = f"{date_str} {time_str}".strip()
            ts = self._parse_timestamp(ts_raw)

            records.append(
                PumpLogRecord(
                    nozzle_number=nozzle,
                    start_reading=start,
                    end_reading=end,
                    volume_dispensed=self._calculate_volume(start, end),
                    fuel_type=fuel,
                    timestamp=ts,
                    raw_data={
                        "nozzle": nozzle,
                        "start": str(start),
                        "end": str(end),
                        "date": date_str,
                        "time": time_str,
                        "fuel": fuel,
                        "raw_line": match.group(0),
                    },
                )
            )

        if not records:
            raise ValidationError(
                message=(
                    "No pump log entries found in text file. Expected lines like: "
                    "NZL:01 START:12345.67 END:12389.45 DATE:05/03/2026 FUEL:PET"
                ),
            )
        return records

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _calculate_volume(start: Decimal, end: Decimal) -> Decimal:
        """Calculate dispensed volume from meter readings."""
        vol = end - start
        return vol if vol > 0 else Decimal("0")

    @staticmethod
    def _validate_reading(record: PumpLogRecord) -> list[str]:
        """
        Validate a single pump log record.

        Returns a list of issues (empty = valid).
        """
        issues: list[str] = []

        # End must exceed start
        if record.end_reading <= record.start_reading:
            issues.append(
                f"end_reading must be > start_reading "
                f"(start={record.start_reading}, end={record.end_reading})"
            )

        # Volume sanity checks
        vol = record.volume_dispensed
        if vol > _MAX_VOLUME_LITRES:
            issues.append(
                f"volume exceeds maximum ({vol} > {_MAX_VOLUME_LITRES} litres)"
            )
        elif vol > _SUSPICIOUS_VOLUME_LITRES:
            issues.append(
                f"suspicious volume: {vol} litres (> {_SUSPICIOUS_VOLUME_LITRES})"
            )

        # Timestamp freshness
        now = datetime.now(_IST)
        age = now - record.timestamp.replace(tzinfo=_IST)
        if age > timedelta(days=_MAX_AGE_DAYS):
            issues.append(
                f"timestamp older than {_MAX_AGE_DAYS} days "
                f"(recorded {record.timestamp.isoformat()})"
            )

        return issues

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        """Safely convert to Decimal."""
        try:
            return Decimal(str(value).strip().replace(",", ""))
        except (InvalidOperation, ValueError):
            return Decimal("0")

    @staticmethod
    def _normalize_fuel(raw: str) -> str:
        """Map fuel abbreviations to canonical names."""
        return _FUEL_ALIASES.get(raw.strip().lower(), raw.strip().lower())

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        """Parse common date/time strings from pump hardware."""
        raw = value.strip()
        if not raw:
            return datetime.now()

        formats = [
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d-%m-%Y",
            "%d/%m/%y %H:%M:%S",
            "%d/%m/%y %H:%M",
            "%d/%m/%y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue

        # Fallback
        return datetime.now()
