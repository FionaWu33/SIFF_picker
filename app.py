from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from siff_picker.filters import TimeSlot, count_unique_films, filter_by_time_slot, filter_future_screenings
from siff_picker.loader import load_screenings
from siff_picker.models import Screening
from siff_picker.recommender import (
    FilmRecommendation,
    InterestProfile,
    filter_excluded_screenings,
    recommend_screenings,
    screening_format_label,
)


DATA_PATH = Path(__file__).parent / "data" / "siff2026.csv"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

TIME_SLOT_OPTIONS = {
    "1": TimeSlot.WEEKDAY_DAY,
    "2": TimeSlot.WEEKDAY_EVENING,
    "3": TimeSlot.WEEKEND_DAY,
    "4": TimeSlot.WEEKEND_EVENING,
    "5": "全天不限",
}
REGION_OPTIONS = {
    "1": "华语",
    "2": "美国",
    "3": "法国",
    "4": "英国",
    "5": "其他欧洲",
    "6": "不限",
}
CONTENT_OPTIONS = {
    "1": "SIFF官方精选 / 竞赛片",
    "2": "名导作品",
    "3": "新锐作品",
    "4": "大银幕视听",
    "5": "非虚构",
    "6": "动画 / 短片 / 特别放映",
    "7": "世界电影 / 多元探索",
    "8": "不限",
}
EXCLUSION_OPTIONS = {
    "1": "恐怖 / 惊悚片",
    "2": "超长片",
    "3": "午夜场",
    "4": "高票价",
    "5": "无中文字幕",
    "6": "短片 / 短片集",
    "7": "不限",
}


