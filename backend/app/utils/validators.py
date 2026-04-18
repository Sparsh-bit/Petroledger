"""PetroLedger — Domain Validators.

Lightweight guard functions that raise domain exceptions when
preconditions are violated.  These are called in service/route layers
*before* mutations to ensure data integrity.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from uuid import UUID

from app.core.exceptions import AuthorizationError, ValidationError
from app.models.pump import Pump
from app.models.shift import Shift
from app.models.worker import Worker

# ── Organisation / ownership guards ────────────────────────────────────


def validate_shift_belongs_to_org(shift: Shift, org_id: UUID) -> None:
    """Raise :class:`AuthorizationError` if *shift* does not belong to *org_id*.

    ``Shift`` has no direct ``org_id`` column — ownership is determined
    via ``shift.pump.org_id``.  The ``pump`` relationship must be loaded
    before calling this function (the default ``lazy="selectin"`` policy
    takes care of this in normal query paths).
    """
    if shift.pump.org_id != org_id:
        raise AuthorizationError(
            "Shift does not belong to the specified organization.",
            detail={"shift_id": str(shift.id), "expected_org_id": str(org_id)},
        )


def validate_pump_belongs_to_org(pump: Pump, org_id: UUID) -> None:
    """Raise :class:`AuthorizationError` if *pump* does not belong to *org_id*."""
    if pump.org_id != org_id:
        raise AuthorizationError(
            "Pump does not belong to the specified organization.",
            detail={"pump_id": str(pump.id), "expected_org_id": str(org_id)},
        )


def validate_worker_belongs_to_pump(worker: Worker, pump_id: UUID) -> None:
    """Raise :class:`AuthorizationError` if *worker* is not assigned to *pump_id*."""
    if worker.pump_id != pump_id:
        raise AuthorizationError(
            "Worker does not belong to the specified pump.",
            detail={"worker_id": str(worker.id), "expected_pump_id": str(pump_id)},
        )


# ── Value validators ───────────────────────────────────────────────────


def validate_positive_amount(amount: Decimal, field_name: str) -> None:
    """Raise :class:`ValidationError` if *amount* is not strictly positive."""
    if amount <= 0:
        raise ValidationError(
            f"{field_name} must be a positive amount.",
            detail={"field": field_name, "value": str(amount)},
        )


def validate_uuid_string(value: str, field_name: str) -> uuid.UUID:
    """Parse *value* as a UUID and return it, or raise :class:`ValidationError`."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError) as err:
        raise ValidationError(
            f"{field_name} is not a valid UUID.",
            detail={"field": field_name, "value": value},
        ) from err