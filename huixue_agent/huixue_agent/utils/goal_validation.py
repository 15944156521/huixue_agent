"""
学习需求解析结果：规范化与完整性校验。

与 agents/input_parser.py 中约定的 JSON 字段一致。
"""

from __future__ import annotations

import re
from typing import Any

# 与 InputParser 提示词中的字段一致（顺序用于 UI 展示）
GOAL_FIELD_ORDER = [
    "subject",
    "duration_days",
    "daily_hours",
    "focus_topics",
    "target_description",
]

FIELD_LABELS_ZH = {
    "subject": "学习科目 / 主题",
    "duration_days": "学习周期（天数）",
    "daily_hours": "每日可投入时间（小时）",
    "focus_topics": "重点内容（至少一项）",
    "target_description": "学习目标摘要",
}


def _to_int(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(round(v))
    s = str(v).strip()
    if not s:
        return default
    try:
        return int(float(s))
    except ValueError:
        return default


def _to_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _normalize_focus_topics(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        parts: list[str] = []
        for line in v.replace("，", ",").split("\n"):
            for p in line.split(","):
                t = p.strip()
                if t:
                    parts.append(t)
        return parts
    if isinstance(v, list):
        out: list[str] = []
        for item in v:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    return []


def normalize_parsed_goal(raw: dict[str, Any] | None) -> dict[str, Any]:
    """将 LLM 或用户补充的字段统一为稳定类型。"""
    if not raw:
        raw = {}
    subject = str(raw.get("subject") or "").strip()
    target_description = str(raw.get("target_description") or "").strip()
    duration_days = _to_int(raw.get("duration_days"), 0)
    daily_hours = _to_float(raw.get("daily_hours"), 0.0)
    focus_topics = _normalize_focus_topics(raw.get("focus_topics"))
    return {
        "subject": subject,
        "duration_days": duration_days,
        "daily_hours": daily_hours,
        "focus_topics": focus_topics,
        "target_description": target_description,
    }


def validate_parsed_goal(goal: dict[str, Any] | None) -> list[str]:
    """
    返回尚未满足要求的字段名列表（空列表表示可进入生成计划流程）。

    规则说明：
    - subject：非空
    - duration_days：1～365
    - daily_hours：(0, 24]
    - focus_topics：至少一条非空
    - target_description：非空（用于计划与检索上下文）
    """
    g = normalize_parsed_goal(goal)
    missing: list[str] = []
    if not g["subject"]:
        missing.append("subject")
    d = g["duration_days"]
    if d < 1 or d > 365:
        missing.append("duration_days")
    h = g["daily_hours"]
    if h <= 0 or h > 24:
        missing.append("daily_hours")
    if not g["focus_topics"]:
        missing.append("focus_topics")
    if not g["target_description"]:
        missing.append("target_description")
    return missing


def _text_suggests_duration(u: str) -> bool:
    """用户原文是否像明确说了学习周期（天数/周数/月数）。"""
    if not u:
        return False
    if re.search(r"\d+\s*[天日]", u):
        return True
    if re.search(r"\d+\s*[个]?\s*[周週]", u):
        return True
    if re.search(r"[一两二三四五六七八九十半双两]+[个\s]*[周天週]", u):
        return True
    if re.search(r"\d+\s*个\s*月", u) or "半个月" in u or "半年" in u or "一个月" in u:
        return True
    return False


def _text_suggests_daily_hours(u: str) -> bool:
    if not u:
        return False
    if re.search(r"(每天|每日|一天|每晚)\s*[\d一二两三四五六七八九十]", u):
        return True
    if re.search(r"\d+(?:\.\d+)?\s*[个]?\s*小时", u):
        return True
    if re.search(r"\d+(?:\.\d+)?\s*[hH](?![a-zA-Z\u4e00-\u9fff])", u):
        return True
    return False


def _text_suggests_focus(u: str, topics: list[str]) -> bool:
    if not u or not topics:
        return False
    for t in topics:
        if len(t) >= 2 and t in u:
            return True
    if any(k in u for k in ("重点", "主要", "章节", "单元", "模块", "部分")):
        return True
    return False


def fields_not_evident_in_user_text(user_input: str, goal: dict[str, Any] | None) -> list[str]:
    """
    模型可能仍「猜」了数字或重点；若用户原文未体现，则强制要求走补充交互。
    """
    u = (user_input or "").strip()
    g = normalize_parsed_goal(goal)
    out: list[str] = []
    if 1 <= g["duration_days"] <= 365 and not _text_suggests_duration(u):
        out.append("duration_days")
    if 0 < g["daily_hours"] <= 24 and not _text_suggests_daily_hours(u):
        out.append("daily_hours")
    if g["focus_topics"] and not _text_suggests_focus(u, g["focus_topics"]):
        out.append("focus_topics")
    return out


def goal_missing_fields_for_submission(user_input: str, goal: dict[str, Any] | None) -> list[str]:
    """结构化校验 + 与用户原文对照，合并去重（保持顺序）。"""
    base = validate_parsed_goal(goal)
    extra = fields_not_evident_in_user_text(user_input, goal)
    seen: set[str] = set()
    merged: list[str] = []
    for k in base + extra:
        if k not in seen:
            seen.add(k)
            merged.append(k)
    return merged


def merge_goal_supplements(
    base: dict[str, Any],
    *,
    subject: str | None = None,
    duration_days: int | None = None,
    daily_hours: float | None = None,
    focus_topics_text: str | None = None,
    target_description: str | None = None,
) -> dict[str, Any]:
    """用表单补充项覆盖 base 中对应字段，再规范化。"""
    out = dict(normalize_parsed_goal(base))
    if subject is not None:
        out["subject"] = str(subject).strip()
    if duration_days is not None:
        out["duration_days"] = _to_int(duration_days, 0)
    if daily_hours is not None:
        out["daily_hours"] = _to_float(daily_hours, 0.0)
    if focus_topics_text is not None:
        out["focus_topics"] = _normalize_focus_topics(focus_topics_text)
    if target_description is not None:
        out["target_description"] = str(target_description).strip()
    return normalize_parsed_goal(out)
