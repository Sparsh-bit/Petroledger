"""
PetroLedger — Shift Date Helpers.

Shift 3 at Indian petrol stations spans midnight (22:00–06:00 IST).
Any query for "all shifts on date D" must include:

  • Shifts where start_time falls within D 00:00–23:59 IST  (S1, S2)
  • Shifts where start_time falls within D-1 22:00 to D 06:00 IST  (S3)

``get_shifts_for_date()`` encapsulates this logic in a reusable
SQLAlchemy WHERE clause so all callers stay consistent.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_

from app.models.shift import Shift

IST = ZoneInfo("Asia/Kolkata")


def get_date_window_utc(shift_date: date) -> tuple[datetime, datetime, datetime, datetime]:
    """Return the four UTC boundary datetimes needed to query a full shift day.

    Returns
    -------
    (day_start_utc, day_end_utc, s3_start_utc, s3_end_utc)
        day_start  — midnight IST at the start of *shift_date*
        day_end    — midnight IST at the start of *shift_date + 1*
        s3_start   — 22:00 IST on *shift_date - 1*  (Shift 3 start window)
        s3_end     — 06:00 IST on *shift_date*        (Shift 3 end boundary)
    """
    prev_date = shift_date - timedelta(days=1)

    day_start_utc = datetime(
        shift_date.year, shift_date.month, shift_date.day, tzinfo=IST
    ).astimezone(UTC)
    day_end_utc = (
        datetime(shift_date.year, shift_date.month, shift_date.day, tzinfo=IST)
        + timedelta(days=1)
    ).astimezone(UTC)

    s3_start_utc = datetime(
        prev_date.year, prev_date.month, prev_date.day, 22, 0, tzinfo=IST
    ).astimezone(UTC)
    s3_end_utc = datetime(
        shift_date.year, shift_date.month, shift_date.day, 6, 0, tzinfo=IST
    ).astimezone(UTC)

    return day_start_utc, day_end_utc, s3_start_utc, s3_end_utc


def shifts_for_date_filter(shift_date: date):
    """Return a SQLAlchemy WHERE clause that matches all shifts for *shift_date*.

    Handles Shift 3 midnight-spanning correctly.

    Usage::

        stmt = select(Shift).where(shifts_for_date_filter(today))
    """
    day_start_utc, day_end_utc, s3_start_utc, s3_end_utc = get_date_window_utc(shift_date)

    return or_(
        # Regular shifts (S1, S2): started during the calendar day
        (Shift.start_time >= day_start_utc) & (Shift.start_time < day_end_utc),
        # Shift 3: started last night, runs into today morning
        (Shift.start_time >= s3_start_utc) & (Shift.start_time < s3_end_utc),
    )


async def get_shifts_for_date(
    shift_date: date,
    db,
    pump_id=None,
    org_id=None,
):
    """Query all Shift rows for *shift_date*, optionally scoped to a pump or org.

    Parameters
    ----------
    shift_date:
        The calendar date (in IST) to query shifts for.
    db:
        Async SQLAlchemy session.
    pump_id:
        Optional UUID to filter by a single pump.
    org_id:
        Optional UUID to filter by organisation (all pumps in the site).

    Returns
    -------
    list[Shift]
        All shifts whose start_time falls within the day window,
        including Shift 3 midnight-spanning shifts.
    """
    from sqlalchemy import select

    from app.models.pump import Pump

    stmt = select(Shift).where(shifts_for_date_filter(shift_date))

    if pump_id is not None:
        stmt = stmt.where(Shift.pump_id == pump_id)
    elif org_id is not None:
        pump_subq = select(Pump.id).where(Pump.org_id == org_id)
        stmt = stmt.where(Shift.pump_id.in_(pump_subq))

    result = await db.execute(stmt)
    return list(result.scalars().all())
