"""Time helpers for local business dates stored as UTC-naive timestamps."""

import os
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo


BUSINESS_TIMEZONE = ZoneInfo(os.getenv("BUSINESS_TIMEZONE", "Europe/Volgograd"))


def utc_now() -> datetime:
    return datetime.utcnow()


def local_now() -> datetime:
    return datetime.now(BUSINESS_TIMEZONE)


def business_today() -> date:
    return local_now().date()


def _local_boundary_to_utc_naive(day: date) -> datetime:
    local_boundary = datetime.combine(day, time.min, tzinfo=BUSINESS_TIMEZONE)
    return local_boundary.astimezone(timezone.utc).replace(tzinfo=None)


def business_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    start = _local_boundary_to_utc_naive(day)
    end = _local_boundary_to_utc_naive(date.fromordinal(day.toordinal() + 1))
    return start, end


def business_month_bounds_utc(month: date) -> tuple[datetime, datetime]:
    start_month = date(month.year, month.month, 1)
    if start_month.month == 12:
        next_month = date(start_month.year + 1, 1, 1)
    else:
        next_month = date(start_month.year, start_month.month + 1, 1)
    return _local_boundary_to_utc_naive(start_month), _local_boundary_to_utc_naive(next_month)


def business_date_from_utc(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BUSINESS_TIMEZONE).date()
