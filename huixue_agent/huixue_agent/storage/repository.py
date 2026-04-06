import json
from datetime import date

from storage.db import get_connection


class StudyRepository:
    def create_study_plan(self, user_id, raw_input, parsed_goal, plan_data, plan_start_date=None):
        with get_connection() as conn:
            cursor = conn.cursor()
            start = plan_start_date or str(date.today())
            cursor.execute(
                """
                INSERT INTO study_plans (
                    user_id, raw_input, parsed_goal_json, plan_json, plan_text, status,
                    plan_start_date
                ) VALUES (?, ?, ?, ?, ?, 'active', ?)
                """,
                (
                    user_id,
                    raw_input,
                    json.dumps(parsed_goal, ensure_ascii=False),
                    json.dumps(plan_data, ensure_ascii=False),
                    plan_data.get("summary", ""),
                    start,
                ),
            )
            return cursor.lastrowid

    def get_current_plan(self, user_id):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM study_plans
                WHERE user_id = ? AND status = 'active'
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_plan_dict(row)

    def get_plan_by_id(self, plan_id):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM study_plans WHERE id = ?", (plan_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_plan_dict(row)

    def add_progress_log(self, plan_id, progress_data, feedback):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO progress_logs (
                    plan_id, study_date, completion_ratio, completed_tasks, pending_tasks,
                    note, delay_reason, is_off_track, feedback_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    progress_data.get("study_date") or str(date.today()),
                    float(progress_data.get("completion_ratio", 0)),
                    progress_data.get("completed_tasks", ""),
                    progress_data.get("pending_tasks", ""),
                    progress_data.get("note", ""),
                    progress_data.get("delay_reason", ""),
                    1 if feedback.get("is_off_track") else 0,
                    json.dumps(feedback, ensure_ascii=False),
                ),
            )
            return cursor.lastrowid

    def get_latest_progress(self, plan_id):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM progress_logs
                WHERE plan_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (plan_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_progress_dict(row)

    def list_progress_logs(self, plan_id):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM progress_logs
                WHERE plan_id = ?
                ORDER BY study_date ASC, id ASC
                """,
                (plan_id,),
            )
            return [self._row_to_progress_dict(r) for r in cursor.fetchall()]

    def save_evaluation_result(self, plan_id, progress_log_id, evaluation_data):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO evaluation_results (
                    plan_id, progress_log_id, questions_json, score, total_questions,
                    result_level, user_answers, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    progress_log_id,
                    json.dumps(evaluation_data.get("questions", []), ensure_ascii=False),
                    float(evaluation_data.get("score", 0)),
                    int(evaluation_data.get("total_questions", 0)),
                    evaluation_data.get("result_level", ""),
                    evaluation_data.get("user_answers", ""),
                    evaluation_data.get("summary", ""),
                ),
            )
            return cursor.lastrowid

    def get_latest_evaluation(self, plan_id):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM evaluation_results
                WHERE plan_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (plan_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_evaluation_dict(row)

    def save_adjustment(self, plan_id, based_on_log_id, adjustment):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO plan_adjustments (
                    plan_id, based_on_log_id, adjusted_plan_json,
                    adjusted_plan_text, suggestions_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    based_on_log_id,
                    json.dumps(adjustment, ensure_ascii=False),
                    adjustment.get("analysis", ""),
                    json.dumps(adjustment.get("adjustments", []), ensure_ascii=False),
                ),
            )
            return cursor.lastrowid

    def replace_active_plan(self, plan_id, new_plan_data):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE study_plans
                SET plan_json = ?, plan_text = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(new_plan_data, ensure_ascii=False),
                    new_plan_data.get("summary", ""),
                    plan_id,
                ),
            )

    def _row_to_plan_dict(self, row):
        try:
            plan_start = row["plan_start_date"]
        except (KeyError, IndexError, TypeError):
            plan_start = None
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "raw_input": row["raw_input"],
            "parsed_goal": json.loads(row["parsed_goal_json"]),
            "plan_data": json.loads(row["plan_json"]),
            "plan_text": row["plan_text"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "plan_start_date": plan_start,
        }

    def _row_to_progress_dict(self, row):
        return {
            "id": row["id"],
            "plan_id": row["plan_id"],
            "study_date": row["study_date"],
            "completion_ratio": row["completion_ratio"],
            "completed_tasks": row["completed_tasks"],
            "pending_tasks": row["pending_tasks"],
            "note": row["note"],
            "delay_reason": row["delay_reason"],
            "is_off_track": bool(row["is_off_track"]),
            "feedback": json.loads(row["feedback_json"]),
            "created_at": row["created_at"],
        }

    def _row_to_evaluation_dict(self, row):
        return {
            "id": row["id"],
            "plan_id": row["plan_id"],
            "progress_log_id": row["progress_log_id"],
            "questions": json.loads(row["questions_json"]),
            "score": row["score"],
            "total_questions": row["total_questions"],
            "result_level": row["result_level"],
            "user_answers": row["user_answers"],
            "summary": row["summary"],
            "created_at": row["created_at"],
        }

