import json
from datetime import date

from agents.input_parser import InputParser
from agents.info_validator import InfoValidator
from agents.plan_validator import PlanValidator
from agents.evaluation_agent import EvaluationAgent
from agents.optimization_agent import OptimizationAgent
from agents.plan_agent import PlanAgent
from graph.workflows import build_adjust_workflow, build_plan_workflow
from rag.retriever import KnowledgeRetriever
from services.schedule import (
    current_plan_day_index,
    effective_plan_start,
    index_logs_by_study_date,
    max_plan_day_index,
    scan_missed_and_incomplete,
    tasks_for_plan_day,
)
from storage.db import init_db
from storage.repository import StudyRepository


def _progress_for_prompt(progress: dict) -> dict:
    """去掉仅用于系统内部的字段，避免塞进提示词过长或干扰模型。"""
    if not progress:
        return progress
    skip = {"calendar_synthetic"}
    return {k: v for k, v in progress.items() if k not in skip}


class StudyPlannerService:
    def __init__(self, api_key, user_id=1):
        init_db()
        self.user_id = user_id
        self.parser = InputParser(api_key)
        self.validator = InfoValidator(api_key)
        self.plan_validator = PlanValidator(strict_mode=False)
        self.planner = PlanAgent(api_key)
        self.evaluator = EvaluationAgent(api_key)
        self.optimizer = OptimizationAgent(api_key)
        self.repo = StudyRepository()
        self.retriever = KnowledgeRetriever()
        self._plan_workflow = build_plan_workflow(
            self.parser, self.planner, self.retriever
        )
        self._adjust_workflow = build_adjust_workflow(
            self.optimizer, self.retriever
        )

    def check_input_completeness(self, user_input: str):
        """
        检查用户输入的完整性。
        返回: {
            "completeness_score": int,
            "is_complete": bool,  # 是否信息充分
            "critical_missing": list,  # 关键缺失字段
            "optional_missing": list,  # 可选缺失字段
            "analysis": str,
            "followup_questions": list  # 如果不完整，包含后续问题
        }
        """
        completeness = self.validator.check_completeness(user_input)
        score = completeness.get("completeness_score", 50)
        critical = completeness.get("critical_missing", [])
        optional = completeness.get("optional_missing", [])
        
        result = {
            "completeness_score": score,
            "is_complete": score >= 85,
            "critical_missing": critical,
            "optional_missing": optional,
            "analysis": completeness.get("analysis", ""),
            "followup_questions": []
        }
        
        # 如果信息不充分，生成后续问题
        if not result["is_complete"]:
            all_missing = critical + optional
            questions = self.validator.generate_followup_questions(user_input, all_missing)
            result["followup_questions"] = questions
        
        return result

    def enrich_input_with_answers(self, 
                                   original_input: str, 
                                   followup_qa: list) -> tuple[str, dict]:
        """
        将多轮交互答案整合到原始输入，生成增强后的用户描述。
        followup_qa: [{"field": "...", "question": "...", "answer": "..."}, ...]
        返回: (增强后的用户描述, 完整的解析结果)
        """
        if not followup_qa or not any(qa.get("answer") for qa in followup_qa):
            # 没有有效的补充答案，使用原始输入
            return original_input, self.parser.parse(original_input)
        
        # 获取增强后的用户描述
        integrated_description = self.validator.integrate_followup_answer(
            original_input, 
            followup_qa
        )
        
        # 使用增强描述进行解析
        parsed_goal = self.parser.parse_enriched(integrated_description)
        
        return integrated_description, parsed_goal

    def create_plan_with_interaction(self, user_input: str, 
                                      followup_qa: list = None,
                                      plan_start_date=None):
        """
        支持多轮交互的计划生成。
        流程：检查完整性 → 如果需要，进行多轮交互 → 生成完整计划
        
        Args:
            user_input: 初始用户输入
            followup_qa: 可选的后续问答数组，用于多轮交互补全
            plan_start_date: 计划开始日期
            
        返回: {
            "completeness": {
                "score": int,
                "is_complete": bool,
                "questions_asked": list  # 向用户提出的问题
            },
            "enriched_input": str,  # 增强后的用户描述
            "plan": dict,  # 生成的计划
            "rag_context": str  # 检索到的知识库文本
        }
        """
        # 第一步：检查完整性
        completeness = self.check_input_completeness(user_input)
        
        # 第二步：如果信息不完整但已有后续答案，则补全
        enriched_input = user_input
        if followup_qa:
            enriched_input, _ = self.enrich_input_with_answers(user_input, followup_qa)
        
        # 第三步：用（可能增强的）输入生成计划
        workflow_out = self._plan_workflow.invoke(
            {"user_input": enriched_input.strip()}
        )
        parsed_goal = workflow_out.get("parsed_goal") or {}
        plan_data = workflow_out.get("plan_data") or {}
        
        if plan_start_date is None:
            start_str = date.today().isoformat()
        elif isinstance(plan_start_date, date):
            start_str = plan_start_date.isoformat()
        else:
            start_str = str(plan_start_date)[:10]
            
        plan_id = self.repo.create_study_plan(
            user_id=self.user_id,
            raw_input=user_input,
            parsed_goal=parsed_goal,
            plan_data=plan_data,
            plan_start_date=start_str,
        )
        plan = self.repo.get_plan_by_id(plan_id)
        rag_context = workflow_out.get("rag_context") or ""
        
        # 第四步：验证生成的计划是否合理
        validation_result = self.plan_validator.validate(parsed_goal, plan_data)
        
        return {
            "completeness": {
                "score": completeness["completeness_score"],
                "is_complete": completeness["is_complete"],
                "analysis": completeness["analysis"],
                "questions_asked": completeness.get("followup_questions", [])
            },
            "enriched_input": enriched_input,
            "plan": plan,
            "rag_context": rag_context,
            "validation": validation_result  # ← 新增验证结果
        }

    def create_plan(self, user_input, plan_start_date=None):
        """
        plan_start_date: date 或可解析的 ISO 字符串；表示「计划第 1 天」对应日历上的哪一天。
        """
        workflow_out = self._plan_workflow.invoke(
            {"user_input": (user_input or "").strip()}
        )
        parsed_goal = workflow_out.get("parsed_goal") or {}
        plan_data = workflow_out.get("plan_data") or {}
        if plan_start_date is None:
            start_str = date.today().isoformat()
        elif isinstance(plan_start_date, date):
            start_str = plan_start_date.isoformat()
        else:
            start_str = str(plan_start_date)[:10]
        plan_id = self.repo.create_study_plan(
            user_id=self.user_id,
            raw_input=user_input,
            parsed_goal=parsed_goal,
            plan_data=plan_data,
            plan_start_date=start_str,
        )
        plan = self.repo.get_plan_by_id(plan_id)
        rag_context = workflow_out.get("rag_context") or ""
        return plan, rag_context

    def get_schedule_snapshot(self, plan_id, today: date | None = None):
        """结合系统时钟与计划起始日，给出今日任务、缺勤与未达标日期（用于提醒与动态调整）。"""
        today = today or date.today()
        plan = self.repo.get_plan_by_id(plan_id)
        if not plan:
            return None

        start = effective_plan_start(plan, today)
        max_day = max_plan_day_index(plan["plan_data"])
        plan_day = current_plan_day_index(start, today)
        logs = self.repo.list_progress_logs(plan_id)
        by_date = index_logs_by_study_date(logs)
        missed, incomplete = scan_missed_and_incomplete(
            start, today, max_day, by_date, min_completion_ok=50.0
        )
        today_tasks = (
            tasks_for_plan_day(plan["plan_data"], plan_day) if plan_day >= 1 else []
        )
        return {
            "today_iso": today.isoformat(),
            "plan_start_date": start.isoformat(),
            "current_plan_day": plan_day,
            "max_plan_day": max_day,
            "today_tasks": today_tasks,
            "missed_days": missed,
            "incomplete_days": incomplete,
            "needs_attention": bool(missed or incomplete),
        }

    def get_current_plan(self):
        return self.repo.get_current_plan(self.user_id)

    def get_latest_evaluation(self, plan_id):
        return self.repo.get_latest_evaluation(plan_id)

    def analyze_progress(self, completion_ratio, delay_reason=""):
        ratio = float(completion_ratio)
        is_off_track = ratio < 70 or bool(delay_reason.strip())
        level = "正常"
        if ratio < 50:
            level = "严重偏离"
        elif ratio < 70:
            level = "轻度偏离"

        return {
            "is_off_track": is_off_track,
            "status_level": level,
            "message": "建议按节奏继续学习" if not is_off_track else "建议重新规划后续任务",
            "completion_ratio": ratio,
            "delay_reason": delay_reason,
        }

    def record_progress(self, plan_id, progress_data):
        feedback = self.analyze_progress(
            completion_ratio=progress_data.get("completion_ratio", 0),
            delay_reason=progress_data.get("delay_reason", ""),
        )
        log_id = self.repo.add_progress_log(plan_id, progress_data, feedback)
        latest = self.repo.get_latest_progress(plan_id)
        latest["id"] = log_id
        return latest

    def generate_evaluation(self, plan_id):
        plan = self.repo.get_plan_by_id(plan_id)
        progress = self.repo.get_latest_progress(plan_id)
        if not plan or not progress:
            return None

        snap = self.get_schedule_snapshot(plan_id)
        learning_topic = {
            "plan_summary": plan["plan_data"].get("summary", ""),
            "daily_tasks": plan["plan_data"].get("daily_tasks", []),
            "completed_tasks": progress.get("completed_tasks", ""),
            "pending_tasks": progress.get("pending_tasks", ""),
            "note": progress.get("note", ""),
            "study_date": progress.get("study_date", ""),
            "calendar_hint": snap,
        }
        rag_query = json.dumps(learning_topic, ensure_ascii=False)
        rag_context = self.retriever.retrieve(rag_query, top_k=4)
        evaluation = self.evaluator.evaluate(
            learning_topic, rag_context=rag_context or None
        )
        evaluation["progress_log_id"] = progress["id"]
        evaluation["rag_context"] = rag_context or ""
        return evaluation

    def save_evaluation_result(
        self,
        plan_id,
        score,
        total_questions,
        user_answers="",
        summary="",
        questions=None,
    ):
        latest_progress = self.repo.get_latest_progress(plan_id)
        if not latest_progress:
            return None

        generated = {"questions": questions or []}
        if not generated["questions"]:
            generated = self.generate_evaluation(plan_id)
        if not generated:
            return None

        result_level = self._score_to_level(score, total_questions)
        evaluation_data = {
            "questions": generated.get("questions", []),
            "score": score,
            "total_questions": total_questions,
            "result_level": result_level,
            "user_answers": user_answers,
            "summary": summary,
        }
        evaluation_id = self.repo.save_evaluation_result(
            plan_id=plan_id,
            progress_log_id=latest_progress["id"],
            evaluation_data=evaluation_data,
        )
        saved = self.repo.get_latest_evaluation(plan_id)
        saved["id"] = evaluation_id
        return saved

    def adjust_plan(self, plan_id):
        plan = self.repo.get_plan_by_id(plan_id)
        latest_progress = self.repo.get_latest_progress(plan_id)
        latest_evaluation = self.repo.get_latest_evaluation(plan_id)
        if not plan:
            return None

        snap = self.get_schedule_snapshot(plan_id)
        if not latest_progress and snap and snap["needs_attention"]:
            latest_progress = {
                "id": None,
                "plan_id": plan_id,
                "study_date": snap["today_iso"],
                "completion_ratio": 0.0,
                "completed_tasks": "",
                "pending_tasks": "",
                "note": json.dumps(
                    {
                        "missed_days": snap["missed_days"],
                        "incomplete_days": snap["incomplete_days"],
                    },
                    ensure_ascii=False,
                ),
                "delay_reason": "日历检测：存在未打卡或完成率低于50%的学习日",
                "is_off_track": True,
                "feedback": {
                    "is_off_track": True,
                    "status_level": "严重偏离",
                    "message": "系统根据日历判断学习进度未连续达标，请压缩或重排后续任务。",
                    "completion_ratio": 0.0,
                    "delay_reason": "日历缺勤或未达标",
                },
                "calendar_synthetic": True,
            }
        elif not latest_progress:
            return None

        learning_status = {
            "plan_summary": plan["plan_data"].get("summary", ""),
            "latest_progress": _progress_for_prompt(latest_progress),
            "latest_evaluation": latest_evaluation,
            "is_off_track": latest_progress.get("is_off_track", False),
            "calendar_context": snap,
        }
        adjust_query_parts = [
            str(plan["plan_data"].get("summary", "")),
            str(latest_progress.get("completed_tasks", "")),
            str(latest_progress.get("pending_tasks", "")),
            str(latest_progress.get("note", "")),
        ]
        if latest_evaluation:
            adjust_query_parts.append(
                json.dumps(
                    {
                        "score": latest_evaluation.get("score"),
                        "total_questions": latest_evaluation.get("total_questions"),
                        "result_level": latest_evaluation.get("result_level"),
                        "summary": latest_evaluation.get("summary"),
                    },
                    ensure_ascii=False,
                )
            )
        if snap:
            adjust_query_parts.append(
                "日历摘要："
                + json.dumps(
                    {
                        "today": snap["today_iso"],
                        "plan_start": snap["plan_start_date"],
                        "current_plan_day": snap["current_plan_day"],
                        "missed": snap["missed_days"],
                        "incomplete": snap["incomplete_days"],
                    },
                    ensure_ascii=False,
                )
            )
        adjust_query = "\n".join(adjust_query_parts)
        workflow_out = self._adjust_workflow.invoke(
            {
                "adjust_query": adjust_query,
                "learning_status": learning_status,
            }
        )
        adjustment = workflow_out.get("adjustment")
        if not adjustment:
            adjustment = self.optimizer.optimize(learning_status)

        updated_plan = dict(plan["plan_data"])
        if adjustment.get("updated_daily_tasks"):
            updated_plan["daily_tasks"] = adjustment["updated_daily_tasks"]
        if adjustment.get("analysis"):
            updated_plan["summary"] = f"{updated_plan.get('summary', '')}\n调整说明：{adjustment['analysis']}"

        log_id = latest_progress.get("id")
        self.repo.save_adjustment(plan_id, log_id, adjustment)
        self.repo.replace_active_plan(plan_id, updated_plan)
        return {
            "adjustment": adjustment,
            "updated_plan": self.repo.get_plan_by_id(plan_id),
        }

    def _score_to_level(self, score, total_questions):
        if not total_questions:
            return "未评估"
        ratio = float(score) / float(total_questions)
        if ratio >= 0.8:
            return "掌握较好"
        if ratio >= 0.6:
            return "基本掌握"
        return "需要加强"

