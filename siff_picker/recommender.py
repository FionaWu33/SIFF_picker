from __future__ import annotations

from dataclasses import dataclass

from .models import Screening


CONTENT_SIFF_OFFICIAL = "SIFF官方精选 / 竞赛片"
CONTENT_AUTEUR = "名导作品"
CONTENT_EMERGING = "新锐作品"
CONTENT_BIG_SCREEN = "大银幕视听"
CONTENT_NONFICTION = "非虚构"
CONTENT_ANIMATION_SHORT_SPECIAL = "动画 / 短片 / 特别放映"
CONTENT_WORLD = "世界电影 / 多元探索"

FALLBACK_CONTENT_ORDER = [
    CONTENT_SIFF_OFFICIAL,
    CONTENT_AUTEUR,
    CONTENT_EMERGING,
    CONTENT_WORLD,
    CONTENT_NONFICTION,
    CONTENT_BIG_SCREEN,
    CONTENT_ANIMATION_SHORT_SPECIAL,
]

CHINESE_REGIONS = {"中国", "中国大陆", "中国内地", "中国香港", "中国台湾", "新加坡", "马来西亚"}
EUROPE_REGIONS = {
    "阿尔巴尼亚",
    "奥地利",
    "白俄罗斯",
    "比利时",
    "波黑",
    "保加利亚",
    "克罗地亚",
    "塞浦路斯",
    "捷克",
    "丹麦",
    "爱沙尼亚",
    "芬兰",
    "德国",
    "希腊",
    "匈牙利",
    "冰岛",
    "爱尔兰",
    "意大利",
    "拉脱维亚",
    "立陶宛",
    "卢森堡",
    "马耳他",
    "摩尔多瓦",
    "黑山",
    "荷兰",
    "北马其顿",
    "挪威",
    "波兰",
    "葡萄牙",
    "罗马尼亚",
    "俄罗斯",
    "塞尔维亚",
    "斯洛伐克",
    "斯洛文尼亚",
    "西班牙",
    "瑞典",
    "瑞士",
    "乌克兰",
}
DISPLAY_FORMAT_KEYWORDS = ["IMAX", "4K", "CINITY", "杜比", "XR", "ONYX", "LUXE"]
NORMALIZE_REMOVE_CHARS = str.maketrans("", "", "· .-/")


@dataclass(frozen=True)
class InterestProfile:
    region_preferences: list[str]
    content_preferences: list[str]
    exclusions: list[str]
    creators: list[str]
    works: list[str]


@dataclass(frozen=True)
class FilmRecommendation:
    title: str
    director: str
    country_or_region: str
    duration: int | None
    score: int
    reasons: list[str]
    candidate_basis: list[str]
    screenings: list[Screening]
    content_matches: list[str]
    has_creator_or_work_match: bool
    is_fallback: bool


def filter_excluded_screenings(screenings: list[Screening], profile: InterestProfile) -> list[Screening]:
    if "不限" in profile.exclusions:
        return screenings
    return [screening for screening in screenings if not _is_excluded(screening, profile.exclusions)]


def recommend_screenings(
    screenings: list[Screening],
    profile: InterestProfile,
    limit: int = 20,
) -> list[FilmRecommendation]:
    recommendations = [
        score_film(film_screenings, profile)
        for film_screenings in _group_screenings_by_film(screenings).values()
    ]
    positive_recommendations = [item for item in recommendations if item.score > 0]

    if len(positive_recommendations) >= 5:
        return _sort_positive_recommendations(positive_recommendations)[:limit]

    positive_keys = {_recommendation_key(item) for item in positive_recommendations}
    fallback_recommendations = [
        _as_fallback_recommendation(item)
        for item in recommendations
        if _recommendation_key(item) not in positive_keys and item.content_matches
    ]
    return (
        _sort_positive_recommendations(positive_recommendations)
        + _sort_fallback_recommendations(fallback_recommendations)
    )[:limit]


