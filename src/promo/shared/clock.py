from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

LOCAL_TIMEZONE = ZoneInfo("Europe/Helsinki")


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def to_local_time(value: datetime, tz: ZoneInfo = LOCAL_TIMEZONE) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(tz)

