"""
PetroLedger — Shift Report Generator.

Produces a single-shift PDF report using Jinja2 HTML templates
rendered to PDF via WeasyPrint.

Report contents:
  • Site name, shift number, date, attendant names
  • FMS / UPI / Card / Fleet totals
  • Expected vs Actual cash, Variance (MATCH / SHORTAGE / EXCESS)
  • Confidence score with band (HIGH / MEDIUM / LOW)
  • Anomaly flags for the shift
  • Nozzle-wise dispensing breakdown
  • Footer: generated timestamp + CONFIDENTIAL label
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignments import AnomalyFlag
from app.models.fms import (
    FleetTransaction,
    FmsTransaction,
    PosBatchSettlement,
)
from app.models.reconciliation import ReconciliationResult
from app.models.shift import Shift
from app.models.transaction import UPITransaction
from app.utils.datetime import format_ist, to_ist

log = structlog.stdlib.get_logger("petroledger.reports.shift")

_REPORTS_DIR = Path(os.environ.get("REPORTS_DIR", "./reports"))


# ── Jinja2 HTML Template ─────────────────────────────────────────────────

_SHIFT_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; font-size: 11px; color: #333; margin: 0; padding: 20px; }
    h1 { font-size: 18px; margin-bottom: 2px; }
    h2 { font-size: 13px; margin-top: 16px; margin-bottom: 6px; border-bottom: 1px solid #ccc; padding-bottom: 3px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
    th { background: #1a3a5c; color: white; padding: 6px 8px; text-align: left; }
    td { padding: 5px 8px; border-bottom: 1px solid #eee; }
    tr:nth-child(even) td { background: #f7f7f7; }
    .total-row td { font-weight: bold; background: #eef4ff; }
    .variance-match { color: #16a34a; font-weight: bold; }
    .variance-shortage { color: #dc2626; font-weight: bold; }
    .variance-excess { color: #d97706; font-weight: bold; }
    .badge-high { background: #dc2626; color: white; padding: 2px 6px; border-radius: 3px; }
    .badge-medium { background: #d97706; color: white; padding: 2px 6px; border-radius: 3px; }
    .badge-low { background: #16a34a; color: white; padding: 2px 6px; border-radius: 3px; }
    .confidence-HIGH { color: #16a34a; font-weight: bold; }
    .confidence-MEDIUM { color: #d97706; font-weight: bold; }
    .confidence-LOW { color: #dc2626; font-weight: bold; }
    .footer { margin-top: 30px; font-size: 9px; color: #999; border-top: 1px solid #ccc; padding-top: 6px; }
    .right { text-align: right; }
    .header-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px; }
    .header-item { font-size: 11px; }
    .header-item .label { color: #666; font-size: 10px; }
    .summary-box { background: #f0f4ff; border: 1px solid #c7d7f5; border-radius: 4px;
                   padding: 12px; margin-bottom: 12px; }
    .summary-row { display: flex; justify-content: space-between; margin-bottom: 4px; }
  </style>
</head>
<body>

<h1>&#9981; PetroLedger — Shift Reconciliation Report</h1>
<div style="color: #666; font-size: 10px; margin-bottom: 16px;">CONFIDENTIAL — OWNER ONLY</div>

<div class="header-grid">
  <div class="header-item"><div class="label">Site</div><strong>{{ site_name }}</strong></div>
  <div class="header-item"><div class="label">Shift Date</div><strong>{{ shift_date }}</strong></div>
  <div class="header-item"><div class="label">Shift</div><strong>{{ shift_start }} – {{ shift_end }}</strong></div>
  <div class="header-item"><div class="label">Attendant</div><strong>{{ attendant_name }}</strong></div>
  <div class="header-item"><div class="label">Shift ID</div><span style="font-size:9px">{{ shift_id }}</span></div>
  <div class="header-item"><div class="label">Status</div><strong>{{ shift_status }}</strong></div>
</div>

<h2>Payment Summary</h2>
<table>
  <tr><th>Source</th><th class="right">Amount (₹)</th></tr>
  <tr><td>FMS Total (Dispensed)</td><td class="right">{{ fms_total }}</td></tr>
  <tr><td>UPI Payments</td><td class="right">{{ upi_total }}</td></tr>
  <tr><td>Card / POS Payments</td><td class="right">{{ card_total }}</td></tr>
  <tr><td>Fleet Card Payments</td><td class="right">{{ fleet_total }}</td></tr>
  <tr class="total-row"><td>Expected Cash</td><td class="right">{{ expected_cash }}</td></tr>
  <tr class="total-row"><td>Actual Cash (Submitted)</td><td class="right">{{ actual_cash }}</td></tr>
  <tr>
    <td><strong>Variance</strong></td>
    <td class="right">
      <span class="variance-{{ variance_class }}">
        ₹{{ variance }} ({{ variance_type }})
      </span>
    </td>
  </tr>
</table>

<div class="summary-box">
  <div class="summary-row">
    <span>Confidence Score</span>
    <span class="confidence-{{ confidence_band }}">
      {{ confidence_score }}% — {{ confidence_band }}
    </span>
  </div>
  {% if review_reasons %}
  <div style="font-size:10px; color:#c00; margin-top:6px;">
    ⚠ Requires manual review:<br>
    {% for reason in review_reasons %}&nbsp;&nbsp;• {{ reason }}<br>{% endfor %}
  </div>
  {% endif %}
</div>

{% if anomalies %}
<h2>Anomaly Flags ({{ anomalies|length }})</h2>
<table>
  <tr><th>Type</th><th>Description</th><th>Severity</th><th class="right">Amount (₹)</th></tr>
  {% for a in anomalies %}
  <tr>
    <td>{{ a.flag_type }}</td>
    <td>{{ a.description }}</td>
    <td><span class="badge-{{ a.severity|lower }}">{{ a.severity }}</span></td>
    <td class="right">{{ a.amount or "—" }}</td>
  </tr>
  {% endfor %}
</table>
{% else %}
<h2>Anomaly Flags</h2>
<p style="color:#16a34a">✓ No anomalies detected for this shift.</p>
{% endif %}

{% if nozzle_rows %}
<h2>Nozzle-wise Dispensing Breakdown</h2>
<table>
  <tr><th>Nozzle</th><th>Product</th><th class="right">Transactions</th><th class="right">Volume (L)</th><th class="right">Amount (₹)</th></tr>
  {% for n in nozzle_rows %}
  <tr>
    <td>{{ n.nozzle_ref }}</td>
    <td>{{ n.product }}</td>
    <td class="right">{{ n.txn_count }}</td>
    <td class="right">{{ n.volume }}</td>
    <td class="right">{{ n.amount }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

<div class="footer">
  Generated: {{ generated_at }} IST &nbsp;|&nbsp; PetroLedger v1.0 &nbsp;|&nbsp; CONFIDENTIAL — OWNER ONLY
</div>
</body>
</html>"""


