from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import app
from siff_picker.filters import filter_future_screenings
from tests.test_recommender_rules import make_screening


def test_default_current_beijing_time_uses_realtime_now(monkeypatch):
    captured = {}
    fixed_now = datetime(2026, 6, 21, 15, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            captured["tz"] = tz
            return fixed_now

    monkeypatch.setattr(app, "datetime", FakeDateTime)

    assert app.get_current_beijing_time() == fixed_now
    assert captured["tz"].key == "Asia/Shanghai"


def test_now_override_controls_future_screening_filter():
    now_override = app.get_current_beijing_time(datetime(2026, 6, 15, 12, 0))
    screenings = [
        make_screening(film_id="started", show_date=date(2026, 6, 15), start=time(11, 59)),
        make_screening(film_id="equal", show_date=date(2026, 6, 15), start=time(12, 0)),
        make_screening(film_id="future", show_date=date(2026, 6, 15), start=time(12, 1)),
    ]

    result = filter_future_screenings(screenings, now_override)

    assert now_override.tzinfo.key == "Asia/Shanghai"
    assert [screening.film_id for screening in result] == ["future"]


def test_aware_now_override_is_converted_to_beijing_time():
    utc_now = datetime(2026, 6, 15, 4, 0, tzinfo=ZoneInfo("UTC"))

    result = app.get_current_beijing_time(utc_now)

    assert result == datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
