from __future__ import annotations

from dataclasses import dataclass

from .models import Screening


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
PREMIUM_FORMAT_KEYWORDS = {"4K", "IMAX", "CINITY", "DOLBY VISION", "ONYX", "LUXE", "XR"}
PREMIUM_HALL_KEYWORDS = {"4K", "IMAX", "CINITY", "杜比", "巨幕", "激光", "ONYX", "LUXE"}
NORMALIZE_REMOVE_CHARS = str.maketrans("", "", "· .-/")


@dataclass(frozen=True)
class InterestProfile:
    region_preferences: list[str]
    prefer_premium_format: bool
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
    screenings: list[Screening]
    has_creator_or_work_match: bool
    has_premium_format_match: bool


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

    return sorted(
        recommendations,
        key=lambda item: (
            -item.score,
            not item.has_creator_or_work_match,
            not item.has_premium_format_match,
            -len(item.screenings),
            item.screenings[0].show_date,
            item.screenings[0].start_time,
            item.title,
        ),
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

    region_hits = _matched_region_preferences(screenings, profile.region_preferences)
    if region_hits:
        score += 2
        reasons.append(f"命中国家/地区偏好：{', '.join(region_hits)}")

    has_premium_format_match = profile.prefer_premium_format and any(
        _is_premium_screening(screening) for screening in screenings
    )
    if has_premium_format_match:
        score += 1
        reasons.append("命中影院设施偏好：存在视听效果更佳的可观看场次")

    reasons.append(f"存在 {len(screenings)} 个可观看场次")

    return FilmRecommendation(
        title=representative.display_name,
        director=representative.director,
        country_or_region=representative.country,
        duration=representative.length_min,
        score=score,
        reasons=_unique_values(reasons),
        screenings=screenings,
        has_creator_or_work_match=has_creator_or_work_match,
        has_premium_format_match=has_premium_format_match,
    )


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


def _is_premium_screening(screening: Screening) -> bool:
    format_text = screening.format_flags.upper()
    hall_text = screening.hall.upper()
    return (
        screening.is_4k
        or any(keyword in format_text for keyword in PREMIUM_FORMAT_KEYWORDS)
        or any(keyword.upper() in hall_text for keyword in PREMIUM_HALL_KEYWORDS)
    )


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
