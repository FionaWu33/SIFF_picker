from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from app import filter_by_time_slots, get_current_beijing_time, parse_keyword_list
from siff_picker.filters import TimeSlot, filter_future_screenings
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
DEMO_MODE = "演示模式"
REAL_MODE = "真实模式"
DEMO_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
RESULTS_PAGE_SIZE = 10
SCREENINGS_PREVIEW_SIZE = 3

TIME_LABEL_TO_SLOT = {
    "工作日白天": TimeSlot.WEEKDAY_DAY,
    "工作日晚间": TimeSlot.WEEKDAY_EVENING,
    "周末白天": TimeSlot.WEEKEND_DAY,
    "周末晚间": TimeSlot.WEEKEND_EVENING,
    "全天不限": "全天不限",
}
REGION_OPTIONS = ["华语", "美国", "法国", "英国", "其他欧洲", "不限"]
CONTENT_OPTIONS = [
    "SIFF官方精选 / 竞赛片",
    "名导作品",
    "新锐作品",
    "大银幕视听",
    "非虚构",
    "动画 / 短片 / 特别放映",
    "世界电影 / 多元探索",
    "不限",
]
EXCLUSION_LABEL_TO_VALUE = {
    "不看恐怖 / 惊悚片": "恐怖 / 惊悚片",
    "不看超长片（≥3小时）": "超长片",
    "不看午夜场（24:00后）": "午夜场",
    "不看票价 ≥120": "高票价",
    "不看无中文字幕": "无中文字幕",
    "不看短片 / 短片集": "短片 / 短片集",
    "不限": "不限",
}


@st.cache_data
def load_all_screenings() -> list[Screening]:
    return load_screenings(DATA_PATH)


def main() -> None:
    st.set_page_config(page_title="SIFF Picker", page_icon="🎬", layout="centered")
    st.title("SIFF Picker")
    st.caption("在有限的时间和精力约束下，帮你从 SIFF 海量片单中找到可能感兴趣的电影。")
    st.caption(
        "• 基于 SIFF 官方片单与放映数据  \n"
        "• 结合可用时间、内容偏好和排除项生成候选片单  \n"
        "• 提供推荐理由与候选依据，保留用户最终判断"
    )

    with st.container(border=True):
        st.subheader("筛选条件")
        st.caption("未选择的条件默认按“不限”处理。")

        run_mode = st.radio(
            "运行模式",
            [DEMO_MODE, REAL_MODE],
            index=0,
            horizontal=True,
        )
        if run_mode == DEMO_MODE:
            st.caption("演示模式：使用固定时间 2026-06-15 12:00，仅用于体验产品逻辑。")
        else:
            st.caption("真实模式：使用当前北京时间过滤已开始场次。")
        st.divider()

        selected_time_labels = _checkbox_group(
            "可用时间（多选）",
            list(TIME_LABEL_TO_SLOT.keys()),
            key_prefix="time",
            exclusive_option="全天不限",
        )
        st.divider()

        selected_regions = _checkbox_group(
            "国家 / 地区偏好（多选）",
            REGION_OPTIONS,
            key_prefix="region",
            exclusive_option="不限",
        )
        st.divider()

        selected_contents = _checkbox_group(
            "内容偏好（多选）",
            CONTENT_OPTIONS,
            key_prefix="content",
            exclusive_option="不限",
        )
        st.divider()

        selected_exclusion_labels = _checkbox_group(
            "排除项（多选）",
            list(EXCLUSION_LABEL_TO_VALUE.keys()),
            key_prefix="exclusion",
            columns=2,
            exclusive_option="不限",
        )
        selected_exclusions = [EXCLUSION_LABEL_TO_VALUE[label] for label in selected_exclusion_labels]
        st.divider()

        creators_text = st.text_input(
            "喜欢的导演 / 创作者（可跳过）",
            value="",
            placeholder="如：杨德昌、比利·怀尔德",
        )
        works_text = st.text_input(
            "印象深刻的作品（可跳过）",
            value="",
            placeholder="如：一一、哈利·波特、桃色公寓",
        )

        submitted = st.button("生成候选片单", type="primary")

    if submitted:
        now_override = DEMO_NOW if run_mode == DEMO_MODE else None
        result = _generate_recommendations(
            selected_time_labels,
            selected_regions,
            selected_contents,
            selected_exclusions,
            creators_text,
            works_text,
            now_override=now_override,
            run_mode=run_mode,
        )
        result["has_content_preferences"] = _has_content_preferences(
            selected_regions,
            selected_contents,
            creators_text,
            works_text,
        )
        st.session_state["last_result"] = result
        st.session_state["visible_recommendation_count"] = RESULTS_PAGE_SIZE

    if "last_result" not in st.session_state:
        st.info("完成选择后，点击“生成候选片单”查看结果。")
        return

    result = st.session_state["last_result"]
    _render_results(result["recommendations"], result.get("has_content_preferences", False))


