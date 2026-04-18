"""
PetroLedger — POS Settlement Slip OCR Service.

Extracts structured transaction data from POS terminal settlement-slip images
using Tesseract (primary) or AWS Textract (fallback).

Regex patterns target common Indian POS receipt fields:
    TID / Terminal ID, MID / Merchant ID, TOTAL / AMOUNT / Rs,
    Date (DD/MM/YY or DD-MM-YYYY), Approval Code, Card last 4 digits.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

import structlog
from PIL import Image, ImageFilter, ImageOps

from app.core.config import get_settings
from app.core.exceptions import ValidationError

logger = structlog.stdlib.get_logger("petroledger.parsers.pos_ocr")

# ── Data classes ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class POSRecord:
    """A single normalised POS transaction extracted from a slip image."""

    terminal_id: str
    merchant_id: str
    amount: Decimal
    timestamp: datetime
    approval_code: str
    card_last_4: str
    raw_text: str


@dataclass(slots=True)
class POSParseResult:
    """Outcome of parsing a POS slip image."""

    record: POSRecord | None = None
    success: bool = False
    confidence: float = 0.0
    errors: list[str] = field(default_factory=list)


# ── Regex patterns ──────────────────────────────────────────────────────

# Terminal ID — e.g. "TID: 12345678", "Terminal ID:12345678", "TID 12345678"
_RE_TERMINAL_ID = re.compile(
    r"(?:TID|TERMINAL\s*(?:ID)?)\s*[:\-]?\s*(\d{4,16})",
    re.IGNORECASE,
)

# Merchant ID — e.g. "MID: 87654321", "MERCHANT ID:87654321"
_RE_MERCHANT_ID = re.compile(
    r"(?:MID|MERCHANT\s*(?:ID)?)\s*[:\-]?\s*(\d{4,16})",
    re.IGNORECASE,
)

# Amount — e.g. "Total: Rs. 1,23,456.78", "AMOUNT Rs1500.00", "INR 500"
_RE_AMOUNT = re.compile(
    r"(?:TOTAL|AMOUNT|SALE\s*AMOUNT|GRAND\s*TOTAL|Rs\.?|INR)\s*[:\-]?\s*"
    r"[₹]?\s*([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)

# Date — DD/MM/YY, DD/MM/YYYY, DD-MM-YY, DD-MM-YYYY, YYYY-MM-DD
_RE_DATE = re.compile(
    r"(?:DATE|DT)\s*[:\-]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"
    r"|(\d{4}[/\-]\d{1,2}[/\-]\d{1,2})",
    re.IGNORECASE,
)

# Time — HH:MM:SS or HH:MM
_RE_TIME = re.compile(
    r"(?:TIME|TM)\s*[:\-]?\s*(\d{1,2}:\d{2}(?::\d{2})?)",
    re.IGNORECASE,
)

# Approval / Auth Code — e.g. "Approval Code: 123456", "AUTH CODE:654321"
_RE_APPROVAL = re.compile(
    r"(?:APPR(?:OVAL)?|AUTH)\s*(?:CODE)?\s*[:\-]?\s*(\w{4,12})",
    re.IGNORECASE,
)

# Card last 4 — e.g. "CARD NO: XXXX XXXX XXXX 1234", "Card: ****1234"
_RE_CARD_LAST4 = re.compile(
    r"(?:CARD\s*(?:NO|NUMBER)?)\s*[:\-]?\s*[*Xx\s]*(\d{4})\s*$"
    r"|[*Xx]{4,}\s*(\d{4})",
    re.IGNORECASE | re.MULTILINE,
)


# ── Service ─────────────────────────────────────────────────────────────


class POSOCRService:
    """
    OCR-based POS settlement slip parser.

    Usage::

        svc = POSOCRService()
        result = svc.parse(image_bytes, "slip_001.jpg")
    """

    # ── Image Pre-processing ────────────────────────────────────────

    @staticmethod
    def preprocess_image(image_bytes: bytes) -> Image.Image:
        """
        Prepare an image for OCR.

        Steps:
            1. Open image from bytes.
            2. Auto-orient using EXIF (handles phone rotation).
            3. Convert to grayscale.
            4. Apply median filter for de-noising.
            5. Apply adaptive threshold for clear text edges.
            6. Scale up small images for better Tesseract accuracy.
        """
        img = Image.open(io.BytesIO(image_bytes))

        # Auto-orient from EXIF metadata (rotation correction)
        img = ImageOps.exif_transpose(img)

        # Grayscale
        img = img.convert("L")

        # De-noise with median filter
        img = img.filter(ImageFilter.MedianFilter(size=3))

        # Increase contrast via autocontrast
        img = ImageOps.autocontrast(img, cutoff=1)

        # Binarize — simple threshold at 140 (good default for thermal slips)
        img = img.point(lambda px: 255 if px > 140 else 0, mode="1")

        # Scale up small images (Tesseract works best ≥ 300 DPI)
        min_width = 1000
        if img.width < min_width:
            scale = min_width / img.width
            img = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.LANCZOS,
            )

        return img

    # ── Text Extraction ─────────────────────────────────────────────

    def extract_text(
        self,
        image_bytes: bytes,
        use_aws: bool = False,
    ) -> str:
        """
        Extract text from a POS slip image.

        Parameters
        ----------
        image_bytes:
            Raw image file bytes (JPEG, PNG, etc.).
        use_aws:
            If ``True``, try AWS Textract instead of / in addition to
            Tesseract.

        Returns the best text it can get (Tesseract first, Textract fallback).
        """
        text = ""

        # ── Primary: Tesseract ──────────────────────────────────────
        if not use_aws:
            try:
                text = self._extract_tesseract(image_bytes)
                if text.strip():
                    return text
            except Exception as exc:
                logger.warning(
                    "tesseract_failed",
                    error=str(exc),
                    fallback="aws_textract",
                )
                # Fall through to Textract

        # ── Fallback: AWS Textract ──────────────────────────────────
        try:
            text = self._extract_textract(image_bytes)
        except Exception as exc:
            logger.error("textract_failed", error=str(exc))
            if not text:
                raise ValidationError(
                    message=f"OCR extraction failed for image: {exc}",
                    detail={"tesseract": "failed", "textract": str(exc)},
                ) from exc

        return text

    # ── Slip Parsing (regex) ────────────────────────────────────────

    def parse_slip(self, text: str) -> POSRecord:
        """
        Extract structured fields from OCR text using regex patterns.

        Attempts to find: terminal_id, merchant_id, amount,
        date+time, approval_code, card_last_4.
        """
        terminal_id = self._first_match(_RE_TERMINAL_ID, text) or ""
        merchant_id = self._first_match(_RE_MERCHANT_ID, text) or ""
        approval_code = self._first_match(_RE_APPROVAL, text) or ""
        card_last_4 = self._first_match(_RE_CARD_LAST4, text) or ""
        amount = self._extract_amount(text)
        timestamp = self._extract_timestamp(text)

        return POSRecord(
            terminal_id=terminal_id,
            merchant_id=merchant_id,
            amount=amount,
            timestamp=timestamp,
            approval_code=approval_code,
            card_last_4=card_last_4,
            raw_text=text,
        )

    # ── Main entry point ────────────────────────────────────────────

    def parse(
        self,
        image_bytes: bytes,
        filename: str,
        use_aws: bool = False,
    ) -> POSParseResult:
        """
        Full pipeline: preprocess → OCR → regex parse → confidence score.

        Parameters
        ----------
        image_bytes:
            Raw image bytes.
        filename:
            Original filename (for logging / error messages).
        use_aws:
            Pass ``True`` to use AWS Textract.
        """
        result = POSParseResult()

        # ── Extract text ────────────────────────────────────────────
        try:
            text = self.extract_text(image_bytes, use_aws=use_aws)
        except ValidationError:
            raise
        except Exception as exc:
            result.errors.append(f"OCR failed for '{filename}': {exc}")
            logger.exception("pos_ocr_failed", filename=filename)
            return result

        if not text.strip():
            result.errors.append(f"No text extracted from '{filename}'.")
            return result

        # ── Parse fields ────────────────────────────────────────────
        try:
            record = self.parse_slip(text)
        except Exception as exc:
            result.errors.append(f"Slip parsing failed: {exc}")
            logger.exception("pos_parse_failed", filename=filename)
            return result

        result.record = record
        result.confidence = self._score_confidence(record)
        result.success = result.confidence >= 0.5

        logger.info(
            "pos_parse_complete",
            filename=filename,
            confidence=result.confidence,
            terminal_id=record.terminal_id or "(none)",
            amount=str(record.amount),
        )
        return result

    # ── Private helpers ─────────────────────────────────────────────

    def _extract_tesseract(self, image_bytes: bytes) -> str:
        """Run Tesseract OCR on pre-processed image."""
        import pytesseract

        img = self.preprocess_image(image_bytes)
        text: str = pytesseract.image_to_string(
            img,
            config="--psm 6 --oem 3",  # PSM 6 = uniform block of text
        )
        logger.debug("tesseract_result", text_length=len(text))
        return text

    def _extract_textract(self, image_bytes: bytes) -> str:
        """Call AWS Textract DetectDocumentText."""
        import boto3

        settings = get_settings()
        client = boto3.client(
            "textract",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        )

        response = client.detect_document_text(
            Document={"Bytes": image_bytes},
        )

        lines: list[str] = []
        for block in response.get("Blocks", []):
            if block["BlockType"] == "LINE":
                lines.append(block.get("Text", ""))

        text = "\n".join(lines)
        logger.debug("textract_result", text_length=len(text), lines=len(lines))
        return text

    @staticmethod
    def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
        """Return the first non-empty capture group from a regex match."""
        m = pattern.search(text)
        if not m:
            return None
        # Return the first non-empty group
        for g in m.groups():
            if g:
                return g.strip()
        return None

    @staticmethod
    def _extract_amount(text: str) -> Decimal:
        """
        Find all amount candidates and return the largest.

        Handles Indian formatting: ``1,23,456.78``, ``Rs. 500``.
        """
        amounts: list[Decimal] = []

        for m in _RE_AMOUNT.finditer(text):
            raw = m.group(1)
            if not raw:
                continue
            raw = raw.replace(",", "")
            try:
                amounts.append(Decimal(raw))
            except InvalidOperation:
                continue

        return max(amounts) if amounts else Decimal("0")

    @staticmethod
    def _extract_timestamp(text: str) -> datetime:
        """Combine date + time regex matches into a datetime."""
        # ── Date ────────────────────────────────────────────────────
        date_str = ""
        dm = _RE_DATE.search(text)
        if dm:
            date_str = dm.group(1) or dm.group(2) or ""

        # ── Time ────────────────────────────────────────────────────
        time_str = ""
        tm = _RE_TIME.search(text)
        if tm:
            time_str = tm.group(1)

        if not date_str:
            return datetime.now()  # fallback

        # Try common date formats
        combined = f"{date_str} {time_str}".strip() if time_str else date_str
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
            "%d-%m-%y %H:%M:%S",
            "%d-%m-%y %H:%M",
            "%d-%m-%y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(combined, fmt)
            except ValueError:
                continue

        return datetime.now()  # ultimate fallback

    @staticmethod
    def _score_confidence(record: POSRecord) -> float:
        """
        Score extraction confidence based on how many key fields were found.

        - 1.00 → all 4 key fields (terminal_id, amount, date, approval_code)
        - 0.75 → 3 fields
        - 0.50 → only amount extracted
        - 0.00 → amount missing
        """
        if not record.amount:
            return 0.0

        key_fields = [
            bool(record.terminal_id),
            record.amount > 0,
            record.timestamp != datetime.min,
            bool(record.approval_code),
        ]
        found = sum(key_fields)

        if found >= 4:
            return 1.0
        elif found >= 3:
            return 0.75
        elif found >= 2:
            return 0.6
        else:
            return 0.5  # only amount
