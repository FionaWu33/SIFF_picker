from __future__ import annotations

import csv
from datetime import date, time
from pathlib import Path

from .models import Screening


def load_screenings(csv_path: str | Path) -> list[Screening]:
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8-sig") as file:
        return [_row_to_screening(row) for row in csv.DictReader(file)]


def _row_to_screening(row: dict[str, str]) -> Screening:
    return Screening(
        film_id=row["officialFilmId"].strip(),
        name_cn=row["nameCn"].strip(),
        name_cn_base=row["nameCnBase"].strip(),
        name_en=row["nameEn"].strip(),
        show_date=date.fromisoformat(row["date"]),
        weekday=row["weekday"].strip(),
        start_time=_parse_time(row["stime"]),
        end_time=_parse_time(row["etime"]),
        length_min=_parse_int(row["lengthMin"]),
        price_yuan=_parse_int(row["priceYuan"]),
        cinema=row["cinema"].strip(),
        hall=row["hallsName"].strip(),
        group=row["group"].strip(),
        director=row["director"].strip(),
        country=row["country"].strip(),
        remarks=row["remarks"].strip(),
        format_flags=row["formatFlags"].strip(),
        is_4k=_parse_bool(row["is4k"]),
    )


def _parse_time(value: str) -> time:
    hour, minute = value.split(":", maxsplit=1)
    return time(hour=int(hour), minute=int(minute))


def _parse_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


def _parse_bool(value: str) -> bool:
    return value.strip() in {"1", "true", "True", "TRUE", "yes", "Y"}