def _generate_recommendations(
    selected_time_labels: list[str],
    selected_regions: list[str],
    selected_contents: list[str],
    selected_exclusions: list[str],
    creators_text: str,
    works_text: str,
    now_override: datetime | None = None,
    run_mode: str = REAL_MODE,
) -> dict:
    screenings = load_all_screenings()
    now = get_current_beijing_time(now_override)
    future_screenings = filter_future_screenings(screenings, now)

    selected_time_values = _normalize_unlimited_selection(
        [TIME_LABEL_TO_SLOT[label] for label in selected_time_labels],
        unlimited_value="全天不限",
    )
    skip_time_filter = "全天不限" in selected_time_values
    time_filtered_screenings = (
        future_screenings
        if skip_time_filter
        else filter_by_time_slots(future_screenings, [value for value in selected_time_values if isinstance(value, TimeSlot)])
    )

    profile = InterestProfile(
        region_preferences=_normalize_unlimited_selection(selected_regions, unlimited_value="不限"),
        content_preferences=_normalize_unlimited_selection(selected_contents, unlimited_value="不限"),
        exclusions=_normalize_unlimited_selection(selected_exclusions, unlimited_value="不限"),
        creators=parse_keyword_list(creators_text),
        works=parse_keyword_list(works_text),
    )
    eligible_screenings = filter_excluded_screenings(time_filtered_screenings, profile)
    recommendations = recommend_screenings(eligible_screenings, profile)
    return {
        "screenings": screenings,
        "future_screenings": future_screenings,
        "time_filtered_screenings": time_filtered_screenings,
        "eligible_screenings": eligible_screenings,
        "recommendations": recommendations,
        "now": now,
        "run_mode": run_mode,
    }


def _normalize_unlimited_selection(values: list, unlimited_value: str) -> list:
    concrete_values = [value for value in values if value != unlimited_value]
    if concrete_values:
        return concrete_values
    return [unlimited_value]


def _has_content_preferences(
    selected_regions: list[str],
    selected_contents: list[str],
    creators_text: str,
    works_text: str,
) -> bool:
    return bool(
        [region for region in selected_regions if region != "不限"]
        or [content for content in selected_contents if content != "不限"]
        or parse_keyword_list(creators_text)
        or parse_keyword_list(works_text)
    )


def _checkbox_group(
    label: str,
    options: list[str],
    key_prefix: str,
    columns: int = 3,
    exclusive_option: str | None = None,
) -> list[str]:
    st.markdown(f"**{label}**")
    selected: list[str] = []
    option_columns = st.columns(columns)
    keys = [f"{key_prefix}_{index}" for index in range(len(options))]
    exclusive_key = keys[options.index(exclusive_option)] if exclusive_option in options else None

    for index, option in enumerate(options):
        key = keys[index]
        with option_columns[index % columns]:
            st.checkbox(
                option,
                value=False,
                key=key,
                on_change=_sync_exclusive_checkbox_group,
                args=(key, keys, exclusive_key),
            )
            if st.session_state.get(key, False):
                selected.append(option)
    return selected


def _sync_exclusive_checkbox_group(changed_key: str, keys: list[str], exclusive_key: str | None) -> None:
    if exclusive_key is None or not st.session_state.get(changed_key, False):
        return

    if changed_key == exclusive_key:
        for key in keys:
            if key != exclusive_key:
                st.session_state[key] = False
        return

    st.session_state[exclusive_key] = False


