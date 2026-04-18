"""PetroLedger — Date/Time Utilities.

All helpers normalise to IST (Asia/Kolkata) so that shift boundaries,
report dates, and reconciliation windows are consistent regardless of
the server's system timezone.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def get_ist_now() -> datetime:
    """Return the current moment in IST."""
    return datetime.now(IST)


def to_ist(dt: datetime) -> datetime:
    """Convert an arbitrary timezone-aware (or naïve-UTC) datetime to IST.

    If *dt* is naïve it is assumed to be UTC before conversion.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(IST)


def shift_date(dt: datetime) -> date:
    """Extract the calendar date in IST for a given datetime.

    Useful for grouping transactions by *shift day*.
    """
    return to_ist(dt).date()


def is_same_shift_day(dt1: datetime, dt2: datetime) -> bool:
    """Return ``True`` if both datetimes fall on the same IST calendar day."""
    return shift_date(dt1) == shift_date(dt2)


def format_ist(dt: datetime, fmt: str = "%d/%m/%Y %H:%M") -> str:
    """Format a datetime as a human-readable IST string."""
    return to_ist(dt).strftime(fmt)
