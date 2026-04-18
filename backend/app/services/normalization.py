"""
PetroLedger — Record Normalisation Service.

Converts parsed data-class records (``UPIRecord``, ``POSRecord``,
``PumpLogRecord``) into SQLAlchemy ORM instances ready for database
insertion.  Handles:

* Setting ``content_hash`` for deduplication.
* Resolving ``nozzle_number`` → ``nozzle_id`` via DB lookup.
* Conflict-safe bulk insert (``ON CONFLICT DO NOTHING`` on ``content_hash``).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.pump import Nozzle
from app.models.transaction import POSTransaction, PumpLog, UPITransaction
from app.services.deduplication import DeduplicationService
from app.services.parsers.pos_ocr import POSRecord
from app.services.parsers.pump_log import PumpLogRecord
from app.services.parsers.upi_csv import UPIRecord

logger = structlog.stdlib.get_logger("petroledger.services.normalization")


class NormalizationService:
    """
    Converts parsed records into ORM model instances and inserts them.

    Usage::

        norm = NormalizationService()
        txns = await norm.normalize_upi_records(records, shift_id, db)
        count = await norm.bulk_insert(db, txns)
    """

    def __init__(self) -> None:
        self._dedup = DeduplicationService()

    # ── UPI ─────────────────────────────────────────────────────────

    async def normalize_upi_records(
        self,
        records: list[UPIRecord],
        shift_id: uuid.UUID,
        db: AsyncSession,
        org_id: uuid.UUID,
    ) -> list[UPITransaction]:
        """
        Convert :class:`UPIRecord` instances into :class:`UPITransaction`
        ORM objects linked to *shift_id*, with ``content_hash`` set.
        """
        models: list[UPITransaction] = []

        for rec in records:
            content_hash = self._dedup.generate_upi_hash(rec)

            txn = UPITransaction(
                id=uuid.uuid4(),
                org_id=org_id,
                shift_id=shift_id,
                amount=Decimal(str(rec.amount)),
                upi_ref=rec.txn_id,
                bank=rec.bank or None,
                timestamp=rec.timestamp,
                raw_data=rec.raw_row,
                content_hash=content_hash,
            )
            models.append(txn)

        logger.info(
            "upi_normalized",
            count=len(models),
            shift_id=str(shift_id),
        )
        return models

    # ── POS ─────────────────────────────────────────────────────────

    async def normalize_pos_records(
        self,
        records: list[POSRecord],
        shift_id: uuid.UUID,
        db: AsyncSession,
        org_id: uuid.UUID,
    ) -> list[POSTransaction]:
        """
        Convert :class:`POSRecord` instances into :class:`POSTransaction`
        ORM objects linked to *shift_id*, with ``content_hash`` set.
        """
        models: list[POSTransaction] = []

        for rec in records:
            content_hash = self._dedup.generate_pos_hash(rec)

            txn = POSTransaction(
                id=uuid.uuid4(),
                org_id=org_id,
                shift_id=shift_id,
                amount=Decimal(str(rec.amount)),
                terminal_id=rec.terminal_id,
                timestamp=rec.timestamp,
                content_hash=content_hash,
            )
            models.append(txn)

        logger.info(
            "pos_normalized",
            count=len(models),
            shift_id=str(shift_id),
        )
        return models

    # ── Pump Logs ───────────────────────────────────────────────────

    async def normalize_pump_logs(
        self,
        records: list[PumpLogRecord],
        shift_id: uuid.UUID,
        pump_id: uuid.UUID,
        db: AsyncSession,
        org_id: uuid.UUID,
    ) -> list[PumpLog]:
        """
        Convert :class:`PumpLogRecord` instances into :class:`PumpLog`
        ORM objects.

        Resolves ``nozzle_number`` → ``nozzle_id`` by querying the
        ``nozzles`` table for the given *pump_id*.  If a nozzle is not
        found, the record is skipped and an error is logged.
        """
        # Pre-fetch nozzle mapping for this pump: {nozzle_number: nozzle_id}
        nozzle_map = await self._build_nozzle_map(db, pump_id)

        models: list[PumpLog] = []
        skipped = 0

        for rec in records:
            nozzle_id = nozzle_map.get(rec.nozzle_number)
            if nozzle_id is None:
                logger.warning(
                    "nozzle_not_found",
                    nozzle_number=rec.nozzle_number,
                    pump_id=str(pump_id),
                )
                skipped += 1
                continue

            content_hash = self._dedup.generate_pump_hash(rec)

            log = PumpLog(
                id=uuid.uuid4(),
                org_id=org_id,
                shift_id=shift_id,
                nozzle_id=nozzle_id,
                start_reading=Decimal(str(rec.start_reading)),
                end_reading=Decimal(str(rec.end_reading)),
                volume_dispensed=Decimal(str(rec.volume_dispensed)),
                fuel_type=rec.fuel_type,
                content_hash=content_hash,
            )
            models.append(log)

        logger.info(
            "pump_logs_normalized",
            count=len(models),
            skipped=skipped,
            shift_id=str(shift_id),
            pump_id=str(pump_id),
        )
        return models

    # ── Bulk Insert ─────────────────────────────────────────────────

    @staticmethod
    async def bulk_insert(
        db: AsyncSession,
        instances: Sequence[UPITransaction | POSTransaction | PumpLog],
    ) -> int:
        """
        Insert ORM instances in bulk, skipping rows whose
        ``content_hash`` already exists (``ON CONFLICT DO NOTHING``).

        Parameters
        ----------
        db:
            Async database session.
        instances:
            Homogeneous list of ORM model instances (all same type).

        Returns
        -------
        int
            Number of rows actually inserted.
        """
        if not instances:
            return 0

        # Determine table from first instance
        model_cls = type(instances[0])
        table = model_cls.__table__

        # Build list of value dicts
        rows: list[dict[str, Any]] = []
        for inst in instances:
            row: dict[str, Any] = {}
            for col in table.columns:
                row[col.name] = getattr(inst, col.name, None)
            rows.append(row)

        stmt = (
            pg_insert(table)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=["org_id", "content_hash"],
            )
        )

        result = await db.execute(stmt)
        await db.flush()

        inserted = result.rowcount  # type: ignore[union-attr]
        logger.info(
            "bulk_insert_complete",
            table=table.name,
            attempted=len(rows),
            inserted=inserted,
        )
        return inserted

    # ── Private helpers ─────────────────────────────────────────────

    @staticmethod
    async def _build_nozzle_map(
        db: AsyncSession,
        pump_id: uuid.UUID,
    ) -> dict[int, uuid.UUID]:
        """
        Query all nozzles for a pump and return ``{nozzle_number: nozzle_id}``.

        Raises :class:`NotFoundError` if the pump has zero nozzles.
        """
        stmt = select(Nozzle.nozzle_number, Nozzle.id).where(
            Nozzle.pump_id == pump_id
        )
        result = await db.execute(stmt)
        mapping = {row.nozzle_number: row.id for row in result.all()}

        if not mapping:
            raise NotFoundError(
                resource="Nozzle",
                message=f"No nozzles found for pump {pump_id}",
            )

        logger.debug(
            "nozzle_map_built",
            pump_id=str(pump_id),
            nozzles=list(mapping.keys()),
        )
        return mapping
