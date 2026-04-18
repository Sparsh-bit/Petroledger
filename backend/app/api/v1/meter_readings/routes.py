"""PetroLedger — Meter Reading API Routes.

POST /meter-readings/shifts/{shift_id}/upload   — OCR receipt image
POST /meter-readings/shifts/{shift_id}/manual   — manual JSON entry
GET  /meter-readings/shifts/{shift_id}          — shift meter summary
DELETE /meter-readings/shifts/{shift_id}/nozzle/{nozzle_id} — delete a reading
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_active_user
from app.api.deps.rbac import require_role
from app.core.exceptions import NotFoundError, ValidationError
from app.core.tenant import verify_tenant_match
from app.db.session import get_db
from app.models.assignments import NozzleAssignment
from app.models.nozzle_meter_reading import NozzleMeterReading
from app.models.nozzle_shift_sale import NozzleShiftSale
from app.models.organization import Organization
from app.models.pump import Nozzle, Pump
from app.models.shift import Shift, ShiftStatus
from app.models.user import User, UserRole
from app.models.worker import Worker
from app.schemas.meter_reading import (
    MeterReadingManualRequest,
    MeterReadingUploadResponse,
    NozzleReadingResult,
    NozzleShiftSaleDetail,
    ShiftMeterSummary,
)
from app.services.ocr.etot_parser import ETOTParserService, get_ocr_service

router = APIRouter()

_MANAGER_ROLES = (UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


# ── POST /shifts/{shift_id}/upload — OCR path ────────────────────────────────


@router.post(
    "/shifts/{shift_id}/upload",
    response_model=MeterReadingUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload ETOT receipt image (OCR via AWS Textract)",
)
async def upload_meter_reading(
    shift_id: uuid.UUID,
    file: UploadFile = File(..., description="JPEG or PNG receipt image"),
    reading_type: Literal["opening", "closing"] = Form(
        ..., description="'opening' or 'closing'"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(*_MANAGER_ROLES)),
    ocr_svc: ETOTParserService = Depends(get_ocr_service),
) -> MeterReadingUploadResponse:
    """Upload a receipt image. Textract OCR extracts nozzle meter values.

    Stores readings, auto-computes shift sale when both opening and closing
    exist for a nozzle. File bytes are discarded after OCR — not stored.
    """
    shift = await _get_open_shift(shift_id, current_user, db)

    content_type = file.content_type or ""
    if content_type not in ("image/jpeg", "image/png", "image/jpg"):
        raise ValidationError(
            message=f"Invalid file type '{content_type}'. Accepted: image/jpeg, image/png."
        )

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_IMAGE_BYTES:
        raise ValidationError(message="File too large. Maximum size is 10 MB.")

    ocr_result = await ocr_svc.parse_image(file_bytes)
    del file_bytes  # discard immediately after OCR

    nozzle_results, all_warnings = await _process_parsed_readings(
        shift=shift,
        reading_type=reading_type,
        nozzle_data=ocr_result["nozzles"],
        entered_manually=False,
        current_user=current_user,
        db=db,
    )

    return MeterReadingUploadResponse(
        shift_id=shift_id,
        reading_type=reading_type,
        processed_nozzles=nozzle_results,
        ocr_used=True,
        warnings=all_warnings,
    )


# ── POST /shifts/{shift_id}/manual — manual JSON path ───────────────────────


@router.post(
    "/shifts/{shift_id}/manual",
    response_model=MeterReadingUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit meter readings manually (JSON)",
)
async def manual_meter_reading(
    shift_id: uuid.UUID,
    payload: MeterReadingManualRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(*_MANAGER_ROLES)),
) -> MeterReadingUploadResponse:
    """Accept meter readings as a JSON body instead of an image."""
    shift = await _get_open_shift(shift_id, current_user, db)

    nozzle_data = [
        {
            "nozzle_number": r.nozzle_number,
            "amount_cumulative": r.amount_cumulative,
            "volume_cumulative": r.volume_cumulative,
            "tot_sales_cumulative": r.tot_sales_cumulative,
        }
        for r in payload.nozzle_readings
    ]

    nozzle_results, all_warnings = await _process_parsed_readings(
        shift=shift,
        reading_type=payload.reading_type,
        nozzle_data=nozzle_data,
        entered_manually=True,
        current_user=current_user,
        db=db,
    )

    return MeterReadingUploadResponse(
        shift_id=shift_id,
        reading_type=payload.reading_type,
        processed_nozzles=nozzle_results,
        ocr_used=False,
        warnings=all_warnings,
    )


# ── GET /shifts/{shift_id} — meter summary ───────────────────────────────────


@router.get(
    "/shifts/{shift_id}",
    response_model=ShiftMeterSummary,
    summary="Get meter reading summary for a shift",
)
async def get_shift_meter_summary(
    shift_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ShiftMeterSummary:
    """Return all computed nozzle shift sales and completeness status."""
    await _verify_shift_tenant(shift_id, current_user, db)

    sales_stmt = select(NozzleShiftSale).where(NozzleShiftSale.shift_id == shift_id)
    sales = (await db.execute(sales_stmt)).scalars().all()

    # Collect nozzle numbers that have readings (may be incomplete)
    readings_stmt = (
        select(NozzleMeterReading.nozzle_id)
        .where(NozzleMeterReading.shift_id == shift_id)
        .distinct()
    )
    nozzles_with_readings = set(
        (await db.execute(readings_stmt)).scalars().all()
    )

    # All active nozzles on this shift's pump
    pump_id = (
        await db.execute(select(Shift.pump_id).where(Shift.id == shift_id))
    ).scalar_one()
    all_nozzles_stmt = select(Nozzle).where(
        Nozzle.pump_id == pump_id, Nozzle.is_active.is_(True)
    )
    all_nozzles = (await db.execute(all_nozzles_stmt)).scalars().all()
    all_nozzle_ids = {n.id for n in all_nozzles}
    nozzle_num_map = {n.id: n.nozzle_number for n in all_nozzles}

    missing_nozzle_ids = all_nozzle_ids - {s.nozzle_id for s in sales}
    missing_nozzle_numbers = sorted(
        nozzle_num_map.get(nid, 0) for nid in missing_nozzle_ids
    )

    total_sale = sum(
        Decimal(str(s.shift_sale_amount)) for s in sales
    ) if sales else Decimal("0.00")

    nozzle_details = []
    for sale in sales:
        nozzle_num = nozzle_num_map.get(sale.nozzle_id, 0)
        worker_name = _resolve_worker_name(sale)
        nozzle_details.append(
            NozzleShiftSaleDetail(
                nozzle_number=nozzle_num,
                nozzle_id=sale.nozzle_id,
                worker_id=sale.worker_id,
                worker_name=worker_name,
                shift_sale_amount=Decimal(str(sale.shift_sale_amount)),
                shift_sale_volume=Decimal(str(sale.shift_sale_volume)),
                shift_transaction_count=sale.shift_transaction_count,
                is_verified=sale.is_verified,
            )
        )

    return ShiftMeterSummary(
        shift_id=shift_id,
        total_shift_sale=total_sale,
        nozzles=nozzle_details,
        readings_complete=len(missing_nozzle_ids) == 0 and bool(sales),
        missing_nozzles=missing_nozzle_numbers,
    )


# ── DELETE /shifts/{shift_id}/nozzle/{nozzle_id} ─────────────────────────────


@router.delete(
    "/shifts/{shift_id}/nozzle/{nozzle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a meter reading to allow re-upload",
)
async def delete_meter_reading(
    shift_id: uuid.UUID,
    nozzle_id: uuid.UUID,
    reading_type: Literal["opening", "closing"] = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
    ),
) -> None:
    """Delete a specific reading.  Also deletes the associated shift sale record."""
    await _verify_shift_tenant(shift_id, current_user, db)

    reading_stmt = select(NozzleMeterReading).where(
        NozzleMeterReading.shift_id == shift_id,
        NozzleMeterReading.nozzle_id == nozzle_id,
        NozzleMeterReading.reading_type == reading_type,
    )
    reading = (await db.execute(reading_stmt)).scalar_one_or_none()
    if reading is None:
        raise NotFoundError(
            resource="NozzleMeterReading",
            identifier=f"{shift_id}/{nozzle_id}/{reading_type}",
        )
    await db.delete(reading)

    # Also remove the computed shift sale so it can be recomputed on re-upload
    sale_stmt = select(NozzleShiftSale).where(
        NozzleShiftSale.shift_id == shift_id,
        NozzleShiftSale.nozzle_id == nozzle_id,
    )
    sale = (await db.execute(sale_stmt)).scalar_one_or_none()
    if sale is not None:
        await db.delete(sale)

    await db.flush()


# ── Shared Logic ─────────────────────────────────────────────────────────────


async def _process_parsed_readings(
    *,
    shift: Shift,
    reading_type: str,
    nozzle_data: list[dict],
    entered_manually: bool,
    current_user: User,
    db: AsyncSession,
) -> tuple[list[NozzleReadingResult], list[str]]:
    """Insert readings and compute shift sales for each nozzle in *nozzle_data*."""
    from app.core.exceptions import DuplicateError

    # Load all nozzles for this pump once
    nozzles_stmt = select(Nozzle).where(
        Nozzle.pump_id == shift.pump_id, Nozzle.is_active.is_(True)
    )
    nozzles = (await db.execute(nozzles_stmt)).scalars().all()
    nozzle_by_number: dict[int, Nozzle] = {n.nozzle_number: n for n in nozzles}

    results: list[NozzleReadingResult] = []
    all_warnings: list[str] = []

    for nozzle_raw in nozzle_data:
        n_num = nozzle_raw["nozzle_number"]
        nozzle = nozzle_by_number.get(n_num)
        if nozzle is None:
            raise ValidationError(
                message=f"Nozzle {n_num} not found on pump {shift.pump_id}."
            )

        # Look up active worker assignment for this shift + nozzle
        assign_stmt = select(NozzleAssignment).where(
            NozzleAssignment.shift_id == shift.id,
            NozzleAssignment.nozzle_id == nozzle.id,
            NozzleAssignment.relieved_at.is_(None),
        )
        assignment = (await db.execute(assign_stmt)).scalar_one_or_none()
        if assignment is None:
            raise ValidationError(
                message=(
                    f"No worker assigned to nozzle {n_num}. "
                    f"Assign a worker first."
                )
            )
        worker_id = assignment.attendant_id

        # Check for duplicate (UNIQUE constraint: shift_id + nozzle_id + reading_type)
        existing_stmt = select(NozzleMeterReading).where(
            NozzleMeterReading.shift_id == shift.id,
            NozzleMeterReading.nozzle_id == nozzle.id,
            NozzleMeterReading.reading_type == reading_type,
        )
        if (await db.execute(existing_stmt)).scalar_one_or_none() is not None:
            raise DuplicateError(
                f"{reading_type.capitalize()} reading already submitted for "
                f"nozzle {n_num}. Delete it first to re-upload."
            )

        reading = NozzleMeterReading(
            tenant_id=current_user.tenant_id,
            shift_id=shift.id,
            nozzle_id=nozzle.id,
            worker_id=worker_id,
            reading_type=reading_type,
            amount_cumulative=nozzle_raw["amount_cumulative"],
            volume_cumulative=nozzle_raw["volume_cumulative"],
            tot_sales_cumulative=nozzle_raw["tot_sales_cumulative"],
            receipt_image_url=None,
            entered_manually=entered_manually,
        )
        db.add(reading)
        await db.flush()

        # Attempt to compute shift sale (needs both opening + closing)
        nozzle_warnings = await _try_compute_shift_sale(shift.id, nozzle.id, db)
        shift_sale_computed = nozzle_warnings is not None
        sale_amount: Decimal | None = None
        if shift_sale_computed:
            sale_stmt = select(NozzleShiftSale).where(
                NozzleShiftSale.shift_id == shift.id,
                NozzleShiftSale.nozzle_id == nozzle.id,
            )
            sale = (await db.execute(sale_stmt)).scalar_one_or_none()
            if sale is not None:
                sale_amount = Decimal(str(sale.shift_sale_amount))
            all_warnings.extend(nozzle_warnings or [])

        # Resolve worker name for response
        worker_stmt = select(Worker).where(Worker.id == worker_id)
        worker = (await db.execute(worker_stmt)).scalar_one_or_none()
        worker_name = _worker_display_name(worker)

        results.append(
            NozzleReadingResult(
                nozzle_number=n_num,
                nozzle_id=nozzle.id,
                worker_id=worker_id,
                worker_name=worker_name,
                amount_cumulative=Decimal(str(nozzle_raw["amount_cumulative"])),
                volume_cumulative=Decimal(str(nozzle_raw["volume_cumulative"])),
                tot_sales_cumulative=nozzle_raw["tot_sales_cumulative"],
                shift_sale_computed=shift_sale_computed,
                shift_sale_amount=sale_amount,
            )
        )

    return results, all_warnings


async def _try_compute_shift_sale(
    shift_id: uuid.UUID,
    nozzle_id: uuid.UUID,
    db: AsyncSession,
) -> list[str] | None:
    """Upsert a NozzleShiftSale when both readings exist for this nozzle+shift.

    Returns a list of warnings (possibly empty) if the sale was computed, or
    None if not enough readings exist yet.
    """
    opening = await _get_reading(shift_id, nozzle_id, "opening", db)
    closing = await _get_reading(shift_id, nozzle_id, "closing", db)

    if opening is None or closing is None:
        return None

    closing_amount = Decimal(str(closing.amount_cumulative))
    opening_amount = Decimal(str(opening.amount_cumulative))

    if closing_amount < opening_amount:
        raise ValidationError(
            message=(
                f"Closing amount ({closing_amount}) is less than opening amount "
                f"({opening_amount}) for nozzle {nozzle_id}. "
                f"Wrong receipts may have been uploaded in wrong order."
            )
        )

    shift_sale = closing_amount - opening_amount
    shift_vol = Decimal(str(closing.volume_cumulative)) - Decimal(
        str(opening.volume_cumulative)
    )
    shift_txn = closing.tot_sales_cumulative - opening.tot_sales_cumulative

    warnings: list[str] = []
    if shift_sale > Decimal("500000"):
        warnings.append(
            f"Shift sale of ₹{shift_sale} for nozzle {nozzle_id} is unusually high. "
            f"Please verify."
        )

    # Upsert nozzle_shift_sales
    existing_stmt = select(NozzleShiftSale).where(
        NozzleShiftSale.shift_id == shift_id,
        NozzleShiftSale.nozzle_id == nozzle_id,
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()

    if existing is not None:
        existing.opening_amount = opening.amount_cumulative
        existing.closing_amount = closing.amount_cumulative
        existing.shift_sale_amount = shift_sale
        existing.opening_volume = opening.volume_cumulative
        existing.closing_volume = closing.volume_cumulative
        existing.shift_sale_volume = shift_vol
        existing.opening_tot_sales = opening.tot_sales_cumulative
        existing.closing_tot_sales = closing.tot_sales_cumulative
        existing.shift_transaction_count = shift_txn
        await db.flush()
    else:
        sale = NozzleShiftSale(
            tenant_id=opening.tenant_id,
            shift_id=shift_id,
            nozzle_id=nozzle_id,
            worker_id=opening.worker_id,
            opening_amount=opening.amount_cumulative,
            closing_amount=closing.amount_cumulative,
            shift_sale_amount=shift_sale,
            opening_volume=opening.volume_cumulative,
            closing_volume=closing.volume_cumulative,
            shift_sale_volume=shift_vol,
            opening_tot_sales=opening.tot_sales_cumulative,
            closing_tot_sales=closing.tot_sales_cumulative,
            shift_transaction_count=shift_txn,
        )
        db.add(sale)
        await db.flush()

    return warnings


async def _get_reading(
    shift_id: uuid.UUID,
    nozzle_id: uuid.UUID,
    reading_type: str,
    db: AsyncSession,
) -> NozzleMeterReading | None:
    stmt = select(NozzleMeterReading).where(
        NozzleMeterReading.shift_id == shift_id,
        NozzleMeterReading.nozzle_id == nozzle_id,
        NozzleMeterReading.reading_type == reading_type,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_open_shift(
    shift_id: uuid.UUID, current_user: User, db: AsyncSession
) -> Shift:
    """Load shift, verify tenant access, and assert it is ACTIVE."""
    shift = (
        await db.execute(select(Shift).where(Shift.id == shift_id))
    ).scalar_one_or_none()
    if shift is None:
        raise NotFoundError(resource="Shift", identifier=str(shift_id))

    pump = (
        await db.execute(select(Pump).where(Pump.id == shift.pump_id))
    ).scalar_one_or_none()
    if pump is None:
        raise NotFoundError(resource="Pump", identifier=str(shift.pump_id))

    org = (
        await db.execute(select(Organization).where(Organization.id == pump.org_id))
    ).scalar_one_or_none()
    if org is None:
        raise NotFoundError(resource="Organization", identifier=str(pump.org_id))

    verify_tenant_match(org.tenant_id, current_user)

    if shift.status != ShiftStatus.ACTIVE:
        raise ValidationError(
            message=f"Shift is '{shift.status.value}'. Meter readings can only be submitted for ACTIVE shifts."
        )

    return shift


async def _verify_shift_tenant(
    shift_id: uuid.UUID, current_user: User, db: AsyncSession
) -> None:
    """Verify shift belongs to the current user's tenant (read-only check)."""
    stmt = (
        select(Organization.tenant_id)
        .join(Pump, Pump.org_id == Organization.id)
        .join(Shift, Shift.pump_id == Pump.id)
        .where(Shift.id == shift_id)
    )
    tenant_id = (await db.execute(stmt)).scalar_one_or_none()
    if tenant_id is None:
        raise NotFoundError(resource="Shift", identifier=str(shift_id))
    verify_tenant_match(tenant_id, current_user)


def _resolve_worker_name(sale: NozzleShiftSale) -> str:
    worker = getattr(sale, "worker", None)
    if worker is None:
        return str(sale.worker_id)
    user = getattr(worker, "user", None)
    if user is None:
        return str(sale.worker_id)
    return str(getattr(user, "full_name", None) or getattr(user, "email", None) or sale.worker_id)


def _worker_display_name(worker: Worker | None) -> str:
    if worker is None:
        return "Unknown"
    user = getattr(worker, "user", None)
    if user is None:
        return str(worker.id)
    return str(getattr(user, "full_name", None) or getattr(user, "email", None) or worker.id)
