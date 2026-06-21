from datetime import date, time

from app import print_recommendations
from siff_picker.models import Screening
from siff_picker.recommender import (
    CONTENT_ANIMATION_SHORT_SPECIAL,
    CONTENT_AUTEUR,
    CONTENT_BIG_SCREEN,
    CONTENT_EMERGING,
    CONTENT_NONFICTION,
    CONTENT_SIFF_OFFICIAL,
    CONTENT_WORLD,
    InterestProfile,
    filter_excluded_screenings,
    recommend_screenings,
    score_film,
    screening_format_label,
)
from siff_picker.recommender import _content_matches_for_film


def make_screening(
    *,
    film_id: str = "film-1",
    title: str = "测试影片",
    show_date: date = date(2026, 6, 20),
    weekday: str = "周六",
    start: time = time(18, 30),
    end: time = time(20, 0),
    length_min: int = 90,
    price_yuan: int = 80,
    group: str = "世界万象",
    director: str = "测试导演",
    country: str = "美国",
    remarks: str = "",
    format_flags: str = "",
    hall: str = "1号厅",
    is_4k: bool = False,
) -> Screening:
    return Screening(
        film_id=film_id,
        name_cn=title,
        name_cn_base=title,
        name_en="TEST FILM",
        show_date=show_date,
        weekday=weekday,
        start_time=start,
        end_time=end,
        length_min=length_min,
        price_yuan=price_yuan,
        cinema="测试影院",
        hall=hall,
        group=group,
        director=director,
        country=country,
        remarks=remarks,
        format_flags=format_flags,
        is_4k=is_4k,
    )


def profile(
    *,
    regions=None,
    contents=None,
    exclusions=None,
    creators=None,
    works=None,
) -> InterestProfile:
    return InterestProfile(
        region_preferences=regions or ["不限"],
        content_preferences=contents or ["不限"],
        exclusions=exclusions or ["不限"],
        creators=creators or [],
        works=works or [],
    )


def test_official_director_new_work_group_matches_multiple_content_labels():
    screening = make_screening(group="官方推荐-名导新作")

    assert _content_matches_for_film([screening]) == [
        CONTENT_SIFF_OFFICIAL,
        CONTENT_AUTEUR,
        CONTENT_EMERGING,
    ]


def test_siff_classic_4k_restoration_matches_auteur_and_big_screen():
    screening = make_screening(group="SIFF经典-4K修复")

    assert _content_matches_for_film([screening]) == [
        CONTENT_AUTEUR,
        CONTENT_BIG_SCREEN,
    ]


def test_nonfiction_group_mappings():
    screenings = [
        make_screening(group="SIFF纪录", film_id="a"),
        make_screening(group="金爵奖参赛片-纪录片", film_id="b"),
        make_screening(group="宝格丽真实之境", film_id="c"),
    ]

    for screening in screenings:
        assert CONTENT_NONFICTION in _content_matches_for_film([screening])


def test_siff_in_group_name_does_not_automatically_mean_official_selection():
    screening = make_screening(group="SIFF纪录")

    assert CONTENT_SIFF_OFFICIAL not in _content_matches_for_film([screening])


def test_content_preference_scores_three_points_per_match_capped_at_two_matches():
    screening = make_screening(group="官方推荐-名导新作")
    recommendation = score_film(
        [screening],
        profile(contents=[CONTENT_SIFF_OFFICIAL, CONTENT_AUTEUR, CONTENT_EMERGING]),
    )

    assert recommendation.score == 6
    assert recommendation.reasons == [f"命中内容偏好：{CONTENT_SIFF_OFFICIAL}, {CONTENT_AUTEUR}"]


def test_content_preference_unlimited_does_not_score():
    screening = make_screening(group="官方推荐-名导新作")
    recommendation = score_film([screening], profile(contents=["不限"]))

    assert recommendation.score == 0
    assert recommendation.reasons == []


def test_exclusion_filters_long_high_price_no_subtitle_horror_thriller_and_short_films():
    screenings = [
        make_screening(film_id="long", length_min=180),
        make_screening(film_id="price", price_yuan=120),
        make_screening(film_id="subtitle", remarks="无中文字幕"),
        make_screening(film_id="horror", group="午夜惊奇-恐怖精选"),
        make_screening(film_id="thriller", title="惊悚测试片"),
        make_screening(film_id="short", group="SIFF短片"),
        make_screening(film_id="ok", title="保留影片"),
    ]
    result = filter_excluded_screenings(
        screenings,
        profile(exclusions=["超长片", "高票价", "无中文字幕", "恐怖 / 惊悚片", "短片 / 短片集"]),
    )

    assert [screening.film_id for screening in result] == ["ok"]


