"""
PetroLedger — Transaction Deduplication Service.

Generates deterministic content hashes for UPI, POS, and Pump-Log records
and checks them against the database to prevent duplicate inserts.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import POSTransaction, PumpLog, UPITransaction
from app.services.parsers.pos_ocr import POSRecord
from app.services.parsers.pump_log import PumpLogRecord
from app.services.parsers.upi_csv import UPIRecord

logger = structlog.stdlib.get_logger("petroledger.services.deduplication")

T = TypeVar("T")


class DeduplicationService:
    """
    Duplicate-detection service for all transaction types.

    Each ``generate_*_hash`` method produces a deterministic SHA-256
    digest from the record's identifying fields.  The ``check_*_duplicate``
    methods query the corresponding table's ``content_hash`` column
    scoped to the organisation.

    Usage::

        svc = DeduplicationService()
        h   = svc.generate_upi_hash(record)
        dup = await svc.check_upi_duplicate(db, h, org_id)
    """

    # ── Hash Generation ─────────────────────────────────────────────

    @staticmethod
    def generate_upi_hash(record: UPIRecord) -> str:
        """
        SHA-256 of ``txn_id + amount + date(YYYY-MM-DD) + bank``.

        Deterministic for the same logical transaction regardless of
        which shift it gets attached to.
        """
        date_str = record.timestamp.strftime("%Y-%m-%d")
        payload = f"{record.txn_id}|{record.amount}|{date_str}|{record.bank}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_pos_hash(record: POSRecord) -> str:
        """
        SHA-256 of ``approval_code + amount + terminal_id + date``.
        """
        date_str = record.timestamp.strftime("%Y-%m-%d")
        payload = (
            f"{record.approval_code}|{record.amount}"
            f"|{record.terminal_id}|{date_str}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_pump_hash(record: PumpLogRecord) -> str:
        """
        SHA-256 of ``nozzle_number + start_reading + end_reading + date``.
        """
        date_str = record.timestamp.strftime("%Y-%m-%d")
        payload = (
            f"{record.nozzle_number}|{record.start_reading}"
            f"|{record.end_reading}|{date_str}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ── Duplicate Checks ────────────────────────────────────────────

    @staticmethod
    async def check_upi_duplicate(
        db: AsyncSession,
        content_hash: str,
        org_id: uuid.UUID,
    ) -> bool:
        """Return ``True`` if a UPI transaction with this hash already exists for the org."""
        stmt = (
            select(UPITransaction.id)
            .where(
                UPITransaction.org_id == org_id,
                UPITransaction.content_hash == content_hash,
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def check_pos_duplicate(
        db: AsyncSession,
        content_hash: str,
        org_id: uuid.UUID,
    ) -> bool:
        """Return ``True`` if a POS transaction with this hash already exists for the org."""
        stmt = (
            select(POSTransaction.id)
            .where(
                POSTransaction.org_id == org_id,
                POSTransaction.content_hash == content_hash,
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def check_pump_duplicate(
        db: AsyncSession,
        content_hash: str,
        org_id: uuid.UUID,
    ) -> bool:
        """Return ``True`` if a pump log with this hash already exists for the org."""
        stmt = (
            select(PumpLog.id)
            .where(
                PumpLog.org_id == org_id,
                PumpLog.content_hash == content_hash,
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    # ── Bulk Filtering ──────────────────────────────────────────────

    async def filter_duplicates(
        self,
        records: list[T],
        hash_fn: Callable[[T], str],
        check_fn: Callable[
            [AsyncSession, str, uuid.UUID],
            Coroutine[Any, Any, bool],
        ],
        db: AsyncSession,
        org_id: uuid.UUID,
    ) -> tuple[list[T], list[T]]:
        """
        Split a list of records into new and duplicate buckets.

        Parameters
        ----------
        records:
            Parsed records (UPIRecord, POSRecord, or PumpLogRecord).
        hash_fn:
            The ``generate_*_hash`` method for this record type.
        check_fn:
            The ``check_*_duplicate`` method for this record type.
        db:
            Async database session.
        org_id:
            Organisation UUID for scoping.

        Returns
        -------
        tuple[list, list]
            ``(new_records, duplicate_records)``
        """
        new_records: list[T] = []
        duplicate_records: list[T] = []
        seen_hashes: set[str] = set()

        for record in records:
            h = hash_fn(record)

            # Intra-batch dedup
            if h in seen_hashes:
                duplicate_records.append(record)
                continue
            seen_hashes.add(h)

            # DB dedup
            if await check_fn(db, h, org_id):
                duplicate_records.append(record)
            else:
                new_records.append(record)

        logger.info(
            "dedup_complete",
            total=len(records),
            new=len(new_records),
            duplicates=len(duplicate_records),
        )
        return new_records, duplicate_records
