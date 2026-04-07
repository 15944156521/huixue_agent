from __future__ import annotations

import json
import os
from datetime import date

import streamlit as st

from services.schedule import calendar_date_for_plan_day, parse_iso_date
from services.study_planner_service import StudyPlannerService
from utils.goal_validation import (
    FIELD_LABELS_ZH,
    goal_missing_fields_for_submission,
    merge_goal_supplements,
    validate_parsed_goal,
)

GOAL_CLARIFY_CREATE = "goal_clarify_create"
GOAL_CLARIFY_RECREATE = "goal_clarify_recreate"

# 侧边栏展示标签 → 内部页面名（逻辑分支不变）
NAV_ITEMS: list[tuple[str, str]] = [
    ("🏠 首页总览", "首页总览"),
    ("✨ 学习计划生成", "学习计划生成"),
    ("📋 当前学习计划", "当前学习计划"),
    ("📈 学习进度反馈", "学习进度反馈"),
    ("📝 学习检测", "学习检测"),
    ("🔄 动态调整", "动态调整"),
]


st.set_page_config(
    page_title="AI 学习助手",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
service = StudyPlannerService(api_key=API_KEY)

if "latest_generated_evaluation" not in st.session_state:
    st.session_state.latest_generated_evaluation = None


def handle_goal_clarification_flow(service: StudyPlannerService, state_key: str):
    """
    若 session 中存在待补充的结构化目标，则展示表单。
    用户补充完整后执行 create_plan(parsed_goal=...) 并返回 (plan, rag)；否则返回 (None, None)。
    """
    pending = st.session_state.get(state_key)
    if not pending:
        return None, None

    parsed = pending["parsed_goal"]
    missing = goal_missing_fields_for_submission(pending["user_input"], parsed)

    if not missing:
        st.session_state.pop(state_key, None)
        with st.spinner("正在生成学习计划..."):
            try:
                return service.create_plan(
                    pending["user_input"],
                    plan_start_date=pending["plan_start"],
                    parsed_goal=parsed,
                )
            except ValueError:
                return None, None

    st.warning("🧩 还缺几样信息～补全后就能生成计划啦。")
    with st.expander("🔍 当前解析结果（可对照修改）", expanded=False):
        st.json(parsed)

    with st.form(f"goal_clarify_{state_key}"):
        subject_val = duration_val = hours_val = topics_val = desc_val = None
        if "subject" in missing:
            subject_val = st.text_input(
                FIELD_LABELS_ZH["subject"],
                value=parsed.get("subject") or "",
            )
        if "duration_days" in missing:
            d0 = int(parsed.get("duration_days") or 7)
            d0 = max(1, min(365, d0))
            duration_val = st.number_input(
                FIELD_LABELS_ZH["duration_days"],
                min_value=1,
                max_value=365,
                value=d0,
                step=1,
            )
        if "daily_hours" in missing:
            h0 = float(parsed.get("daily_hours") or 2.0)
            h0 = max(0.5, min(24.0, h0))
            hours_val = st.number_input(
                FIELD_LABELS_ZH["daily_hours"],
                min_value=0.5,
                max_value=24.0,
                value=h0,
                step=0.5,
            )
        if "focus_topics" in missing:
            topics = parsed.get("focus_topics") or []
            topics_str = "、".join(topics) if topics else ""
            topics_val = st.text_area(
                FIELD_LABELS_ZH["focus_topics"] + "（每行一条，或用逗号、顿号分隔）",
                value=topics_str,
                height=100,
            )
        if "target_description" in missing:
            desc_val = st.text_area(
                FIELD_LABELS_ZH["target_description"],
                value=parsed.get("target_description") or "",
                height=80,
            )
        c1, c2 = st.columns(2)
        with c1:
            cancelled = st.form_submit_button("↩️ 取消", use_container_width=True)
        with c2:
            submitted = st.form_submit_button(
                "✅ 补全并生成计划", type="primary", use_container_width=True
            )

    if cancelled:
        st.session_state.pop(state_key, None)
        st.rerun()

    if submitted:
        kw = {}
        if "subject" in missing:
            kw["subject"] = subject_val
        if "duration_days" in missing and duration_val is not None:
            kw["duration_days"] = int(duration_val)
        if "daily_hours" in missing and hours_val is not None:
            kw["daily_hours"] = float(hours_val)
        if "focus_topics" in missing:
            kw["focus_topics_text"] = topics_val
        if "target_description" in missing:
            kw["target_description"] = desc_val
        merged = merge_goal_supplements(parsed, **kw)
        still = validate_parsed_goal(merged)
        if still:
            st.session_state[state_key]["parsed_goal"] = merged
            hint = "、".join(FIELD_LABELS_ZH[k] for k in still)
            st.error(f"以下信息仍不完整或超出合理范围，请继续补充：{hint}")
            st.rerun()
        st.session_state.pop(state_key, None)
        with st.spinner("正在生成学习计划..."):
            try:
                return service.create_plan(
                    pending["user_input"],
                    plan_start_date=pending["plan_start"],
                    parsed_goal=merged,
                )
            except ValueError:
                st.error("生成失败，请检查填写内容。")
                return None, None

    return None, None


def show_plan_success(
    plan,
    plan_rag: str | None,
    *,
    show_parsed_json: bool = True,
    success_message: str = "🎉 计划已保存。",
):
    st.success(success_message)
    show_rag_snippets("📚 知识库参考片段（RAG）", plan_rag)
    snap = service.get_schedule_snapshot(plan["id"])
    render_plan(plan, snap)
    if show_parsed_json:
        with st.expander("🧾 结构化目标 JSON", expanded=False):
            st.code(json.dumps(plan["parsed_goal"], ensure_ascii=False, indent=2), language="json")


def show_rag_snippets(title: str, content: str | None):
    """折叠展示本次 RAG 检索到的知识片段。"""
    with st.expander(title, expanded=False):
        text = (content or "").strip()
        if text:
            st.markdown(text)
        else:
            st.caption("暂无命中片段。可在 `data/knowledge/` 添加 .md / .txt 后重试。")


def page_header(title: str, subtitle: str | None = None, icon: str = "✨"):
    sub = (
        f'<p class="hx-subtitle">{subtitle}</p>'
        if subtitle
        else ""
    )
    st.markdown(
        f"""
        <div class="hx-page-head">
            <span class="hx-page-icon" aria-hidden="true">{icon}</span>
            <div>
                <h1 class="hx-page-title">{title}</h1>
                {sub}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def inject_styles():
    st.markdown(
        """
        <style>
            .main .block-container {
                padding-top: 1.5rem;
                padding-bottom: 2rem;
                max-width: 920px;
            }
            .stApp {
                background: #f6f7f9;
            }
            [data-testid="stSidebar"] {
                background: #ffffff;
                border-right: 1px solid #e8eaed;
            }
            [data-testid="stSidebar"] .block-container {
                padding-top: 1.25rem;
            }
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            .hx-page-head {
                display: flex;
                align-items: flex-start;
                gap: 0.75rem;
                margin-bottom: 1.25rem;
                padding-bottom: 1rem;
                border-bottom: 1px solid #e8eaed;
            }
            .hx-page-icon {
                font-size: 1.75rem;
                line-height: 1.2;
            }
            .hx-page-title {
                font-size: 1.35rem;
                font-weight: 600;
                color: #1a1a1a;
                margin: 0;
                letter-spacing: -0.02em;
            }
            .hx-subtitle {
                font-size: 0.9rem;
                color: #5f6368;
                margin: 0.35rem 0 0 0;
                line-height: 1.5;
            }
            .hx-hero {
                background: #fff;
                border: 1px solid #e8eaed;
                border-radius: 12px;
                padding: 1.25rem 1.35rem;
                margin-bottom: 1rem;
            }
            .hx-hero-title {
                font-size: 1.25rem;
                font-weight: 600;
                color: #1a1a1a;
                margin: 0 0 0.5rem 0;
            }
            .hx-hero-desc {
                color: #5f6368;
                font-size: 0.92rem;
                line-height: 1.55;
                margin: 0;
            }
            .hx-pill-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin: 0.75rem 0 0 0;
            }
            .hx-pill {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                font-size: 0.8rem;
                padding: 0.35rem 0.65rem;
                border-radius: 999px;
                background: #f1f3f4;
                color: #3c4043;
            }
            .hx-card {
                background: #fff;
                border: 1px solid #e8eaed;
                border-radius: 10px;
                padding: 1rem 1.1rem;
                margin-bottom: 0.65rem;
            }
            .hx-section-label {
                font-size: 0.78rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.04em;
                color: #80868b;
                margin: 1.1rem 0 0.5rem 0;
            }
            .hx-task-title {
                font-weight: 600;
                color: #202124;
                font-size: 0.95rem;
            }
            .hx-task-meta {
                color: #80868b;
                font-size: 0.82rem;
                margin-top: 0.25rem;
            }
            div[data-testid="stExpander"] details {
                border: 1px solid #e8eaed !important;
                border-radius: 10px !important;
                background: #fff !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_plan(plan_record, schedule_snapshot=None):
    if not plan_record:
        st.info("📭 暂无计划，请先去「学习计划生成」。")
        return

    plan_data = plan_record["plan_data"]
    if schedule_snapshot:
        with st.expander("📅 日历对齐", expanded=False):
            st.caption(
                f"起始 **{schedule_snapshot['plan_start_date']}** · 今日 **{schedule_snapshot['today_iso']}** · "
                f"第 **{schedule_snapshot['current_plan_day']}** / {schedule_snapshot['max_plan_day']} 天"
            )

    st.markdown('<p class="hx-section-label">摘要</p>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="hx-card">{plan_data.get("summary", "暂无摘要")}</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        with st.expander("🪜 阶段安排", expanded=False):
            stages = plan_data.get("stages", [])
            if stages:
                for stage in stages:
                    st.markdown(f"**{stage.get('name', '阶段')}** · {stage.get('days', '待定')}")
                    focus_list = stage.get("focus", [])
                    if focus_list:
                        st.caption("重点：" + "、".join(focus_list))
            else:
                st.caption("暂无")

    with c2:
        with st.expander("🎯 里程碑", expanded=False):
            milestones = plan_data.get("milestones", [])
            if milestones:
                for item in milestones:
                    st.write(f"· {item}")
            else:
                st.caption("暂无")

    daily_tasks = plan_data.get("daily_tasks", [])
    n_tasks = len(daily_tasks)
    start_d = None
    if schedule_snapshot:
        start_d = parse_iso_date(schedule_snapshot.get("plan_start_date"))

    st.markdown(
        f'<p class="hx-section-label">每日任务 · {n_tasks} 项</p>',
        unsafe_allow_html=True,
    )
    if daily_tasks:
        for task in daily_tasks:
            day_n = task.get("day", "-")
            cal_label = ""
            if start_d is not None:
                try:
                    dn = int(day_n)
                    if dn >= 1:
                        cal_label = calendar_date_for_plan_day(start_d, dn).isoformat()
                except (TypeError, ValueError):
                    pass
            line1 = f"Day {day_n}"
            if cal_label:
                line1 += f" · {cal_label}"
            st.markdown(
                f"""
                <div class="hx-card">
                    <div class="hx-task-title">{line1}</div>
                    <div style="margin-top:0.35rem;color:#3c4043;font-size:0.9rem;">{task.get('task', '')}</div>
                    <div class="hx-task-meta">⏱ 约 {task.get('estimated_hours', 0)} 小时</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("暂无每日任务。")


def render_sidebar(service, current_plan):
    st.sidebar.markdown("### 📌 菜单")
    labels = [pair[0] for pair in NAV_ITEMS]
    picked = st.sidebar.radio(
        "页面",
        labels,
        label_visibility="collapsed",
    )
    page = dict(NAV_ITEMS)[picked]

    st.sidebar.divider()
    st.sidebar.caption("⏰ 今日")
    st.sidebar.markdown(f"**{date.today().isoformat()}**")
    if current_plan:
        snap = service.get_schedule_snapshot(current_plan["id"])
        if snap:
            st.sidebar.caption("📍 计划进度")
            st.sidebar.markdown(f"第 **{snap['current_plan_day']}** 天")
            if snap["needs_attention"]:
                st.sidebar.error("⚠️ 有缺勤/未达标")
            elif snap["today_tasks"]:
                st.sidebar.success("✅ 今日有任务")
            else:
                st.sidebar.caption("今日无日序任务")

    st.sidebar.divider()
    st.sidebar.caption("状态")
    if current_plan:
        st.sidebar.markdown("计划：**已生成** ✓")
        with st.sidebar.expander("技术信息", expanded=False):
            st.caption(f"计划 ID `{current_plan['id']}`")
            st.caption(f"知识库片段 {service.retriever.chunk_count()}")
            st.caption("编排 · LangGraph")
    else:
        st.sidebar.markdown("计划：**未生成**")
        with st.sidebar.expander("技术信息", expanded=False):
            st.caption(f"知识库片段 {service.retriever.chunk_count()}")
            st.caption("编排 · LangGraph")
    return page


def render_home(current_plan):
    page_header(
        "AI 学习助手",
        "定计划 → 打卡 → 小测 → 按需调整，一条龙搞定学习节奏。",
        icon="📘",
    )
    st.markdown(
        """
        <div class="hx-hero">
            <p class="hx-hero-desc">
                用自然语言说出目标，系统会帮你拆成可执行日程；记得常来记进度、做检测，偏了还能一键重排。
            </p>
            <div class="hx-pill-row">
                <span class="hx-pill">✨ 智能计划</span>
                <span class="hx-pill">📈 进度</span>
                <span class="hx-pill">📝 小测</span>
                <span class="hx-pill">🔄 调整</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if current_plan:
        st.success("🌟 已有计划，去记进度或做个小测吧～")
        snap = service.get_schedule_snapshot(current_plan["id"])
        if snap and snap["needs_attention"]:
            st.warning("🗓 有几天没打卡或完成率偏低，记得补录或去「动态调整」。")
            with st.expander("缺勤 / 未达标日期", expanded=False):
                if snap["missed_days"]:
                    st.write("缺勤：", snap["missed_days"])
                if snap["incomplete_days"]:
                    st.write("未达标：", snap["incomplete_days"])
        if snap and snap["today_tasks"]:
            st.markdown('<p class="hx-section-label">今日任务</p>', unsafe_allow_html=True)
            for t in snap["today_tasks"]:
                st.markdown(
                    f"""
                    <div class="hx-card">
                        <div class="hx-task-title">Day {t.get('day')}</div>
                        <div style="margin-top:0.3rem;font-size:0.9rem;color:#3c4043;">{t.get('task', '')}</div>
                        <div class="hx-task-meta">⏱ 约 {t.get('estimated_hours', 0)} 小时</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        with st.expander("📋 展开完整计划", expanded=False):
            render_plan(current_plan, snap)
    else:
        st.info("👋 还没有计划，去左侧「✨ 学习计划生成」写一句目标试试吧。")


def render_create_plan():
    page_header(
        "学习计划生成",
        "写清楚目标；缺信息时会自动让你补几笔，再生成计划。",
        icon="✨",
    )
    with st.expander("💡 怎么用", expanded=False):
        st.caption(
            "选起始日 → 描述目标 → 点生成。若周期、每日时长或重点没说清，会出现补充表单。"
        )

    plan_done, rag_done = handle_goal_clarification_flow(service, GOAL_CLARIFY_CREATE)
    if plan_done:
        show_plan_success(plan_done, rag_done)

    plan_start = st.date_input(
        "📅 计划第 1 天（日历起点）",
        value=date.today(),
        help="Day 1、Day 2… 与真实日期对齐；用于今日任务与缺勤判断。",
    )
    user_input = st.text_area(
        "🎯 学习目标（自然语言）",
        height=140,
        placeholder="例：两周复习操作系统，每天 3 小时，重点进程与内存",
    )
    if st.button("🚀 生成并保存学习计划", type="primary", use_container_width=True):
        if not user_input.strip():
            st.warning("请输入学习目标。")
        else:
            parsed = service.parse_user_goal(user_input.strip())
            if service.goal_missing_fields(parsed, user_input.strip()):
                st.session_state[GOAL_CLARIFY_CREATE] = {
                    "user_input": user_input.strip(),
                    "plan_start": plan_start,
                    "parsed_goal": parsed,
                }
                st.rerun()
            else:
                with st.spinner("正在解析需求并生成学习计划..."):
                    plan, plan_rag = service.create_plan(
                        user_input.strip(),
                        plan_start_date=plan_start,
                        parsed_goal=parsed,
                    )
                if plan:
                    show_plan_success(plan, plan_rag)
                else:
                    st.error("学习计划生成失败，请检查网络或稍后重试。")


def render_current_plan(current_plan):
    page_header("当前学习计划", "查看日程；需要重来时在下方展开。", icon="📋")
    if not current_plan:
        st.info("还没有计划，请先去「学习计划生成」。")
        return
    snap = service.get_schedule_snapshot(current_plan["id"])
    render_plan(current_plan, snap)
    with st.expander("🔁 重新制定学习计划"):
        plan_done, rag_done = handle_goal_clarification_flow(service, GOAL_CLARIFY_RECREATE)
        if plan_done:
            show_plan_success(
                plan_done,
                rag_done,
                show_parsed_json=False,
                success_message="🎉 新计划已保存。",
            )

        existing_start = parse_iso_date(current_plan.get("plan_start_date")) or date.today()
        plan_start = st.date_input("📅 新计划第 1 天", value=existing_start)
        user_input = st.text_area(
            "🎯 新的学习目标",
            height=110,
            placeholder="例：一周复习数据结构，每天 2 小时，重点树与图",
        )
        if st.button("🚀 重新生成计划", use_container_width=True):
            if not user_input.strip():
                st.warning("请输入新的学习目标。")
            else:
                parsed = service.parse_user_goal(user_input.strip())
                if service.goal_missing_fields(parsed, user_input.strip()):
                    st.session_state[GOAL_CLARIFY_RECREATE] = {
                        "user_input": user_input.strip(),
                        "plan_start": plan_start,
                        "parsed_goal": parsed,
                    }
                    st.rerun()
                else:
                    with st.spinner("正在解析需求并生成新的学习计划..."):
                        plan, plan_rag = service.create_plan(
                            user_input.strip(),
                            plan_start_date=plan_start,
                            parsed_goal=parsed,
                        )
                    if plan:
                        show_plan_success(
                            plan,
                            plan_rag,
                            show_parsed_json=False,
                            success_message="🎉 新计划已保存。",
                        )
                    else:
                        st.error("生成失败，请稍后重试。")


def render_progress(current_plan):
    page_header("学习进度反馈", "记一笔今天学了多少，系统会顺手出反馈和小测题。", icon="📈")
    if not current_plan:
        st.info("请先生成计划。")
        return

    snap = service.get_schedule_snapshot(current_plan["id"])
    if snap:
        with st.expander("📌 今日对齐信息", expanded=False):
            st.caption(
                f"{snap['today_iso']} · 起始 {snap['plan_start_date']} · "
                f"计划第 **{snap['current_plan_day']}** 天"
            )
            if snap["today_tasks"]:
                for t in snap["today_tasks"]:
                    st.write(f"· Day {t.get('day')}：{t.get('task', '')}（~{t.get('estimated_hours', 0)}h）")
        if snap["needs_attention"]:
            st.warning("有缺勤或某天完成率低于 50%，可改日期补录或去「动态调整」。")

    col1, col2 = st.columns([1.1, 1])
    with col1:
        record_date = st.date_input(
            "📅 进度日期",
            value=date.today(),
            help="补录昨天请改选日期。",
        )
        completion_ratio = st.slider("✅ 当日完成度 (%)", 0, 100, 60)
        completed_tasks = st.text_area("✔️ 已完成", placeholder="今天搞定了什么")
        pending_tasks = st.text_area("⏳ 未完成", placeholder="还剩什么")
    with col2:
        delay_reason = st.text_input("🤔 偏差原因（可选）", placeholder="时间不够 / 其他课挤占…")
        note = st.text_area("💭 备注（可选）", height=160, placeholder="随手记两句")

    if st.button("📤 提交进度并生成反馈", type="primary", use_container_width=True):
        progress_data = {
            "study_date": record_date.isoformat(),
            "completion_ratio": completion_ratio,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "delay_reason": delay_reason,
            "note": note,
        }
        latest = service.record_progress(current_plan["id"], progress_data)
        generated_evaluation = service.generate_evaluation(current_plan["id"])
        st.session_state.latest_generated_evaluation = generated_evaluation
        if latest:
            st.success("📝 已记下～")
            with st.expander("📊 反馈详情", expanded=False):
                st.json(latest["feedback"])
            if generated_evaluation:
                show_rag_snippets(
                    "📚 出题参考（RAG）",
                    generated_evaluation.get("rag_context"),
                )
                st.info("🎯 检测题已备好，去「📝 学习检测」答题吧。")
        else:
            st.error("学习进度记录失败，请稍后重试。")


def render_evaluation(current_plan):
    page_header("学习检测", "先记进度才会出题；答完保存结果。", icon="📝")
    if not current_plan:
        st.info("请先生成计划。")
        return

    latest_generated_evaluation = st.session_state.latest_generated_evaluation
    latest_saved_evaluation = service.get_latest_evaluation(current_plan["id"])

    if latest_generated_evaluation:
        if latest_generated_evaluation.get("focus_summary"):
            st.caption(f"🎯 {latest_generated_evaluation.get('focus_summary', '')}")
        show_rag_snippets(
            "📚 出题参考（RAG）",
            latest_generated_evaluation.get("rag_context"),
        )
        st.markdown('<p class="hx-section-label">题目</p>', unsafe_allow_html=True)
        for question in latest_generated_evaluation.get("questions", []):
            st.markdown(
                f"""
                <div class="hx-card">
                    <div class="hx-task-title">{question.get('id', '-')} · {question.get('type', '题')}</div>
                    <div style="margin-top:0.4rem;font-size:0.92rem;color:#202124;">{question.get('question', '')}</div>
                    <div class="hx-task-meta">考点：{question.get('check_point', '')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        total_questions = len(latest_generated_evaluation.get("questions", []))
        score = st.number_input(
            "✅ 答对几题？",
            min_value=0,
            max_value=max(total_questions, 1),
            value=0,
            step=1,
        )
        user_answers = st.text_area("✏️ 答题简述（可选）", placeholder="一两句思路即可")
        evaluation_summary = st.text_area("🪞 自我总结（可选）", placeholder="哪里卡住了？")

        if st.button("💾 提交检测结果", type="primary", use_container_width=True):
            saved_evaluation = service.save_evaluation_result(
                current_plan["id"],
                score=score,
                total_questions=total_questions,
                user_answers=user_answers,
                summary=evaluation_summary,
                questions=latest_generated_evaluation.get("questions", []),
            )
            if saved_evaluation:
                st.success("🎉 已保存")
                with st.expander("📊 结果详情", expanded=False):
                    st.json(saved_evaluation)
    elif latest_saved_evaluation:
        st.success("📂 已有最近一次检测结果")
        with st.expander("📊 查看详情", expanded=False):
            st.json(latest_saved_evaluation)
    else:
        st.info("请先去「📈 学习进度反馈」提交一次进度。")


def render_adjustment(current_plan):
    page_header("动态调整", "结合进度、小测和日历，重排后面的任务。", icon="🔄")
    if not current_plan:
        st.info("请先生成计划。")
        return

    snap = service.get_schedule_snapshot(current_plan["id"])
    if snap and snap["needs_attention"]:
        with st.expander("ℹ️ 关于缺勤时如何调整", expanded=False):
            st.caption(
                "有日历缺勤/未达标时，即使没有进度记录也可尝试调整；若有进度，会把日历摘要一并交给优化。"
            )

    st.caption("点按钮后，会刷新后续每日任务（原逻辑不变）。")
    if st.button("⚡ 生成调整建议", type="primary", use_container_width=True):
        result = service.adjust_plan(current_plan["id"])
        if not result:
            st.warning("需要先至少一条进度记录（或满足日历缺勤时的合成条件）。")
        else:
            st.success("✨ 已更新计划")
            with st.expander("📊 调整说明（JSON）", expanded=False):
                st.json(result["adjustment"])
            st.markdown('<p class="hx-section-label">调整后日程</p>', unsafe_allow_html=True)
            ns = service.get_schedule_snapshot(result["updated_plan"]["id"])
            render_plan(result["updated_plan"], ns)


inject_styles()
current_plan = service.get_current_plan()
page = render_sidebar(service, current_plan)

if page != "学习计划生成":
    st.session_state.pop(GOAL_CLARIFY_CREATE, None)
if page != "当前学习计划":
    st.session_state.pop(GOAL_CLARIFY_RECREATE, None)

if page == "首页总览":
    render_home(current_plan)
elif page == "学习计划生成":
    render_create_plan()
elif page == "当前学习计划":
    render_current_plan(current_plan)
elif page == "学习进度反馈":
    render_progress(current_plan)
elif page == "学习检测":
    render_evaluation(current_plan)
elif page == "动态调整":
    render_adjustment(current_plan)
