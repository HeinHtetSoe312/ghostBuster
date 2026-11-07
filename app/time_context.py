from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def resolve_when(
    tz_name: str, hour: Optional[int] = None, day_of_week: Optional[int] = None
) -> Tuple[datetime, bool]:
    """Return (datetime, simulated). Overrides shift the live clock to a chosen weekday/hour."""
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    when = datetime.now(tz)
    simulated = hour is not None or day_of_week is not None
    if day_of_week is not None:
        when = when + timedelta(days=day_of_week - when.weekday())
    if hour is not None:
        when = when.replace(hour=hour, minute=0, second=0, microsecond=0)
    return when, simulated
