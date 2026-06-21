from datetime import date, time

from app import CONTENT_OPTIONS, EXCLUSION_OPTIONS, REGION_OPTIONS, TIME_SLOT_OPTIONS, filter_by_time_slots, parse_multi_choice
from siff_picker.filters import TimeSlot
from siff_picker.recommender import (
    CONTENT_AUTEUR,
    InterestProfile,
    filter_excluded_screenings,
    score_film,
)

from tests.test_recommender_rules import make_screening


def test_region_unlimited_is_ignored_when_specific_regions_are_selected():
    selected = parse_multi_choice("1,2,6", REGION_OPTIONS)

    assert selected == ["华语", "美国"]

    recommendation = score_film(
        [make_screening(country="中国,美国")],
        InterestProfile(selected, ["不限"], ["不限"], [], []),
    )
    assert recommendation.score == 2
    assert recommendation.reasons == ["命中国家 / 地区偏好：华语, 美国"]


def test_content_unlimited_is_ignored_when_specific_content_is_selected():
    selected = parse_multi_choice("2,8", CONTENT_OPTIONS)

    assert selected == [CONTENT_AUTEUR]

    recommendation = score_film(
        [make_screening(group="SIFF经典-4K修复")],
        InterestProfile(["不限"], selected, ["不限"], [], []),
    )
    assert recommendation.score == 3
    assert recommendation.reasons == [f"命中内容偏好：{CONTENT_AUTEUR}"]


def test_exclusion_unlimited_is_ignored_when_specific_exclusions_are_selected():
    selected = parse_multi_choice("1,7", EXCLUSION_OPTIONS)

    assert selected == ["恐怖 / 惊悚片"]

    screenings = [
        make_screening(film_id="horror", group="午夜惊奇-恐怖精选"),
        make_screening(film_id="safe", title="安全影片"),
    ]
    result = filter_excluded_screenings(
        screenings,
        InterestProfile(["不限"], ["不限"], selected, [], []),
    )
    assert [screening.film_id for screening in result] == ["safe"]


def test_all_day_is_ignored_when_specific_time_slot_is_selected():
    selected = parse_multi_choice("2,5", TIME_SLOT_OPTIONS)

    assert selected == [TimeSlot.WEEKDAY_EVENING]

    screenings = [
        make_screening(film_id="evening", show_date=date(2026, 6, 19), weekday="周五", start=time(18, 30)),
        make_screening(film_id="day", show_date=date(2026, 6, 19), weekday="周五", start=time(13, 0)),
    ]
    result = filter_by_time_slots(screenings, selected)
    assert [screening.film_id for screening in result] == ["evening"]


def test_only_unlimited_keeps_dimension_unrestricted():
    assert parse_multi_choice("6", REGION_OPTIONS) == ["不限"]
    assert parse_multi_choice("8", CONTENT_OPTIONS) == ["不限"]
    assert parse_multi_choice("7", EXCLUSION_OPTIONS) == ["不限"]
    assert parse_multi_choice("5", TIME_SLOT_OPTIONS) == ["全天不限"]

    region_score = score_film(
        [make_screening(country="美国")],
        InterestProfile(["不限"], ["不限"], ["不限"], [], []),
    )
    content_score = score_film(
        [make_screening(group="SIFF经典-4K修复")],
        InterestProfile(["不限"], ["不限"], ["不限"], [], []),
    )
    exclusion_result = filter_excluded_screenings(
        [make_screening(film_id="horror", group="午夜惊奇-恐怖精选")],
        InterestProfile(["不限"], ["不限"], ["不限"], [], []),
    )

    assert region_score.score == 0
    assert content_score.score == 0
    assert [screening.film_id for screening in exclusion_result] == ["horror"]
