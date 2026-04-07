import os
import sqlite3
from contextlib import contextmanager


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "study_assistant.db")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


@contextmanager
def get_connection():
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS study_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                raw_input TEXT NOT NULL,
                parsed_goal_json TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                plan_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS progress_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                study_date TEXT NOT NULL,
                completion_ratio REAL NOT NULL,
                completed_tasks TEXT,
                pending_tasks TEXT,
                note TEXT,
                delay_reason TEXT,
                is_off_track INTEGER NOT NULL DEFAULT 0,
                feedback_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plan_id) REFERENCES study_plans(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                based_on_log_id INTEGER,
                adjusted_plan_json TEXT NOT NULL,
                adjusted_plan_text TEXT NOT NULL,
                suggestions_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plan_id) REFERENCES study_plans(id),
                FOREIGN KEY (based_on_log_id) REFERENCES progress_logs(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                progress_log_id INTEGER,
                questions_json TEXT NOT NULL,
                score REAL DEFAULT 0,
                total_questions INTEGER DEFAULT 0,
                result_level TEXT,
                user_answers TEXT,
                summary TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plan_id) REFERENCES study_plans(id),
                FOREIGN KEY (progress_log_id) REFERENCES progress_logs(id)
            )
            """
        )

        cursor.execute(
            """
            INSERT OR IGNORE INTO users (id, username)
            VALUES (1, 'default_user')
            """
        )

        cursor.execute("PRAGMA table_info(study_plans)")
        study_plan_cols = {row[1] for row in cursor.fetchall()}
        if "plan_start_date" not in study_plan_cols:
            cursor.execute(
                "ALTER TABLE study_plans ADD COLUMN plan_start_date TEXT"
            )
