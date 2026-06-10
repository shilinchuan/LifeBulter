import os
import sqlite3
import tempfile
import unittest
from datetime import date


# Qt widgets can be constructed without opening real desktop windows. This
# keeps CI/local smoke tests fast and avoids interfering with the user's app.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QDate

from app.database import DatabaseManager, Singleton
from app.main_window import MainWindow
from app.modules.account_module import AccountModule, RecordDialog
from app.modules.todo_module import QuadrantDetailDialog
from app.widgets.chart_widget import ChartWidget


class LifeButlerSmokeTest(unittest.TestCase):
    def setUp(self):
        # Every test gets its own throwaway database. DatabaseManager is a
        # singleton, so the previous instance must be cleared before changing
        # LIFEBUTLER_DB_PATH.
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["LIFEBUTLER_DB_PATH"] = os.path.join(self.temp_dir.name, "lifebutler.db")
        Singleton._instances.pop(DatabaseManager, None)

    def tearDown(self):
        # Close and forget the singleton connection before deleting the temp
        # directory, otherwise SQLite can leave WAL/SHM files open on macOS.
        db = Singleton._instances.pop(DatabaseManager, None)
        if db:
            db.close()
        self.temp_dir.cleanup()

    def test_new_database_daily_task_and_pomodoro(self):
        # Brand-new installs should create the latest schema directly and be
        # able to use the two newest concepts: today tasks and pomodoro stats.
        db = DatabaseManager()
        today = date.today().isoformat()
        version = db.execute_query("SELECT value FROM schema_meta WHERE key='schema_version'")[0]["value"]
        self.assertEqual(version, "3")

        task_id = db.add_todo("写测试", "medium", "", "q1", today)
        db.add_pomodoro_session(task_id, f"{today}T09:00:00", f"{today}T09:25:00", 25, 25, "completed")

        self.assertEqual(len(db.get_today_todos(today)), 1)
        stats = db.get_pomodoro_stats_for_tasks([task_id], today)
        self.assertEqual(stats[task_id]["count"], 1)
        self.assertEqual(stats[task_id]["minutes"], 25)

    def test_old_database_migrates_without_losing_data(self):
        # This hand-built schema mimics the pre-migration app. The test guards
        # against future migration edits that accidentally drop old user data.
        path = os.environ["LIFEBUTLER_DB_PATH"]
        conn = sqlite3.connect(path)
        conn.executescript("""
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
                category TEXT NOT NULL UNIQUE,
                amount REAL NOT NULL CHECK(amount > 0),
                month TEXT NOT NULL
            );
            CREATE TABLE todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                priority TEXT NOT NULL CHECK(priority IN ('high','medium','low')),
                due_date TEXT,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','done')),
                created_at TEXT NOT NULL
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
            INSERT INTO todos (title,priority,due_date,status,created_at)
            VALUES ('旧任务','medium','2026-06-03','pending','2026-06-01T10:00:00');
        """)
        conn.commit()
        conn.close()

        db = DatabaseManager()
        # v2 task fields should be present after migration.
        columns = {row["name"] for row in db.execute_query("PRAGMA table_info(todos)")}
        self.assertIn("quadrant", columns)
        self.assertIn("today_date", columns)
        # Existing rows must survive the migration.
        self.assertEqual(db.get_todos()[0]["title"], "旧任务")
        # The old budgets table is migrated for compatibility, but the budget
        # feature is no longer exposed by the app.
        self.assertTrue(hasattr(db, "get_records"))

    def test_main_window_and_charts_construct(self):
        # This is a UI smoke test: build the main window and make sure theme
        # changes reach matplotlib charts, not just Qt widgets.
        app = QApplication.instance() or QApplication(["lifebutler-test"])
        window = MainWindow()
        self.assertEqual(window.stack.count(), 4)
        primary_buttons = [
            window.account_module.add_btn,
            window.todo_module.add_btn,
            window.health_module.add_weight_btn,
            window.health_module.add_exercise_btn,
            window.memo_module.add_btn,
        ]
        self.assertTrue(all(btn.objectName() == "primaryActionButton" for btn in primary_buttons))
        self.assertEqual(window.todo_module.add_btn.text(), "➕ 新增任务")
        self.assertEqual(window.health_module.edit_weight_btn.text(), "✏️ 编辑")
        self.assertEqual(window.health_module.delete_exercise_btn.text(), "🗑️ 删除")
        window._apply_theme(False)
        self.assertTrue(window.findChildren(ChartWidget))
        self.assertTrue(all(not chart.is_dark for chart in window.findChildren(ChartWidget)))
        window._apply_theme(True)
        self.assertTrue(all(chart.is_dark for chart in window.findChildren(ChartWidget)))
        # Standalone chart drawing should also work in both themes.
        chart = ChartWidget()
        chart.draw_pie_chart({"餐饮": 20, "交通": 10}, "支出分布")
        chart.draw_line_chart(["06-01", "06-02"], [70, 71], "体重变化趋势")
        chart.draw_bar_chart(["跑步"], [30], "本周运动分布")
        chart.set_theme(False)
        self.assertFalse(chart.is_dark)
        window.close()
        app.processEvents()

    def test_account_type_labels_and_chart_toggle(self):
        app = QApplication.instance() or QApplication(["lifebutler-test"])
        db = DatabaseManager()
        today = date.today().isoformat()
        db.add_record("expense", "餐饮", 20, today, "")
        db.add_record("income", "工资", 100, today, "")

        dialog = RecordDialog()
        self.assertEqual(dialog.type_combo.itemText(0), "支出")
        self.assertEqual(dialog.type_combo.itemData(0), "expense")
        self.assertEqual(dialog.type_combo.itemText(1), "收入")
        self.assertEqual(dialog.type_combo.itemData(1), "income")
        dialog.type_combo.setCurrentIndex(1)
        self.assertEqual(dialog.get_data()["type"], "income")

        edit_dialog = RecordDialog(record={
            "type": "income",
            "category": "工资",
            "amount": 100,
            "date": today,
            "note": "",
        })
        self.assertEqual(edit_dialog.type_combo.currentText(), "收入")
        self.assertEqual(edit_dialog.get_data()["type"], "income")

        module = AccountModule()
        self.assertEqual(module.current_chart_type, "expense")
        self.assertTrue(module.expense_chart_btn.isChecked())
        self.assertFalse(module.income_chart_btn.isChecked())
        module._show_income_chart()
        self.assertEqual(module.current_chart_type, "income")
        self.assertTrue(module.income_chart_btn.isChecked())
        self.assertFalse(module.expense_chart_btn.isChecked())
        module._show_expense_chart()
        self.assertEqual(module.current_chart_type, "expense")
        self.assertTrue(module.expense_chart_btn.isChecked())
        self.assertFalse(module.income_chart_btn.isChecked())
        module.close()
        app.processEvents()

    def test_todo_pool_and_quadrants_stay_in_sync(self):
        # The task pool and four-quadrant overview are two views of the same
        # todos table. This catches regressions where editing one view leaves
        # the other stale.
        app = QApplication.instance() or QApplication(["lifebutler-test"])
        window = MainWindow()
        module = window.todo_module
        today = QDate.currentDate().toString("yyyy-MM-dd")
        task_id = module.db.add_todo("同步测试", "medium", "", "q1", today)

        module._refresh()
        self.assertEqual(module.table.columnCount(), 7)
        self.assertEqual(module.quadrant_tables["q1"].rowCount(), 1)
        self.assertEqual(module.quadrant_tables["q2"].rowCount(), 0)
        # Compact quadrant cards intentionally show only task + focus summary;
        # full details live in QuadrantDetailDialog.
        self.assertEqual(module.quadrant_tables["q1"].columnCount(), 3)
        detail = QuadrantDetailDialog(
            module,
            module.QUADRANT_LABELS["q1"],
            module._today_tasks_by_quadrant["q1"],
            module._today_stats,
        )
        self.assertEqual(detail.table.rowCount(), 1)
        self.assertEqual(detail.table.columnCount(), 4)

        todo = module.db.get_todo(task_id)
        # Moving a task between quadrants should immediately move it in the
        # overview after refresh.
        module.db.update_todo(task_id, todo["title"], todo["priority"], todo["due_date"], todo["status"], "q2", today)
        module._refresh()
        self.assertEqual(module.quadrant_tables["q1"].rowCount(), 0)
        self.assertEqual(module.quadrant_tables["q2"].rowCount(), 1)

        module.selected_today_task_id = task_id
        # Completing a today task removes it from the current quadrant because
        # today views only show pending tasks.
        module._complete_selected_today_task()
        self.assertEqual(module.db.get_todo(task_id)["status"], "done")
        self.assertEqual(module.quadrant_tables["q2"].rowCount(), 0)
        window.close()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
