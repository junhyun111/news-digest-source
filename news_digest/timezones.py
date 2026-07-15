from __future__ import annotations

from datetime import timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def get_timezone(name: str) -> tzinfo:
    if name.casefold() in {"utc", "etc/utc", "z"}:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name == "Asia/Seoul":
            return timezone(timedelta(hours=9), "Asia/Seoul")
        raise
