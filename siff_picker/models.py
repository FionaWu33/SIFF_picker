from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True)
class Screening:
    film_id: str
    name_cn: str
    name_cn_base: str
    name_en: str
    show_date: date
    weekday: str
    start_time: time
    end_time: time
    length_min: int | None
    price_yuan: int | None
    cinema: str
    hall: str
    group: str
    director: str
    country: str
    remarks: str
    format_flags: str
    is_4k: bool

    @property
    def display_name(self) -> str:
        return self.name_cn_base or self.name_cn or self.name_en or "未知影片"
