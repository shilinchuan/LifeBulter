import os
import sqlite3
import tempfile
import unittest
from datetime import date

from app.database import DatabaseManager, Singleton
from app.services.goal_service import (
    build_objective_detail,
    calculate_kr_progress,
)
from app.services.overview_service import build_today_overview
from app.services.quick_capture_service import commit_quick_capture, parse_quick_capture
from app.services.week_service import build_week_summary, current_year_week, render_week_review_markdown


class LifeButlerServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["LIFEBUTLER_DB_PATH"] = os.path.join(self.temp_dir.name, "lifebutler.db")
        Singleton._instances.pop(DatabaseManager, None)

    def tearDown(self):
        db = Singleton._instances.pop(DatabaseManager, None)
        if db:
            db.close()
        self.temp_dir.cleanup()

    def test_new_database_schema_version_is_v5(self):
        db = DatabaseManager()
        version = db.execute_query("SELECT value FROM schema_meta WHERE key='schema_version'")[0]["value"]
        self.assertEqual(version, "5")
        todo_columns = {row["name"] for row in db.execute_query("PRAGMA table_info(todos)")}
        self.assertNotIn("project_id", todo_columns)

    def test_v3_database_migrates_to_v5(self):
        path = os.environ["LIFEBUTLER_DB_PATH"]
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta (key,value) VALUES ('schema_version','3');
            CREATE TABLE records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('income','expense')),
                category TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                date TEXT NOT NULL,
                note TEXT DEFAULT ''
            );
            CREATE TABLE budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                month TEXT NOT NULL,
                UNIQUE(category, month)
            );
            CREATE TABLE todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                priority TEXT NOT NULL CHECK(priority IN ('high','medium','low')),
                due_date TEXT,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','done')),
                created_at TEXT NOT NULL,
                quadrant TEXT NOT NULL DEFAULT 'q2',
                today_date TEXT DEFAULT '',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE health_weight (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                weight REAL NOT NULL CHECK(weight > 0),
                height REAL NOT NULL CHECK(height > 0),
                bmi REAL NOT NULL
            );
            CREATE TABLE health_exercise (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                duration INTEGER NOT NULL CHECK(duration > 0)
            );
            CREATE TABLE memos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                category TEXT DEFAULT 'general',
                tags TEXT DEFAULT '',
                is_pinned INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE pomodoro_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                planned_minutes INTEGER NOT NULL CHECK(planned_minutes > 0),
                actual_minutes INTEGER NOT NULL CHECK(actual_minutes >= 0),
                status TEXT NOT NULL CHECK(status IN ('completed','stopped')),
                note TEXT DEFAULT ''
            );
            INSERT INTO records (type,category,amount,date,note)
            VALUES ('expense','餐饮',20,'2026-06-01','午餐');
            INSERT INTO todos (title,priority,due_date,status,created_at,quadrant,today_date,updated_at)
            VALUES ('旧 v3 任务','medium','','pending','2026-06-01T10:00:00','q2','','2026-06-01T10:00:00');
            INSERT INTO health_weight (date,weight,height,bmi)
            VALUES ('2026-06-01',70,175,22.9);
            INSERT INTO health_exercise (date,type,duration)
            VALUES ('2026-06-01','跑步',30);
            INSERT INTO memos (title,content,category,tags,is_pinned,created_at,updated_at)
            VALUES ('旧备忘','内容','general','',0,'2026-06-01T10:00:00','2026-06-01T10:00:00');
        """)
        conn.commit()
        conn.close()

        db = DatabaseManager()
        version = db.execute_query("SELECT value FROM schema_meta WHERE key='schema_version'")[0]["value"]
        self.assertEqual(version, "5")
        todo_columns = {row["name"] for row in db.execute_query("PRAGMA table_info(todos)")}
        self.assertNotIn("project_id", todo_columns)
        for table in ("objectives", "key_results", "projects", "weekly_tasks", "weekly_reviews"):
            self.assertTrue(db.execute_query("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)))
        self.assertEqual(db.get_todos()[0]["title"], "旧 v3 任务")
        self.assertEqual(len(db.get_records()), 1)
        self.assertEqual(len(db.get_weight_records()), 1)
        self.assertEqual(len(db.get_exercise_records()), 1)
        self.assertEqual(len(db.get_memos()), 1)

    def test_v4_database_drops_todo_project_id_in_v5(self):
        path = os.environ["LIFEBUTLER_DB_PATH"]
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO schema_meta (key,value) VALUES ('schema_version','4');
            CREATE TABLE todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                priority TEXT NOT NULL,
                due_date TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                quadrant TEXT NOT NULL DEFAULT 'q2',
                today_date TEXT DEFAULT '',
                project_id INTEGER,
                updated_at TEXT NOT NULL
            );
            INSERT INTO todos (title,priority,due_date,status,created_at,quadrant,today_date,project_id,updated_at)
            VALUES ('旧 v4 任务','medium','2026-06-10','pending','2026-06-01T10:00:00','q1','2026-06-02',42,'2026-06-03T10:00:00');
        """)
        conn.commit()
        conn.close()

        db = DatabaseManager()
        version = db.execute_query("SELECT value FROM schema_meta WHERE key='schema_version'")[0]["value"]
        self.assertEqual(version, "5")
        todo_columns = {row["name"] for row in db.execute_query("PRAGMA table_info(todos)")}
        self.assertNotIn("project_id", todo_columns)
        todo = db.get_todos()[0]
        self.assertEqual(todo["title"], "旧 v4 任务")
        self.assertEqual(todo["quadrant"], "q1")
        self.assertEqual(todo["today_date"], "2026-06-02")

    def test_goal_project_task_and_weekly_task_apis(self):
        db = DatabaseManager()
        objective_id = db.add_objective("学业推进", "数据库课程", "quarter", 2026, 2)
        kr_id = db.add_key_result(objective_id, "完成课程报告", "percentage", 30, 100, "%")
        project_id = db.add_project("数据库报告", "完成论文和演示", objective_id)
        task_id = db.add_todo("写 ER 图", "medium", "", "q2", "")

        self.assertEqual(db.get_objective(objective_id)["title"], "学业推进")
        self.assertEqual(db.get_key_results(objective_id)[0]["id"], kr_id)
        self.assertEqual(db.get_project(project_id)["title"], "数据库报告")
        self.assertEqual(db.get_todo(task_id)["title"], "写 ER 图")

        detail = build_objective_detail(db, objective_id)
        self.assertEqual(detail["objective"]["id"], objective_id)
        self.assertEqual(detail["krs"][0]["progress"], 30)
        self.assertNotIn("task_stats", detail["projects"][0])

        year, week = current_year_week()
        first_id = db.add_weekly_task(task_id, year, week)
        second_id = db.add_weekly_task(task_id, year, week)
        self.assertEqual(first_id, second_id)
        self.assertEqual(len(db.get_weekly_tasks(year, week)), 1)

    def test_services_handle_empty_database(self):
        db = DatabaseManager()
        year, week = current_year_week()
        overview = build_today_overview(db, date.today().isoformat())
        summary = build_week_summary(db, year, week)
        self.assertEqual(overview["top_tasks"], [])
        self.assertEqual(set(overview["quadrants"].keys()), {"q1", "q2", "q3", "q4"})
        self.assertEqual(summary["task_total"], 0)
        self.assertEqual(summary["task_completion_rate"], 0)
        markdown = render_week_review_markdown(
            summary,
            {"proud": "完成核心任务", "change": "减少切换", "commit": "每天推进"},
        )
        self.assertIn("# LifeButler 周报", markdown)
        self.assertIn("## 本周做得好的", markdown)
        self.assertIn("完成核心任务", markdown)

    def test_calculate_kr_progress_variants(self):
        self.assertEqual(calculate_kr_progress({"metric_type": "number", "current_value": 5, "target_value": 10}), 50)
        self.assertEqual(calculate_kr_progress({"metric_type": "number", "current_value": 15, "target_value": 10}), 100)
        self.assertEqual(calculate_kr_progress({"metric_type": "percentage", "current_value": 75, "target_value": 100}), 75)
        self.assertEqual(calculate_kr_progress({"metric_type": "boolean", "current_value": 1, "target_value": 1}), 100)
        self.assertEqual(calculate_kr_progress({"metric_type": "boolean", "current_value": 0, "target_value": 1}), 0)
        self.assertEqual(calculate_kr_progress({"metric_type": "number", "current_value": 1, "target_value": 0}), 0)

    def test_parse_quick_capture_examples(self):
        today = "2026-06-17"
        self.assertEqual(parse_quick_capture("午饭 28 元", today)["kind"], "finance")
        self.assertEqual(parse_quick_capture("午饭 28r", today)["kind"], "finance")
        self.assertEqual(parse_quick_capture("28R", today)["fields"]["amount"], 28.0)
        self.assertEqual(parse_quick_capture("28.5", today)["kind"], "finance")
        self.assertEqual(parse_quick_capture("跑步 30 分钟", today)["kind"], "exercise")
        task = parse_quick_capture("明天提交数据库报告", today)
        self.assertEqual(task["kind"], "task")
        self.assertEqual(task["fields"]["due_date"], "2026-06-18")
        self.assertEqual(parse_quick_capture("想到一个目标地图功能", today)["kind"], "memo")
        self.assertEqual(parse_quick_capture("", today)["kind"], "invalid")

    def test_commit_quick_capture_writes_all_kinds(self):
        db = DatabaseManager()
        today = date.today().isoformat()
        task = parse_quick_capture("今天提交数据库报告", today)
        task_result = commit_quick_capture(db, task, {"add_to_today": True})
        self.assertEqual(task_result["kind"], "task")
        self.assertEqual(len(db.get_today_todos(today)), 1)

        finance = commit_quick_capture(db, parse_quick_capture("午饭 28 元", today), {})
        self.assertEqual(finance["kind"], "finance")
        self.assertEqual(len(db.get_records()), 1)

        exercise = commit_quick_capture(db, parse_quick_capture("跑步 30 分钟", today), {})
        self.assertEqual(exercise["kind"], "exercise")
        self.assertEqual(len(db.get_exercise_records()), 1)

        memo = commit_quick_capture(db, parse_quick_capture("想到一个目标地图功能", today), {})
        self.assertEqual(memo["kind"], "memo")
        self.assertEqual(len(db.get_memos()), 1)

        with self.assertRaises(ValueError):
            commit_quick_capture(db, parse_quick_capture("", today), {})


if __name__ == "__main__":
    unittest.main()
