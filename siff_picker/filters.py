from collections.abc import Iterable
from datetime import datetime, time
from enum import Enum
from zoneinfo import ZoneInfo

from .models import Screening


class TimeSlot(str, Enum):
    WEEKDAY_DAY = "工作日白天"
    WEEKDAY_EVENING = "工作日晚间"
    WEEKEND_DAY = "周末白天"
    WEEKEND_EVENING = "周末晚间"


EVENING_START = time(hour=18, minute=0)
WEEKEND_DAYS = {"周六", "周日"}
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def filter_future_screenings(screenings: Iterable[Screening], now: datetime) -> list[Screening]:
    now_in_shanghai = _as_shanghai_time(now)
    return [
        screening
        for screening in screenings
        if _screening_start_datetime(screening) > now_in_shanghai
    ]


def filter_by_time_slot(screenings: Iterable[Screening], slot: TimeSlot) -> list[Screening]:
    return [screening for screening in screenings if matches_time_slot(screening, slot)]


def matches_time_slot(screening: Screening, slot: TimeSlot) -> bool:
    is_weekend = screening.weekday in WEEKEND_DAYS
    is_evening = screening.start_time >= EVENING_START

    if slot == TimeSlot.WEEKDAY_DAY:
        return not is_weekend and not is_evening
    if slot == TimeSlot.WEEKDAY_EVENING:
        return not is_weekend and is_evening
    if slot == TimeSlot.WEEKEND_DAY:
        return is_weekend and not is_evening
    if slot == TimeSlot.WEEKEND_EVENING:
        return is_weekend and is_evening

    raise ValueError(f"Unknown time slot: {slot}")


def _screening_start_datetime(screening: Screening) -> datetime:
    return datetime.combine(screening.show_date, screening.start_time, tzinfo=SHANGHAI_TZ)


def _as_shanghai_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=SHANGHAI_TZ)
    return value.astimezone(SHANGHAI_TZ)


def count_unique_films(screenings: Iterable[Screening]) -> int:
    return len({screening.film_id or screening.display_name for screening in screenings})


def unique_film_names(screenings: Iterable[Screening]) -> list[str]:
    names_by_key: dict[str, str] = {}
    for screening in screenings:
        key = screening.film_id or screening.display_name
        names_by_key.setdefault(key, screening.display_name)
    return sorted(names_by_key.values())
