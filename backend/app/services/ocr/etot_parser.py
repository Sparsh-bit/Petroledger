"""PetroLedger — ETOT Receipt OCR Service (AWS Textract).

Parses ETOT-MAIN pump receipts.  Each receipt records cumulative lifetime
meter totals per nozzle:

    NOZZLE : N
    A:<amount>      ← cumulative ₹ dispensed since machine install
    V:<volume>      ← cumulative litres dispensed since machine install
    TOT SALES:<n>  ← cumulative transaction count since machine install

Two receipts are printed per shift (opening + closing).  Shift sale = closing A − opening A.
"""

from __future__ import annotations

import asyncio
import functools
import re
from decimal import Decimal, InvalidOperation

import boto3

from app.core.config import get_settings
from app.core.exceptions import ValidationError

settings = get_settings()


class ETOTParserService:
    """Sends receipt images to AWS Textract and parses ETOT-MAIN structure."""

    def __init__(self) -> None:
        self._client = boto3.client(
            "textract",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

    async def parse_image(self, file_bytes: bytes) -> dict:
        """Send *file_bytes* to Textract, extract text lines, parse ETOT structure.

        Returns a dict::

            {
                "pump_serial": str | None,
                "print_datetime": str | None,
                "nozzles": [
                    {
                        "nozzle_number": int,
                        "amount_cumulative": Decimal,
                        "volume_cumulative": Decimal,
                        "tot_sales_cumulative": int,
                    },
                    ...
                ]
            }

        Raises
        ------
        ValidationError
            When no nozzle data is found or a nozzle's fields are incomplete.
        """
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            functools.partial(
                self._client.detect_document_text,
                Document={"Bytes": file_bytes},
            ),
        )
        lines = [
            block["Text"]
            for block in response["Blocks"]
            if block["BlockType"] == "LINE"
        ]
        return self._parse_etot_lines(lines)

    # ── Parser ───────────────────────────────────────────────────────────

    def _parse_etot_lines(self, lines: list[str]) -> dict:
        """Parse ETOT-MAIN receipt lines into structured data.

        Receipt structure per nozzle (always in this order):
          NOZZLE : N
          A:XXXXXXX.XXX
          V:XXXXXXX.XXX
          TOT SALES:XXXXXX
        """
        result: dict = {
            "pump_serial": None,
            "print_datetime": None,
            "nozzles": [],
        }

        current_nozzle: dict | None = None

        for raw_line in lines:
            line = raw_line.strip()

            # Pump serial number (e.g. 16EC1035V)
            if re.match(r"^[0-9]{2}[A-Z]{2}[0-9]{4}[A-Z]$", line):
                result["pump_serial"] = line
                continue

            # Nozzle header — "NOZZLE : 1" or "NOZZLE: 1" or "NOZZLE 1"
            nozzle_match = re.match(
                r"NOZZLE\s*[:\s]\s*(\d+)", line, re.IGNORECASE
            )
            if nozzle_match:
                current_nozzle = {
                    "nozzle_number": int(nozzle_match.group(1)),
                    "amount_cumulative": None,
                    "volume_cumulative": None,
                    "tot_sales_cumulative": None,
                }
                result["nozzles"].append(current_nozzle)
                continue

            if current_nozzle is None:
                continue

            # A field — cumulative amount in ₹  (e.g. "A:25,707,038.550")
            a_match = re.match(r"^A\s*[:\s]\s*([\d,]+\.?\d*)", line, re.IGNORECASE)
            if a_match and current_nozzle["amount_cumulative"] is None:
                try:
                    current_nozzle["amount_cumulative"] = Decimal(
                        a_match.group(1).replace(",", "")
                    )
                except InvalidOperation:
                    pass
                continue

            # V field — cumulative volume in litres  (e.g. "V:279,141.470")
            v_match = re.match(r"^V\s*[:\s]\s*([\d,]+\.?\d*)", line, re.IGNORECASE)
            if v_match and current_nozzle["volume_cumulative"] is None:
                try:
                    current_nozzle["volume_cumulative"] = Decimal(
                        v_match.group(1).replace(",", "")
                    )
                except InvalidOperation:
                    pass
                continue

            # TOT SALES field — cumulative transaction count  (e.g. "TOT SALES:113354")
            tot_match = re.match(
                r"TOT\s*SALES\s*[:\s]\s*(\d+)", line, re.IGNORECASE
            )
            if tot_match and current_nozzle["tot_sales_cumulative"] is None:
                current_nozzle["tot_sales_cumulative"] = int(tot_match.group(1))
                continue

        # ── Validation ───────────────────────────────────────────────────

        if not result["nozzles"]:
            raise ValidationError(
                message=(
                    "No nozzle data found in receipt. "
                    "Check image quality and ensure the full receipt is visible."
                )
            )

        for nozzle in result["nozzles"]:
            missing = [
                k
                for k in ("amount_cumulative", "volume_cumulative", "tot_sales_cumulative")
                if nozzle[k] is None
            ]
            if missing:
                raise ValidationError(
                    message=(
                        f"Nozzle {nozzle['nozzle_number']} is missing fields after OCR: "
                        f"{missing}. Image may be blurry or cropped. "
                        f"Use manual entry instead."
                    )
                )

        return result


# ── FastAPI dependency ────────────────────────────────────────────────────────


async def get_ocr_service() -> ETOTParserService:
    """FastAPI dependency — returns a fresh ETOTParserService per request."""
    return ETOTParserService()