def main() -> None:
    screenings = load_screenings(DATA_PATH)
    now = get_current_beijing_time()
    future_screenings = filter_future_screenings(screenings, now)

    print("欢迎使用 SIFF Picker")
    print("=" * 20)
    print("这个小工具会根据你可观看的时间和兴趣偏好，帮你从 SIFF 片单里筛出电影候选池。")
    print(f"总电影数: {count_unique_films(screenings)}")
    print(f"原始场次数: {len(screenings)}")
    print(f"当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"已开始场次过滤后剩余场次数: {len(future_screenings)}")
    print()

    selected_slots, skip_time_filter = prompt_time_slots()
    region_preferences = prompt_region_preferences()
    content_preferences = prompt_content_preferences()
    exclusions = prompt_exclusions()
    creators, works = prompt_supplemental_preferences()

    profile = InterestProfile(
        region_preferences=region_preferences,
        content_preferences=content_preferences,
        exclusions=exclusions,
        creators=creators,
        works=works,
    )

    time_filtered_screenings = future_screenings if skip_time_filter else filter_by_time_slots(future_screenings, selected_slots)
    eligible_screenings = filter_excluded_screenings(time_filtered_screenings, profile)
    recommendations = recommend_screenings(eligible_screenings, profile)
    print_recommendations(recommendations, time_filtered_screenings, eligible_screenings)


def get_current_beijing_time(now_override: datetime | None = None) -> datetime:
    if now_override is None:
        return datetime.now(SHANGHAI_TZ)
    if now_override.tzinfo is None:
        return now_override.replace(tzinfo=SHANGHAI_TZ)
    return now_override.astimezone(SHANGHAI_TZ)


def prompt_time_slots() -> tuple[list[TimeSlot], bool]:
    while True:
        print("一、可用时间，多选（可用英文逗号分隔，例如 2,4）：")
        print("1 工作日白天")
        print("2 工作日晚间")
        print("3 周末白天")
        print("4 周末晚间")
        print("5 全天不限")

        raw_input = input("> ").strip()
        selected = parse_multi_choice(raw_input, TIME_SLOT_OPTIONS)
        if selected:
            if "全天不限" in selected:
                return [], True
            return [slot for slot in selected if isinstance(slot, TimeSlot)], False

        print("输入没有识别成功，请输入 1、2、3、4、5，或类似 2,4 的组合。")
        print()


def prompt_region_preferences() -> list[str]:
    while True:
        print()
        print("二、国家/地区偏好，多选（可用英文逗号分隔）：")
        print("1 华语")
        print("2 美国")
        print("3 法国")
        print("4 英国")
        print("5 其他欧洲")
        print("6 不限")

        selected = parse_multi_choice(input("> ").strip(), REGION_OPTIONS)
        if selected:
            return ["不限"] if "不限" in selected else selected

        print("输入没有识别成功，请输入 1 到 6，或类似 1,3 的组合。")


def prompt_content_preferences() -> list[str]:
    while True:
        print()
        print("三、内容偏好，多选（可用英文逗号分隔）：")
        print("1 SIFF官方精选 / 竞赛片")
        print("2 名导作品")
        print("3 新锐作品")
        print("4 大银幕视听")
        print("5 非虚构")
        print("6 动画 / 短片 / 特别放映")
        print("7 世界电影 / 多元探索")
        print("8 不限")

        selected = parse_multi_choice(input("> ").strip(), CONTENT_OPTIONS)
        if selected:
            return ["不限"] if "不限" in selected else selected

        print("输入没有识别成功，请输入 1 到 8，或类似 1,4 的组合。")


def prompt_exclusions() -> list[str]:
    while True:
        print()
        print("四、排除项，多选（可用英文逗号分隔）：")
        print("1 不看恐怖 / 惊悚片")
        print("2 不看超长片（3 小时及以上）")
        print("3 不看午夜场（散场时间 24:00 后）")
        print("4 不看票价 120 元及以上场次")
        print("5 不看无中文字幕场次")
        print("6 不看短片 / 短片集")
        print("7 不限")

        selected = parse_multi_choice(input("> ").strip(), EXCLUSION_OPTIONS)
        if selected:
            return ["不限"] if "不限" in selected else selected

        print("输入没有识别成功，请输入 1 到 7，或类似 1,2,5 的组合。")


def prompt_supplemental_preferences() -> tuple[list[str], list[str]]:
    print()
    print("五、补充偏好，可跳过。多个内容可用英文逗号分隔，直接回车表示跳过。")
    creators = parse_keyword_list(input("喜欢的导演 / 创作者\n> "))
    works = parse_keyword_list(input("印象深刻的作品\n> "))
    return creators, works


def parse_multi_choice(raw_input: str, options: dict[str, object]) -> list:
    selected: list = []
    seen: set[object] = set()
    exclusive_values = {"不限", "全天不限"}

    for part in raw_input.split(","):
        key = part.strip()
        value = options.get(key)
        if value is None:
            return []
        if value not in seen:
            selected.append(value)
            seen.add(value)

    concrete_selected = [value for value in selected if value not in exclusive_values]
    if concrete_selected:
        return concrete_selected

    return selected


def parse_keyword_list(raw_input: str) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()

    for part in re.split(r"[、，,；;\s]+", raw_input):
        keyword = part.strip()
        normalized = keyword.casefold()
        if keyword and normalized not in seen:
            keywords.append(keyword)
            seen.add(normalized)

    return keywords


def filter_by_time_slots(screenings: list[Screening], slots: list[TimeSlot]) -> list[Screening]:
    matched_by_key: dict[tuple[str, str, str, str, str], Screening] = {}
    for slot in slots:
        for screening in filter_by_time_slot(screenings, slot):
            key = (
                screening.film_id,
                screening.display_name,
                screening.show_date.isoformat(),
                screening.start_time.strftime("%H:%M"),
                screening.cinema,
            )
            matched_by_key.setdefault(key, screening)

    return sorted(
        matched_by_key.values(),
        key=lambda screening: (screening.show_date, screening.start_time, screening.display_name),
    )


def print_recommendations(
    recommendations: list[FilmRecommendation],
    time_filtered_screenings: list[Screening],
    eligible_screenings: list[Screening],
) -> None:
    print()
    print(f"可用时间筛选后场次: {len(time_filtered_screenings)} 场")
    print(f"排除项过滤后场次: {len(eligible_screenings)} 场")
    print(f"候选片池（评分最高前 {len(recommendations)} 部电影）")
    print("=" * 20)

    if not recommendations:
        print("没有找到符合条件的电影。")
        return

    for index, recommendation in enumerate(recommendations, start=1):
        director = recommendation.director or "导演信息暂无"
        country = recommendation.country_or_region or "国家/地区信息暂无"
        duration = f"{recommendation.duration}分钟" if recommendation.duration is not None else "时长信息暂无"

        print(f"{index}. {recommendation.title}")
        print(f"   导演: {director}")
        print(f"   国家/地区: {country}")
        print(f"   时长: {duration}")
        if recommendation.is_fallback:
            print("   候选依据:")
            for basis in recommendation.candidate_basis:
                print(f"   - {basis}")
        else:
            print(f"   推荐分数: {recommendation.score}")
            print("   推荐理由:")
            for reason in recommendation.reasons:
                print(f"   - {reason}")
        print("   可观看场次:")
        for screening in recommendation.screenings:
            show_time = (
                f"{screening.show_date.isoformat()} {screening.weekday} "
                f"{screening.start_time.strftime('%H:%M')}-{screening.end_time.strftime('%H:%M')}"
            )
            cinema = f"{screening.cinema} {screening.hall}".strip()
            format_label = screening_format_label(screening)
            suffix = f" | {format_label}" if format_label else ""
            print(f"   - {show_time} | {cinema}{suffix}")
        print()


if __name__ == "__main__":
    main()
