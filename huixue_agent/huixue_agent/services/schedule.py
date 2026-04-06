"""日历与「每日任务」对齐：计划起始日、第 N 天、缺勤与未完成检测。"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def effective_plan_start(plan_record: dict[str, Any], fallback_today: date | None = None) -> date:
    """计划第 1 天对应的日历日期：优先 plan_start_date，否则用创建日。"""
    psd = parse_iso_date(plan_record.get("plan_start_date"))
    if psd:
        return psd
    created = plan_record.get("created_at")
    if created:
        c = parse_iso_date(str(created))
        if c:
            return c
    return fallback_today or date.today()


def max_plan_day_index(plan_data: dict[str, Any]) -> int:
    tasks = plan_data.get("daily_tasks") or []
    if not tasks:
        return 0
    days = []
    for t in tasks:
        try:
            days.append(int(t.get("day", 0) or 0))
        except (TypeError, ValueError):
            continue
    return max(days) if days else 0


def calendar_date_for_plan_day(start: date, plan_day: int) -> date:
    return start + timedelta(days=plan_day - 1)


def current_plan_day_index(start: date, today: date) -> int:
    """今天对应计划中的第几天（从 1 起）；早于起始日为 0。"""
    if today < start:
        return 0
    return (today - start).days + 1


def tasks_for_plan_day(plan_data: dict[str, Any], plan_day: int) -> list[dict[str, Any]]:
    tasks = plan_data.get("daily_tasks") or []
    out = []
    for t in tasks:
        try:
            if int(t.get("day", -1)) == plan_day:
                out.append(t)
        except (TypeError, ValueError):
            continue
    return out


def index_logs_by_study_date(logs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """同一自然日多条记录时，保留 id 最大的一条（最后一次提交）。"""
    by_date: dict[str, dict[str, Any]] = {}
    for log in sorted(logs, key=lambda x: (x.get("study_date", ""), x.get("id", 0))):
        key = log.get("study_date") or ""
        if key:
            by_date[key] = log
    return by_date


def scan_missed_and_incomplete(
    start: date,
    today: date,
    max_day: int,
    logs_by_date: dict[str, dict[str, Any]],
    min_completion_ok: float = 50.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    扫描 [start, today) 每个自然日（不含今天）：在计划天数范围内应有打卡。
    无记录视为缺勤；完成率低于阈值视为当日未达标。
    """
    missed: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    if max_day <= 0:
        return missed, incomplete

    d = start
    while d < today:
        plan_day = (d - start).days + 1
        if plan_day > max_day:
            break
        ds = d.isoformat()
        log = logs_by_date.get(ds)
        if log is None:
            missed.append({"date": ds, "plan_day": plan_day})
        else:
            ratio = float(log.get("completion_ratio", 0) or 0)
            if ratio < min_completion_ok:
                incomplete.append(
                    {
                        "date": ds,
                        "plan_day": plan_day,
                        "completion_ratio": ratio,
                    }
                )
        d += timedelta(days=1)
    return missed, incomplete