def _render_results(recommendations: list[FilmRecommendation], has_content_preferences: bool) -> None:
    has_fallback_recommendations = any(recommendation.is_fallback for recommendation in recommendations)
    display_recommendations = recommendations[:20] if has_fallback_recommendations else recommendations
    total_count = len(display_recommendations)

    st.subheader(f"推荐片单（共 {total_count} 部）")
    if has_content_preferences:
        st.caption("根据你的筛选条件，为你生成以下片单。")
    else:
        st.caption("以下按官方内容优先级与可观看时间排序。")

    if not display_recommendations:
        st.warning("没有找到符合条件的电影。")
        return

    visible_count = min(
        st.session_state.get("visible_recommendation_count", RESULTS_PAGE_SIZE),
        total_count,
    )
    for recommendation in display_recommendations[:visible_count]:
        _render_recommendation_card(recommendation)

    if visible_count < total_count:
        st.button(
            "查看更多",
            key="show_more_recommendations",
            on_click=_show_more_recommendations,
            args=(total_count,),
        )
    else:
        st.caption("已展示全部推荐片单")


def _show_more_recommendations(total_count: int) -> None:
    current_count = st.session_state.get("visible_recommendation_count", RESULTS_PAGE_SIZE)
    st.session_state["visible_recommendation_count"] = min(
        current_count + RESULTS_PAGE_SIZE,
        total_count,
    )


def _render_recommendation_card(recommendation: FilmRecommendation) -> None:
    with st.container(border=True):
        st.markdown(f"#### 《{recommendation.title}》")
        metadata = [
            f"导演：{recommendation.director or '暂无'}",
            f"国家 / 地区：{recommendation.country_or_region or '暂无'}",
            f"时长：{recommendation.duration}分钟" if recommendation.duration is not None else "时长：暂无",
        ]
        official_group = _official_group(recommendation)
        if official_group:
            metadata.append(f"官方单元：{official_group}")
        st.caption(" ｜ ".join(metadata))

        if recommendation.is_fallback:
            st.markdown("**候选依据**")
            _render_reason_tags(recommendation.candidate_basis)
        else:
            st.markdown("**推荐理由**")
            _render_reason_tags(recommendation.reasons)

        st.markdown("**可观看场次**")
        preview_screenings = recommendation.screenings[:SCREENINGS_PREVIEW_SIZE]
        remaining_screenings = recommendation.screenings[SCREENINGS_PREVIEW_SIZE:]
        for screening in preview_screenings:
            st.markdown(f"- {_format_screening(screening)}")

        if remaining_screenings:
            with st.expander(f"查看更多场次（{len(remaining_screenings)}）"):
                for screening in remaining_screenings:
                    st.markdown(f"- {_format_screening(screening)}")


def _official_group(recommendation: FilmRecommendation) -> str:
    return next((screening.group.strip() for screening in recommendation.screenings if screening.group.strip()), "")


def _render_reason_tags(reasons: list[str]) -> None:
    tags: list[str] = []
    for reason in reasons:
        if reason.startswith("命中内容偏好："):
            tags.extend(part.strip() for part in reason.removeprefix("命中内容偏好：").split(",") if part.strip())
        elif reason.startswith("命中国家 / 地区偏好："):
            tags.append(f"地区：{reason.removeprefix('命中国家 / 地区偏好：')}")
        elif reason.startswith("命中创作者偏好："):
            tags.append(f"创作者：{reason.removeprefix('命中创作者偏好：')}")
        elif reason.startswith("命中作品偏好："):
            tags.append(f"作品：{reason.removeprefix('命中作品偏好：')}")
        elif reason.startswith("属于 "):
            tags.append(reason.removeprefix("属于 "))
        else:
            tags.append(reason)

    unique_tags = list(dict.fromkeys(tag for tag in tags if tag))
    st.markdown(" ".join(f"`{tag}`" for tag in unique_tags))


def _format_screening(screening: Screening) -> str:
    show_time = (
        f"{screening.show_date.month}月{screening.show_date.day}日 {screening.weekday} "
        f"{screening.start_time.strftime('%H:%M')}-{screening.end_time.strftime('%H:%M')}"
    )
    cinema = f"{screening.cinema} {screening.hall}".strip()
    format_label = _clean_format_label(screening_format_label(screening))
    if format_label:
        return f"{show_time}｜{cinema}｜{format_label}"
    return f"{show_time}｜{cinema}"


def _clean_format_label(format_label: str) -> str:
    labels = [label.strip() for label in format_label.split("/") if label.strip()]
    unique_labels = list(dict.fromkeys(label.upper() for label in labels))
    display_labels = ["杜比" if label == "杜比".upper() else label for label in unique_labels]
    return " / ".join(display_labels)


if __name__ == "__main__":
    main()
