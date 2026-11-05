"""The current time as a family lives it (TKT-65).

Transactions are stored as the wall-clock time of the family, without a timezone, and every cut by day or month reads
those digits as they are. So "now" must never come from the server's own clock (which may be in another timezone than
the people using the app): it is read in the family's timezone.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    """The one place that reads the real clock, so tests can set it."""
    return datetime.now(timezone.utc)


def family_now(timezone_name: str) -> datetime:
    """What the clock on the family's wall says right now (no timezone attached), to the second."""
    return utc_now().astimezone(ZoneInfo(timezone_name)).replace(tzinfo=None, microsecond=0)


def family_today(timezone_name: str) -> date:
    return family_now(timezone_name).date()