def score_film(screenings: list[Screening], profile: InterestProfile) -> FilmRecommendation:
    representative = screenings[0]
    score = 0
    reasons: list[str] = []
    has_creator_or_work_match = False

    creator_score, creator_reasons = _score_creators(screenings, profile.creators)
    if creator_score:
        score += creator_score
        reasons.extend(creator_reasons)
        has_creator_or_work_match = True

    work_score, work_reasons = _score_works(screenings, profile.works)
    if work_score:
        score += work_score
        reasons.extend(work_reasons)
        has_creator_or_work_match = True

    content_matches = _content_matches_for_film(screenings)
    selected_content_matches = _selected_content_matches(content_matches, profile.content_preferences)
    if selected_content_matches:
        scored_content_matches = selected_content_matches[:2]
        score += 3 * len(scored_content_matches)
        reasons.append(f"命中内容偏好：{', '.join(scored_content_matches)}")

    region_hits = _matched_region_preferences(screenings, profile.region_preferences)
    if region_hits:
        score += 2
        reasons.append(f"命中国家 / 地区偏好：{', '.join(region_hits)}")

    return FilmRecommendation(
        title=representative.display_name,
        director=representative.director,
        country_or_region=representative.country,
        duration=representative.length_min,
        score=score,
        reasons=_limit_reasons(reasons),
        candidate_basis=_candidate_basis(content_matches, screenings),
        screenings=screenings,
        content_matches=content_matches,
        has_creator_or_work_match=has_creator_or_work_match,
        is_fallback=False,
    )


def screening_format_label(screening: Screening) -> str:
    text = " ".join([screening.format_flags, screening.hall]).upper()
    labels: list[str] = []

    for keyword in DISPLAY_FORMAT_KEYWORDS:
        normalized_keyword = keyword.upper()
        if normalized_keyword in text or (keyword == "4K" and screening.is_4k):
            labels.append(keyword)

    return " / ".join(_unique_values(labels))


def _sort_positive_recommendations(recommendations: list[FilmRecommendation]) -> list[FilmRecommendation]:
    return sorted(
        recommendations,
        key=lambda item: (
            -item.score,
            not item.has_creator_or_work_match,
            -len(item.content_matches),
            item.screenings[0].show_date,
            item.screenings[0].start_time,
            -len(item.screenings),
            item.title,
        ),
    )


def _sort_fallback_recommendations(recommendations: list[FilmRecommendation]) -> list[FilmRecommendation]:
    return sorted(
        recommendations,
        key=lambda item: (
            _fallback_rank(item),
            item.screenings[0].show_date,
            item.screenings[0].start_time,
            item.title,
        ),
    )


def _as_fallback_recommendation(recommendation: FilmRecommendation) -> FilmRecommendation:
    return FilmRecommendation(
        title=recommendation.title,
        director=recommendation.director,
        country_or_region=recommendation.country_or_region,
        duration=recommendation.duration,
        score=0,
        reasons=[],
        candidate_basis=_candidate_basis(recommendation.content_matches, recommendation.screenings),
        screenings=recommendation.screenings,
        content_matches=recommendation.content_matches,
        has_creator_or_work_match=False,
        is_fallback=True,
    )


def _fallback_rank(recommendation: FilmRecommendation) -> int:
    ranks = [
        FALLBACK_CONTENT_ORDER.index(content)
        for content in recommendation.content_matches
        if content in FALLBACK_CONTENT_ORDER
    ]
    return min(ranks) if ranks else len(FALLBACK_CONTENT_ORDER)


def _recommendation_key(recommendation: FilmRecommendation) -> tuple[str, str]:
    first_screening = recommendation.screenings[0]
    return (first_screening.film_id or recommendation.title, recommendation.director)


def _candidate_basis(content_matches: list[str], screenings: list[Screening]) -> list[str]:
    basis: list[str] = []
    fallback_content = next((content for content in FALLBACK_CONTENT_ORDER if content in content_matches), None)
    if fallback_content:
        basis.append(f"属于 {fallback_content}")
    first_screening = screenings[0]
    basis.append(
        "最早可观看场次："
        f"{first_screening.show_date.month}月{first_screening.show_date.day}日 "
        f"{first_screening.start_time.strftime('%H:%M')}"
    )
    return basis


def _limit_reasons(reasons: list[str]) -> list[str]:
    return _unique_values(reasons)[:3]