# ── Service ──────────────────────────────────────────────────────────────


class ShiftReportService:
    """Generates a PDF reconciliation report for a single shift."""

    def __init__(self) -> None:
        self._jinja_env = Environment(autoescape=select_autoescape(["html"]))
        self._template = self._jinja_env.from_string(_SHIFT_REPORT_TEMPLATE)

    async def generate(
        self,
        shift_id: uuid.UUID,
        db: AsyncSession,
    ) -> Path:
        """Generate a shift PDF report and return its file path.

        The file is written to ``REPORTS_DIR/{site_id}_{date}_{shift_id_short}.pdf``.
        Returns the ``Path`` to the written file so callers can stream it.
        """
        context = await self._build_context(shift_id, db)
        html = self._template.render(**context)
        output_path = self._output_path(context)
        _write_pdf(html, output_path)
        log.info("shift_report_generated", shift_id=str(shift_id), path=str(output_path))
        return output_path

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    async def _build_context(
        self,
        shift_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        shift = await self._load_shift(shift_id, db)
        recon = await self._load_recon(shift_id, db)
        anomalies = await self._load_anomaly_flags(shift_id, db)
        nozzle_rows = await self._build_nozzle_rows(shift_id, db)

        # Site name via pump → org
        site_name = shift.pump.organization.name if (
            hasattr(shift.pump, "organization") and shift.pump.organization
        ) else str(shift.pump.org_id)

        # Attendant name via worker → user
        attendant_name = (
            shift.worker.user.email
            if hasattr(shift.worker, "user") and shift.worker.user
            else str(shift.worker_id)
        )

        start_ist = to_ist(shift.start_time)
        end_ist = to_ist(shift.end_time) if shift.end_time else None

        expected = recon.expected_cash if recon else Decimal("0")
        actual = recon.actual_cash if recon else Decimal("0")
        variance = recon.variance if recon else Decimal("0")

        if variance == 0:
            variance_class, variance_type = "match", "MATCH"
        elif variance > 0:
            variance_class, variance_type = "shortage", "SHORTAGE"
        else:
            variance_class, variance_type = "excess", "EXCESS"

        raw_score = (
            int(float(recon.confidence_score) * 100)
            if recon and recon.confidence_score is not None
            else None
        )
        if raw_score is None:
            confidence_score, confidence_band = "N/A", "MEDIUM"
        elif raw_score >= 90:
            confidence_score, confidence_band = str(raw_score), "HIGH"
        elif raw_score >= 70:
            confidence_score, confidence_band = str(raw_score), "MEDIUM"
        else:
            confidence_score, confidence_band = str(raw_score), "LOW"

        # Collect review reasons from anomalies JSON on recon result
        review_reasons: list[str] = []
        if recon and recon.anomalies:
            for a in recon.anomalies:
                if isinstance(a, dict) and a.get("severity") in ("high", "critical"):
                    review_reasons.append(a.get("description", "High-severity anomaly"))

        # Determine fms/upi/card/fleet totals from anomaly JSON or default to 0
        # (stored in reconciliation_result.anomalies or computed from raw tables)
        fms_total, upi_total, card_total, fleet_total = await self._load_totals(shift_id, db)

        return {
            "site_name": site_name,
            "shift_date": start_ist.strftime("%d %b %Y"),
            "shift_start": start_ist.strftime("%H:%M"),
            "shift_end": end_ist.strftime("%H:%M") if end_ist else "—",
            "attendant_name": attendant_name,
            "shift_id": str(shift_id),
            "shift_status": shift.status.value.upper(),
            "fms_total": f"{fms_total:,.2f}",
            "upi_total": f"{upi_total:,.2f}",
            "card_total": f"{card_total:,.2f}",
            "fleet_total": f"{fleet_total:,.2f}",
            "expected_cash": f"{expected:,.2f}",
            "actual_cash": f"{actual:,.2f}",
            "variance": f"{abs(variance):,.2f}",
            "variance_class": variance_class,
            "variance_type": variance_type,
            "confidence_score": confidence_score,
            "confidence_band": confidence_band,
            "review_reasons": review_reasons,
            "anomalies": [
                {
                    "flag_type": a.flag_type.value,
                    "description": a.description,
                    "severity": a.severity.value,
                    "amount": f"{a.amount:,.2f}" if a.amount else None,
                }
                for a in anomalies
            ],
            "nozzle_rows": nozzle_rows,
            "generated_at": format_ist(datetime.now(UTC)),
            # Extra fields for file naming
            "_site_id": str(shift.pump.org_id),
            "_shift_date_iso": start_ist.strftime("%Y-%m-%d"),
            "_shift_id_short": str(shift_id)[:8],
        }

    def _output_path(self, context: dict[str, Any]) -> Path:
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        filename = (
            f"{context['_site_id']}_{context['_shift_date_iso']}"
            f"_{context['_shift_id_short']}.pdf"
        )
        return _REPORTS_DIR / filename

    # ------------------------------------------------------------------
    # Data loaders
    # ------------------------------------------------------------------

    @staticmethod
    async def _load_shift(shift_id: uuid.UUID, db: AsyncSession) -> Shift:
        from app.core.exceptions import NotFoundError

        result = await db.execute(select(Shift).where(Shift.id == shift_id))
        shift = result.scalar_one_or_none()
        if shift is None:
            raise NotFoundError(resource="Shift", identifier=str(shift_id))
        return shift

    @staticmethod
    async def _load_recon(
        shift_id: uuid.UUID, db: AsyncSession
    ) -> ReconciliationResult | None:
        result = await db.execute(
            select(ReconciliationResult).where(ReconciliationResult.shift_id == shift_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _load_anomaly_flags(
        shift_id: uuid.UUID, db: AsyncSession
    ) -> list[AnomalyFlag]:
        result = await db.execute(
            select(AnomalyFlag).where(AnomalyFlag.shift_id == shift_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def _load_totals(
        shift_id: uuid.UUID, db: AsyncSession
    ) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        from sqlalchemy import func

        from app.models.fms import FmsTxnStatus

        def _sum(stmt):
            return db.execute(stmt)

        fms_stmt = select(
            func.coalesce(func.sum(FmsTransaction.amount), 0)
        ).where(
            FmsTransaction.shift_id == shift_id,
            FmsTransaction.status == FmsTxnStatus.COMPLETED,
            FmsTransaction.is_deleted.is_(False),
        )
        upi_stmt = select(
            func.coalesce(func.sum(UPITransaction.amount), 0)
        ).where(UPITransaction.shift_id == shift_id)
        card_stmt = select(
            func.coalesce(func.sum(PosBatchSettlement.gross_amount), 0)
        ).where(
            PosBatchSettlement.shift_id == shift_id,
            PosBatchSettlement.is_deleted.is_(False),
        )
        fleet_stmt = select(
            func.coalesce(func.sum(FleetTransaction.total_amount), 0)
        ).where(
            FleetTransaction.shift_id == shift_id,
            FleetTransaction.is_deleted.is_(False),
        )

        fms = Decimal(str((await db.execute(fms_stmt)).scalar_one()))
        upi = Decimal(str((await db.execute(upi_stmt)).scalar_one()))
        card = Decimal(str((await db.execute(card_stmt)).scalar_one()))
        fleet = Decimal(str((await db.execute(fleet_stmt)).scalar_one()))
        return fms, upi, card, fleet

    @staticmethod
    async def _build_nozzle_rows(
        shift_id: uuid.UUID, db: AsyncSession
    ) -> list[dict[str, Any]]:
        from sqlalchemy import func

        from app.models.fms import FmsTxnStatus

        stmt = (
            select(
                FmsTransaction.nozzle_id,
                FmsTransaction.product_code,
                func.count().label("txn_count"),
                func.coalesce(func.sum(FmsTransaction.volume_litres), 0).label("volume"),
                func.coalesce(func.sum(FmsTransaction.amount), 0).label("amount"),
            )
            .where(
                FmsTransaction.shift_id == shift_id,
                FmsTransaction.status == FmsTxnStatus.COMPLETED,
                FmsTransaction.is_deleted.is_(False),
            )
            .group_by(FmsTransaction.nozzle_id, FmsTransaction.product_code)
        )
        rows = (await db.execute(stmt)).all()
        return [
            {
                "nozzle_ref": str(r.nozzle_id)[:8],
                "product": r.product_code or "—",
                "txn_count": r.txn_count,
                "volume": f"{Decimal(str(r.volume)):,.3f}",
                "amount": f"{Decimal(str(r.amount)):,.2f}",
            }
            for r in rows
        ]


# ── PDF writer (sync — WeasyPrint is synchronous) ────────────────────────

def _write_pdf(html: str, output_path: Path) -> None:
    """Render HTML to PDF and write to *output_path*."""
    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(str(output_path))
    except ImportError:
        # WeasyPrint may not be available in test environments.
        # Write an HTML placeholder so download endpoints still function.
        output_path.with_suffix(".html").write_text(html, encoding="utf-8")
        log.warning("weasyprint_not_installed", output=str(output_path))