def test_midnight_exclusion_uses_end_time_later_than_start_time_not_late_start_only():
    screenings = [
        make_screening(film_id="late-but-not-midnight", start=time(22, 30), end=time(23, 50)),
        make_screening(film_id="cross-midnight", start=time(23, 30), end=time(1, 10)),
    ]
    result = filter_excluded_screenings(screenings, profile(exclusions=["午夜场"]))

    assert [screening.film_id for screening in result] == ["late-but-not-midnight"]


def test_film_level_aggregation_keeps_one_recommendation_with_all_screenings_sorted():
    screenings = [
        make_screening(film_id="same", start=time(20, 40), director="比利·怀尔德"),
        make_screening(film_id="same", start=time(18, 30), director="比利·怀尔德"),
    ]
    recommendations = recommend_screenings(screenings, profile(creators=["比利怀尔德"]))

    assert len(recommendations) == 1
    assert len(recommendations[0].screenings) == 2
    assert [screening.start_time for screening in recommendations[0].screenings] == [time(18, 30), time(20, 40)]


def test_positive_recommendation_reasons_only_include_scoring_factors():
    recommendation = score_film(
        [make_screening(group="官方推荐-名导新作", director="比利·怀尔德", country="美国")],
        profile(
            regions=["美国"],
            contents=[CONTENT_AUTEUR],
            creators=["比利怀尔德"],
            works=["测试影片"],
        ),
    )

    assert recommendation.score > 0
    assert recommendation.reasons
    assert all("可观看场次" not in reason for reason in recommendation.reasons)
    assert all("已过滤" not in reason for reason in recommendation.reasons)
    assert len(recommendation.reasons) <= 3


def test_positive_recommendation_output_uses_recommendation_reasons(capsys):
    recommendations = recommend_screenings(
        [make_screening(group="官方推荐-名导新作")],
        profile(contents=[CONTENT_AUTEUR]),
    )

    print_recommendations(recommendations, recommendations[0].screenings, recommendations[0].screenings)
    output = capsys.readouterr().out

    assert "推荐分数:" in output
    assert "推荐理由:" in output
    assert "命中内容偏好" in output
    assert "存在 1 个可观看场次" not in output


def test_fallback_enabled_when_positive_recommendations_are_fewer_than_five():
    screenings = [
        make_screening(film_id=f"fallback-{index}", title=f"候选{index}", group="官方推荐-展映")
        for index in range(6)
    ]
    recommendations = recommend_screenings(screenings, profile())

    assert recommendations
    assert all(recommendation.is_fallback for recommendation in recommendations)
    assert all(recommendation.score == 0 for recommendation in recommendations)
    assert all(recommendation.candidate_basis for recommendation in recommendations)


def test_fallback_output_shows_candidate_basis_not_zero_score(capsys):
    recommendations = recommend_screenings(
        [make_screening(group="官方推荐-展映")],
        profile(),
    )

    print_recommendations(recommendations, recommendations[0].screenings, recommendations[0].screenings)
    output = capsys.readouterr().out

    assert "候选依据:" in output
    assert "推荐分数: 0" not in output
    assert "推荐理由:" not in output


def test_fallback_sorting_uses_content_priority_then_earliest_screening_time():
    screenings = [
        make_screening(film_id="world-early", title="世界早场", group="世界万象", start=time(10, 0)),
        make_screening(film_id="official-late", title="官方晚场", group="官方推荐-展映", start=time(20, 0)),
        make_screening(film_id="official-early", title="官方早场", group="官方推荐-展映", start=time(18, 0)),
    ]
    recommendations = recommend_screenings(screenings, profile())

    assert [recommendation.title for recommendation in recommendations[:3]] == ["官方早场", "官方晚场", "世界早场"]


def test_screening_format_label_uses_format_flags_is4k_and_hall_name():
    assert screening_format_label(make_screening(format_flags="IMAX,4K")) == "IMAX / 4K"
    assert screening_format_label(make_screening(is_4k=True)) == "4K"
    assert screening_format_label(make_screening(hall="杜比 CINITY ONYX LUXE XR厅")) == "CINITY / 杜比 / XR / ONYX / LUXE"


def test_screening_format_label_is_display_only_and_does_not_score():
    recommendation = score_film(
        [make_screening(format_flags="IMAX,4K", hall="杜比厅", is_4k=True)],
        profile(),
    )

    assert recommendation.score == 0
    assert recommendation.reasons == []
