from __future__ import annotations

import json
import os
from datetime import date

import streamlit as st

from services.schedule import calendar_date_for_plan_day, parse_iso_date
from services.study_planner_service import StudyPlannerService


st.set_page_config(
    page_title="AI 学习助手",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-f2ea0277b95141aba33bd194d4dee28b")
service = StudyPlannerService(api_key=API_KEY)

if "latest_generated_evaluation" not in st.session_state:
    st.session_state.latest_generated_evaluation = None


def show_rag_snippets(title: str, content: str | None):
    """折叠展示本次 RAG 检索到的知识片段。"""
    with st.expander(title, expanded=False):
        text = (content or "").strip()
        if text:
            st.markdown(text)
        else:
            st.caption(
                "未检索到与当前上下文高度相关的片段。可在 `data/knowledge/` 下添加或补充 .md / .txt 后重试。"
            )


def inject_styles():
    st.markdown(
        """
        <style>
        .main {
            background: linear-gradient(180deg, #f5f7fb 0%, #eef2ff 100%);
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        .hero-card, .info-card {
            background: white;
            border-radius: 18px;
            padding: 1.25rem 1.4rem;
            border: 1px solid rgba(47, 84, 235, 0.10);
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
        }
        .hero-title {
            font-size: 2rem;
            font-weight: 700;
            color: #172554;
            margin-bottom: 0.5rem;
        }
        .hero-desc {
            color: #475569;
            line-height: 1.7;
        }
        .section-title {
            font-size: 1.2rem;
            font-weight: 700;
            color: #1e3a8a;
            margin-top: 0.4rem;
            margin-bottom: 0.8rem;
        }
        .metric-box {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 1rem;
        }
        .tag {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            margin-right: 0.45rem;
            margin-bottom: 0.45rem;
            border-radius: 999px;
            background: #dbeafe;
            color: #1d4ed8;
            font-size: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_plan(plan_record, schedule_snapshot=None):
    if not plan_record:
        st.info("暂无学习计划，请先生成。")
        return

    plan_data = plan_record["plan_data"]
    if schedule_snapshot:
        st.info(
            f"**日历对齐**：计划起始日 `{schedule_snapshot['plan_start_date']}` · "
            f"系统今日 `{schedule_snapshot['today_iso']}` · "
            f"对应计划 **第 {schedule_snapshot['current_plan_day']} 天** "
            f"（计划共 {schedule_snapshot['max_plan_day']} 个学习日任务）"
        )
    st.markdown('<div class="section-title">计划摘要</div>', unsafe_allow_html=True)
    st.write(plan_data.get("summary", "暂无摘要"))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown("**阶段安排**")
        stages = plan_data.get("stages", [])
        if stages:
            for stage in stages:
                st.write(
                    f"**{stage.get('name', '阶段')}**（{stage.get('days', '待定')}）"
                )
                focus_list = stage.get("focus", [])
                if focus_list:
                    st.write("重点：" + "、".join(focus_list))
        else:
            st.write("暂无阶段安排")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown("**里程碑**")
        milestones = plan_data.get("milestones", [])
        if milestones:
            for item in milestones:
                st.write(f"- {item}")
        else:
            st.write("暂无里程碑信息")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">每日任务</div>', unsafe_allow_html=True)
    daily_tasks = plan_data.get("daily_tasks", [])
    start_d = None
    if schedule_snapshot:
        start_d = parse_iso_date(schedule_snapshot.get("plan_start_date"))
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
            day_title = f"Day {day_n}"
            if cal_label:
                day_title += f" · 日历 {cal_label}"
            st.markdown(
                f"""
                <div class="info-card" style="margin-bottom: 0.8rem;">
                    <b>{day_title}</b><br>
                    {task.get('task', '')}<br>
                    <span style="color:#64748b;">预计时长：{task.get('estimated_hours', 0)} 小时</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("暂无每日任务信息。")


def render_sidebar(service, current_plan):
    st.sidebar.markdown("## 导航")
    page = st.sidebar.radio(
        "选择页面",
        ["首页总览", "学习计划生成", "当前学习计划", "学习进度反馈", "学习检测", "动态调整"],
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 时钟与日历")
    st.sidebar.metric("系统今日", date.today().isoformat())
    if current_plan:
        snap = service.get_schedule_snapshot(current_plan["id"])
        if snap:
            st.sidebar.metric("计划第几天", snap["current_plan_day"])
            if snap["needs_attention"]:
                st.sidebar.error("有缺勤或未达标日，请看首页提醒或去动态调整。")
            elif snap["today_tasks"]:
                st.sidebar.success("今日有安排的学习任务。")
            else:
                st.sidebar.caption("今日无对应日序任务（可能已超出计划天数或未开始）。")
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 当前状态")
    st.sidebar.write("学习计划：" + ("已生成" if current_plan else "未生成"))
    if current_plan:
        st.sidebar.caption(f"当前计划 ID：{current_plan['id']}")
    else:
        st.sidebar.caption("请先生成学习计划")
    st.sidebar.caption(f"知识库片段数：{service.retriever.chunk_count()}（RAG）")
    st.sidebar.caption("编排：LangGraph（计划生成 / 动态调整）")
    return page


def render_home(current_plan):
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">AI 学习助手</div>
            <div class="hero-desc">
                面向学习规划、学习执行与学习优化的智能学习辅助系统。
                系统通过学习目标解析、学习计划生成、学习进度反馈、学习检测与动态调整，
                帮助用户形成可执行、可跟踪、可优化的学习闭环。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="metric-box"><b>核心能力</b><br>学习计划生成</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-box"><b>核心能力</b><br>进度反馈与检测</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="metric-box"><b>核心能力</b><br>动态调整优化</div>', unsafe_allow_html=True)

    st.write("")
    if current_plan:
        st.success("当前已有学习计划，可以直接继续记录进度、提交检测和动态调整。")
        snap = service.get_schedule_snapshot(current_plan["id"])
        if snap and snap["needs_attention"]:
            st.warning(
                "**日历提醒**：在计划天数范围内，以下日期未打卡或当日完成率低于 50%。"
                " 建议补录进度或前往「动态调整」重新排期。"
            )
            if snap["missed_days"]:
                st.write("缺勤（无记录）：", snap["missed_days"])
            if snap["incomplete_days"]:
                st.write("未达标：", snap["incomplete_days"])
        if snap and snap["today_tasks"]:
            st.markdown("**今日（按日历）应对齐的任务**")
            for t in snap["today_tasks"]:
                st.write(
                    f"- Day {t.get('day')}：{t.get('task', '')} "
                    f"（约 {t.get('estimated_hours', 0)} 小时）"
                )
        render_plan(current_plan, snap)
    else:
        st.info("当前尚未生成学习计划。建议先进入“学习计划生成”页面创建你的学习路径。")


def render_create_plan():
    st.markdown('<div class="section-title">学习计划生成</div>', unsafe_allow_html=True)
    st.write("请输入你的学习目标。系统会检查信息完整性，如有缺口会进行多轮交互补全。")
    
    plan_start = st.date_input(
        "计划第 1 天对应的日期（日历锚点）",
        value=date.today(),
        help="从此日起，Day 1、Day 2… 会对应到真实日历。",
    )
    
    # 初始化多轮交互状态
    if "plan_stage" not in st.session_state:
        st.session_state.plan_stage = "input"
    if "plan_input" not in st.session_state:
        st.session_state.plan_input = ""
    if "plan_check_result" not in st.session_state:
        st.session_state.plan_check_result = None
    if "plan_answers" not in st.session_state:
        st.session_state.plan_answers = {}
    
    # Stage 1: 初始输入
    if st.session_state.plan_stage == "input":
        st.subheader("📝 第 1 步：描述你的学习目标")
        
        user_input = st.text_area(
            "学习目标",
            height=120,
            placeholder="例如：我想两周复习操作系统，每天3小时，重点是进程和内存",
            value=st.session_state.plan_input
        )
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        def on_check_click():
            if not user_input.strip():
                st.warning("请输入学习目标")
                return
            st.session_state.plan_input = user_input.strip()
            st.write("⏳ 分析中...")
            result = service.check_input_completeness(user_input.strip())
            st.session_state.plan_check_result = result
            if result["is_complete"]:
                st.session_state.plan_stage = "complete"
            else:
                st.session_state.plan_stage = "enrich"
        
        def on_skip_click():
            if not user_input.strip():
                st.warning("请输入学习目标")
                return
            st.session_state.plan_input = user_input.strip()
            st.session_state.plan_stage = "complete"
        
        with col1:
            st.button("✓ 检查完整性", on_click=on_check_click, use_container_width=True)
        with col2:
            st.button("⏭ 跳过检查", on_click=on_skip_click, use_container_width=True)
    
    # Stage 2: 多轮补全
    elif st.session_state.plan_stage == "enrich":
        if st.session_state.plan_check_result:
            check = st.session_state.plan_check_result
            
            st.subheader("💬 第 2 步：补全关键信息")
            st.write(f"**原始输入：** {st.session_state.plan_input}")
            st.write(f"**完整性评分：** {check['completeness_score']}/100")
            
            if check.get("critical_missing"):
                st.warning("🔴 关键缺失：" + "、".join(check["critical_missing"]))
            
            questions = check.get("followup_questions", [])
            if questions:
                st.write("请回答以下问题：")
                
                # 用容器来管理所有问题，避免频繁重新渲染
                for i, q in enumerate(questions):
                    qkey = q.get("field", f"q_{i}")
                    st.markdown(f"**Q{i+1}. {q.get('question', '')}**")
                    if q.get("hint"):
                        st.caption(f"💡 {q['hint']}")
                    answer = st.text_input(
                        "回答",
                        key=f"input_{qkey}",
                        label_visibility="collapsed"
                    )
                    st.session_state.plan_answers[qkey] = {
                        "question": q.get("question"),
                        "answer": answer
                    }
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("✓ 补全完成，生成计划", type="primary", use_container_width=True):
                        st.session_state.plan_stage = "complete"
                with col2:
                    if st.button("← 返回修改", use_container_width=True):
                        st.session_state.plan_stage = "input"
                        st.session_state.plan_check_result = None
                        st.session_state.plan_answers = {}
    
    # Stage 3: 生成计划
    elif st.session_state.plan_stage == "complete":
        st.subheader("🚀 正在生成个性化学习计划...")
        st.info("⏳ 后台处理中...（右上角可见运行符号）")
        
        # 转换答案格式
        followup_qa = []
        for qkey, data in st.session_state.plan_answers.items():
            if data.get("answer"):
                followup_qa.append({
                    "field": qkey,
                    "question": data.get("question"),
                    "answer": data.get("answer")
                })
        
        try:
            result = service.create_plan_with_interaction(
                user_input=st.session_state.plan_input,
                followup_qa=followup_qa if followup_qa else None,
                plan_start_date=plan_start
            )
            
            # 显示结果
            plan = result["plan"]
            if plan:
                st.success("✨ 计划已生成并保存!")
                
                # 显示多轮交互摘要
                if result["completeness"]["questions_asked"]:
                    with st.expander("📊 交互过程摘要"):
                        st.write(f"**完整性评分:** {result['completeness']['score']}/100")
                        st.write(f"**分析:** {result['completeness']['analysis']}")
                
                # 显示合理性检查结果
                validation = result.get("validation", {})
                if validation:
                    st.markdown("---")
                    st.markdown("### ✓ 计划合理性检查结果")
                    
                    # 显示摘要
                    summary = validation.get("summary", "")
                    if "✅" in summary:
                        st.success(summary)
                    elif "⚠️" in summary:
                        st.warning(summary)
                    else:
                        st.error(summary)
                    
                    # 显示详细问题
                    errors = validation.get("errors", [])
                    warnings = validation.get("warnings", [])
                    suggestions = validation.get("suggestions", [])
                    
                    if errors:
                        st.error("**发现的问题：**")
                        for err in errors:
                            st.write(f"• {err}")
                    
                    if warnings:
                        st.warning("**优化建议：**")
                        for warn in warnings:
                            st.write(f"• {warn}")
                    
                    if suggestions:
                        st.info("**改进方案：**")
                        for sug in suggestions:
                            st.write(f"• {sug}")
                    
                    st.markdown("---")
                
                # 显示RAG内容
                show_rag_snippets("📚 RAG检索片段", result["rag_context"])
                
                # 显示计划
                snap = service.get_schedule_snapshot(plan["id"])
                render_plan(plan, snap)
                
                # 重置状态
                st.session_state.plan_stage = "input"
                st.session_state.plan_input = ""
                st.session_state.plan_check_result = None
                st.session_state.plan_answers = {}
            else:
                st.error("❌ 计划生成失败，请检查网络后重试")
                
        except Exception as e:
            st.error(f"❌ 出错: {str(e)}")
            st.session_state.plan_stage = "input"


def render_current_plan(current_plan):
    st.markdown('<div class="section-title">当前学习计划</div>', unsafe_allow_html=True)
    if not current_plan:
        st.info("当前没有可展示的学习计划，请先生成。")
        return
    snap = service.get_schedule_snapshot(current_plan["id"])
    render_plan(current_plan, snap)
    with st.expander("重新制定学习计划"):
        existing_start = parse_iso_date(current_plan.get("plan_start_date")) or date.today()
        plan_start = st.date_input("新计划第 1 天日期", value=existing_start)
        user_input = st.text_area(
            "请输入新的学习目标",
            height=120,
            placeholder="例如：我想一周复习数据结构，每天2小时，重点是树和图",
        )
        if st.button("重新生成计划", use_container_width=True):
            if not user_input.strip():
                st.warning("请输入新的学习目标。")
            else:
                with st.spinner("正在生成新的学习计划..."):
                    plan, plan_rag = service.create_plan(
                        user_input.strip(), plan_start_date=plan_start
                    )
                if plan:
                    st.success("新的学习计划已生成并保存。")
                    show_rag_snippets("本次检索到的知识片段（RAG · 用于生成计划）", plan_rag)
                    ns = service.get_schedule_snapshot(plan["id"])
                    render_plan(plan, ns)
                else:
                    st.error("新的学习计划生成失败，请稍后重试。")


def render_progress(current_plan):
    st.markdown('<div class="section-title">学习进度反馈</div>', unsafe_allow_html=True)
    if not current_plan:
        st.info("请先生成学习计划后再记录进度。")
        return

    snap = service.get_schedule_snapshot(current_plan["id"])
    if snap:
        st.caption(
            f"系统日期：**{snap['today_iso']}** · 计划起始 **{snap['plan_start_date']}** · "
            f"今日为计划 **第 {snap['current_plan_day']} 天**"
        )
        if snap["today_tasks"]:
            st.markdown("**本日应对齐的任务（来自计划 Day 序号）**")
            for t in snap["today_tasks"]:
                st.write(
                    f"- Day {t.get('day')}：{t.get('task', '')} "
                    f"（约 {t.get('estimated_hours', 0)} 小时）"
                )
        if snap["needs_attention"]:
            st.warning(
                "检测到历史缺勤或某日完成率不足 50%，补录时可选择对应日期，或前往「动态调整」。"
            )

    col1, col2 = st.columns([1.1, 1])
    with col1:
        record_date = st.date_input(
            "本条进度对应的日期",
            value=date.today(),
            help="用于按自然日对齐每日计划；补录昨天请改选昨天日期。",
        )
        completion_ratio = st.slider("当日任务完成率(%)", 0, 100, 60)
        completed_tasks = st.text_area("已完成任务", placeholder="例如：完成了进程调度算法复习")
        pending_tasks = st.text_area("未完成任务", placeholder="例如：虚拟内存章节尚未完成")
    with col2:
        delay_reason = st.text_input("偏差原因（可选）", placeholder="例如：临时有其他课程任务")
        note = st.text_area("学习备注（可选）", height=176, placeholder="例如：对页面置换算法理解还不够")

    if st.button("提交进度并生成反馈", type="primary", use_container_width=True):
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
            st.success("学习进度已记录。")
            st.json(latest["feedback"])
            if generated_evaluation:
                show_rag_snippets(
                    "本次检索到的知识片段（RAG · 用于生成检测题）",
                    generated_evaluation.get("rag_context"),
                )
                st.info("系统已根据本次学习情况生成检测题，可前往“学习检测”页面查看。")
        else:
            st.error("学习进度记录失败，请稍后重试。")


def render_evaluation(current_plan):
    st.markdown('<div class="section-title">学习检测</div>', unsafe_allow_html=True)
    if not current_plan:
        st.info("请先生成学习计划。")
        return

    latest_generated_evaluation = st.session_state.latest_generated_evaluation
    latest_saved_evaluation = service.get_latest_evaluation(current_plan["id"])

    if latest_generated_evaluation:
        st.caption(latest_generated_evaluation.get("focus_summary", ""))
        show_rag_snippets(
            "本次检索到的知识片段（RAG · 用于生成检测题）",
            latest_generated_evaluation.get("rag_context"),
        )
        for question in latest_generated_evaluation.get("questions", []):
            st.markdown(
                f"""
                <div class="info-card" style="margin-bottom: 0.8rem;">
                    <b>{question.get('id', '-')} · {question.get('type', '检测题')}</b><br>
                    {question.get('question', '')}<br>
                    <span style="color:#64748b;">考察点：{question.get('check_point', '')}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        total_questions = len(latest_generated_evaluation.get("questions", []))
        score = st.number_input(
            "本次检测答对题数",
            min_value=0,
            max_value=max(total_questions, 1),
            value=0,
            step=1,
        )
        user_answers = st.text_area("答题简述（可选）", placeholder="简要填写你的回答或思路")
        evaluation_summary = st.text_area("自我总结（可选）", placeholder="例如：基础概念掌握较好，但应用分析能力不足")

        if st.button("提交检测结果", type="primary", use_container_width=True):
            saved_evaluation = service.save_evaluation_result(
                current_plan["id"],
                score=score,
                total_questions=total_questions,
                user_answers=user_answers,
                summary=evaluation_summary,
                questions=latest_generated_evaluation.get("questions", []),
            )
            if saved_evaluation:
                st.success("检测结果已保存。")
                st.json(saved_evaluation)
    elif latest_saved_evaluation:
        st.success("已存在最近一次检测结果。")
        st.json(latest_saved_evaluation)
    else:
        st.info("请先在“学习进度反馈”页面提交一次学习进度，以生成检测题。")


def render_adjustment(current_plan):
    st.markdown('<div class="section-title">动态调整</div>', unsafe_allow_html=True)
    if not current_plan:
        st.info("请先生成学习计划。")
        return

    snap = service.get_schedule_snapshot(current_plan["id"])
    if snap and snap["needs_attention"]:
        st.info(
            "当前存在日历层面的缺勤或未达标日，可在**从未提交过进度**时直接生成调整；"
            "若已有进度记录，将把日历摘要一并交给优化智能体。"
        )

    st.write("系统将结合最近一次学习进度、检测结果与**日历缺勤摘要**，对后续学习任务进行重新规划。")
    if st.button("生成调整建议", type="primary", use_container_width=True):
        result = service.adjust_plan(current_plan["id"])
        if not result:
            st.warning("暂无可用于调整的数据，请先提交至少一条进度记录。")
        else:
            st.success("计划调整完成。")
            st.markdown("**调整建议**")
            st.json(result["adjustment"])
            st.markdown("**调整后计划**")
            ns = service.get_schedule_snapshot(result["updated_plan"]["id"])
            render_plan(result["updated_plan"], ns)


inject_styles()
current_plan = service.get_current_plan()
page = render_sidebar(service, current_plan)

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