def _score_creators(screenings: list[Screening], creators: list[str]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    director_text = " ".join(_unique_values(screening.director for screening in screenings))
    other_text = _other_text(screenings)
    normalized_director_parts = _normalized_people_parts(director_text)
    normalized_director_text = normalize_text(director_text)
    normalized_other_text = normalize_text(other_text)

    for creator in creators:
        normalized_creator = normalize_text(creator)
        if not normalized_creator:
            continue

        if normalized_creator in normalized_director_parts:
            score += 6
            reasons.append(f"命中创作者偏好：{creator}")
        elif normalized_creator in normalized_director_text:
            score += 5
            reasons.append(f"命中创作者偏好：{creator}")
        elif normalized_creator in normalized_other_text:
            score += 4
            reasons.append(f"命中创作者偏好：{creator}")

    return score, _unique_values(reasons)


def _score_works(screenings: list[Screening], works: list[str]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    title_text = " ".join(
        _unique_values(
            title
            for screening in screenings
            for title in [screening.name_cn, screening.name_cn_base, screening.name_en]
        )
    )
    other_text = _other_text(screenings)
    normalized_title_parts = _normalized_title_parts(screenings)
    normalized_title_text = normalize_text(title_text)
    normalized_other_text = normalize_text(other_text)

    for work in works:
        normalized_work = normalize_text(work)
        if not normalized_work:
            continue

        if normalized_work in normalized_title_parts:
            score += 6
            reasons.append(f"命中作品偏好：{work}")
        elif normalized_work in normalized_title_text:
            score += 5
            reasons.append(f"命中作品偏好：{work}")
        elif normalized_work in normalized_other_text:
            score += 4
            reasons.append(f"命中作品偏好：{work}")

    return score, _unique_values(reasons)


def normalize_text(value: str) -> str:
    return value.casefold().translate(NORMALIZE_REMOVE_CHARS)


def _group_screenings_by_film(screenings: list[Screening]) -> dict[tuple[str, str, str], list[Screening]]:
    groups: dict[tuple[str, str, str], list[Screening]] = {}
    for screening in screenings:
        groups.setdefault(_film_key(screening), []).append(screening)

    for film_screenings in groups.values():
        film_screenings.sort(key=lambda item: (item.show_date, item.start_time, item.cinema, item.hall))

    return groups


def _film_key(screening: Screening) -> tuple[str, str, str]:
    if screening.film_id:
        return ("film_id", screening.film_id, "")
    if screening.name_cn_base:
        return ("title", screening.name_cn_base, "")
    if screening.display_name:
        return ("title", screening.display_name, "")
    return ("title_director", screening.display_name, screening.director)


def _is_excluded(screening: Screening, exclusions: list[str]) -> bool:
    return any(
        [
            "恐怖 / 惊悚片" in exclusions and _is_horror_or_thriller(screening),
            "超长片" in exclusions and screening.length_min is not None and screening.length_min >= 180,
            "午夜场" in exclusions and _is_midnight_screening(screening),
            "高票价" in exclusions and screening.price_yuan is not None and screening.price_yuan >= 120,
            "无中文字幕" in exclusions and "无中文字幕" in screening.remarks,
            "短片 / 短片集" in exclusions and _is_short_film(screening),
        ]
    )


def _is_horror_or_thriller(screening: Screening) -> bool:
    text = _screening_text(screening)
    return "恐怖" in text or "惊悚" in text


def _is_short_film(screening: Screening) -> bool:
    return any("短片" in value for value in [screening.group, screening.name_cn, screening.name_cn_base])


def _is_midnight_screening(screening: Screening) -> bool:
    return screening.end_time <= screening.start_time


def _matched_region_preferences(screenings: list[Screening], preferences: list[str]) -> list[str]:
    if "不限" in preferences:
        return []

    countries = {
        country.strip()
        for screening in screenings
        for country in screening.country.split(",")
        if country.strip()
    }
    hits: list[str] = []

    for preference in preferences:
        if preference == "华语" and countries & CHINESE_REGIONS:
            hits.append("华语")
        elif preference in {"美国", "法国", "英国"} and preference in countries:
            hits.append(preference)
        elif preference == "其他欧洲" and (countries & EUROPE_REGIONS):
            hits.append("其他欧洲")

    return _unique_values(hits)


def _selected_content_matches(content_matches: list[str], preferences: list[str]) -> list[str]:
    if "不限" in preferences:
        return []
    return [content for content in content_matches if content in preferences]


def _content_matches_for_film(screenings: list[Screening]) -> list[str]:
    matches: list[str] = []
    for screening in screenings:
        matches.extend(_content_matches_for_screening(screening))
    return _unique_values(matches)


def _content_matches_for_screening(screening: Screening) -> list[str]:
    group = screening.group
    text = " ".join([screening.group, screening.format_flags, screening.hall])
    matches: list[str] = []

    if (
        group.startswith("金爵奖参赛片-")
        or group.startswith("官方推荐-")
        or "开闭幕片" in group
        or "特别放映" in group
    ):
        matches.append(CONTENT_SIFF_OFFICIAL)

    if (
        group.startswith("向大师致敬")
        or group.startswith("SIFF经典")
        or "官方推荐-名导新作" in group
        or "官方推荐-评委主席及作品展" in group
        or "官方推荐-评委主席及评委作品展" in group
    ):
        matches.append(CONTENT_AUTEUR)

    if (
        "官方推荐-世界首作" in group
        or "官方推荐-名导新作" in group
        or "金爵奖参赛片-亚洲新人奖" in group
        or "华语新风" in group
        or "今日亚洲-年度亚洲电影" in group
        or "香港电影新动力" in group
    ):
        matches.append(CONTENT_EMERGING)

    if (
        "新视野-IMAX" in group
        or "新视野-杜比视界" in group
        or group.startswith("科幻电影周")
        or "午夜惊奇" in group
        or "4K修复" in group
        or "魔法" in group
        or "置身扩影" in group
        or any(keyword in text.upper() for keyword in ["IMAX", "CINITY", "XR"])
        or "杜比" in text
    ):
        matches.append(CONTENT_BIG_SCREEN)

    if "SIFF纪录" in group or "金爵奖参赛片-纪录片" in group or "宝格丽真实之境" in group:
        matches.append(CONTENT_NONFICTION)

    if (
        "SIFF动画" in group
        or "SIFF短片" in group
        or "金爵奖参赛片-动画片" in group
        or "金爵奖参赛片-短片" in group
        or "动画片" in group
        or "短片片" in group
        or "特别放映" in group
        or "置身扩影" in group
        or "XR" in text.upper()
        or "科幻电影周-阿内·拉鲁科幻动画三部曲" in group
    ):
        matches.append(CONTENT_ANIMATION_SHORT_SPECIAL)

    if (
        "一带一路" in group
        or "世界万象" in group
        or "多元视角" in group
        or "今日亚洲" in group
        or "大好河山·中华电影图卷" in group
        or "宝格丽真实之境" in group
    ):
        matches.append(CONTENT_WORLD)

    return _unique_values(matches)


def _screening_text(screening: Screening) -> str:
    return " ".join(
        [
            screening.name_cn,
            screening.name_cn_base,
            screening.name_en,
            screening.director,
            screening.country,
            screening.group,
            screening.remarks,
        ]
    )


def _other_text(screenings: list[Screening]) -> str:
    return " ".join(
        _unique_values(
            text
            for screening in screenings
            for text in [
                screening.name_cn,
                screening.name_cn_base,
                screening.name_en,
                screening.country,
                screening.group,
                screening.remarks,
                screening.format_flags,
            ]
        )
    )


def _normalized_people_parts(text: str) -> set[str]:
    return {
        normalize_text(part)
        for part in _split_parts(text)
        if normalize_text(part)
    }


def _normalized_title_parts(screenings: list[Screening]) -> set[str]:
    return {
        normalize_text(title)
        for screening in screenings
        for title in [screening.name_cn, screening.name_cn_base, screening.name_en]
        if normalize_text(title)
    }


def _split_parts(text: str) -> list[str]:
    separators = [",", "，", "、", "/", "／", ";", "；"]
    parts = [text]
    for separator in separators:
        next_parts: list[str] = []
        for part in parts:
            next_parts.extend(part.split(separator))
        parts = next_parts
    return [part.strip() for part in parts]


def _unique_values(values) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = value.strip()
        if value and value not in seen:
            unique.append(value)
            seen.add(value)
    return unique
