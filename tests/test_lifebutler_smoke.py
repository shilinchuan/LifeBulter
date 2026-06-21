import os
import sqlite3
import tempfile
import unittest
from datetime import date
from unittest.mock import patch


# Qt widgets can be constructed without opening real desktop windows. This
# keeps CI/local smoke tests fast and avoids interfering with the user's app.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import QDate, QPoint, Qt
from PyQt6.QtTest import QTest

from app.database import DatabaseManager, Singleton
from app.main_window import MainWindow
from app.modules.account_module import AccountModule, RecordDialog
from app.modules.dashboard_module import DashboardModule
from app.modules.goal_module import GoalModule, KeyResultDialog, ObjectiveDialog, ProjectDialog
from app.modules.review_module import ReviewModule, WeekTaskPickerDialog
from app.modules.quick_capture_dialog import QuickCaptureDialog
from app.modules.settings_module import SettingsModule
from app.modules.todo_module import QuadrantDetailDialog, TodoDialog
from app.services.overview_service import build_life_radar, build_today_overview
from app.services.quick_capture_service import parse_quick_capture
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
        self.assertEqual(version, "5")

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
        self.assertNotIn("project_id", columns)
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
        self.assertEqual(window.stack.count(), 8)
        self.assertEqual(window.stack.currentIndex(), 0)
        self.assertIs(window.stack.widget(0), window.dashboard_module)
        primary_buttons = [
            window.dashboard_module.capture_btn,
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
        window.dashboard_module._refresh()
        self.assertGreaterEqual(window.dashboard_module.card_grid.count(), 4)
        # Standalone chart drawing should also work in both themes.
        chart = ChartWidget()
        chart.draw_pie_chart({"餐饮": 20, "交通": 10}, "支出分布")
        chart.draw_line_chart(["06-01", "06-02"], [70, 71], "体重变化趋势")
        chart.draw_bar_chart(["跑步"], [30], "本周运动分布")
        chart.set_theme(False)
        self.assertFalse(chart.is_dark)
        window.close()
        app.processEvents()

    def test_dashboard_module_and_overview_rules(self):
        app = QApplication.instance() or QApplication(["lifebutler-test"])
        db = DatabaseManager()
        today = date.today().isoformat()
        dashboard = DashboardModule()
        overview = build_today_overview(db, today)
        self.assertEqual(overview["today"], today)
        self.assertEqual(set(overview["quadrants"].keys()), {"q1", "q2", "q3", "q4"})
        self.assertIn("pomodoro", overview)
        self.assertIn("finance", overview)
        self.assertIn("health", overview)
        self.assertEqual(dashboard.today_empty_label.text(), "暂无今日任务")

        for idx in range(4):
            db.add_todo(f"紧急任务 {idx}", "medium", today, "q1", today)
        radar = build_life_radar(db, today)
        self.assertTrue(any(item["title"] == "任务过载" for item in radar))
        self.assertTrue(any(item["title"] == "健康缺口" for item in radar))
        dashboard._refresh()
        self.assertEqual(dashboard.today_table.rowCount(), 4)
        dashboard.close()
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

    def test_settings_module_and_backup(self):
        app = QApplication.instance() or QApplication(["lifebutler-test"])
        db = DatabaseManager()
        db.add_memo("备份测试", "内容", "general", "")
        settings = SettingsModule()
        self.assertIn("lifebutler.db", settings.path_edit.toPlainText())
        self.assertTrue(settings.path_edit.isReadOnly())
        self.assertGreater(settings.path_edit.maximumHeight(), 40)
        self.assertEqual(settings.schema_label.text(), "5")
        backup_path = db.backup_data()
        self.assertTrue(os.path.exists(backup_path))

        with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        self.assertIn("CLI JSON", readme)
        self.assertIn("测试命令", readme)
        self.assertIn("用户验收后", readme)
        settings.close()
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

        module.table.selectRow(0)
        with patch("app.modules.todo_module.TodoDialog.exec", return_value=QDialog.DialogCode.Rejected):
            module.table.doubleClicked.emit(module.table.model().index(0, 1))
        self.assertEqual(module.db.get_todo(task_id)["status"], "pending")

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

    def test_goal_module_and_project_ui(self):
        app = QApplication.instance() or QApplication(["lifebutler-test"])
        db = DatabaseManager()
        objective_id = db.add_objective("完成课程项目", "", "quarter", date.today().year, 1)
        db.add_key_result(objective_id, "完成初稿", "percentage", 40, 100, "%")
        project_id = db.add_project("数据库报告", "", objective_id)

        goal_module = GoalModule()
        self.assertFalse(hasattr(goal_module, "edit_objective_btn"))
        self.assertFalse(hasattr(goal_module, "refresh_btn"))
        self.assertNotEqual(goal_module.add_objective_btn.objectName(), "primaryActionButton")
        self.assertGreaterEqual(goal_module.objective_table.rowCount(), 1)
        goal_module.objective_table.selectRow(0)
        goal_module._refresh_detail()
        self.assertEqual(goal_module.kr_table.rowCount(), 1)
        self.assertEqual(goal_module.project_table.rowCount(), 1)
        self.assertEqual(goal_module.kr_table.columnCount(), 4)
        self.assertEqual(
            [goal_module.kr_table.horizontalHeaderItem(i).text() for i in range(goal_module.kr_table.columnCount())],
            ["标题", "数值", "进度", "状态"],
        )
        self.assertEqual(goal_module.project_table.columnCount(), 2)
        self.assertEqual(
            [goal_module.project_table.horizontalHeaderItem(i).text() for i in range(goal_module.project_table.columnCount())],
            ["标题", "状态"],
        )
        self.assertFalse(goal_module.kr_table.horizontalScrollBar().isVisible())
        self.assertFalse(goal_module.project_table.horizontalScrollBar().isVisible())
        goal_module.kr_table.selectRow(0)
        self.assertEqual(goal_module.objective_table.currentRow(), -1)
        QTest.mouseClick(goal_module.kr_table.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(goal_module.kr_table.viewport().width() - 2, goal_module.kr_table.viewport().height() - 2))
        app.processEvents()
        self.assertEqual(goal_module.kr_table.currentRow(), -1)

        goal_module.objective_table.selectRow(0)
        with patch("app.modules.goal_module._DetailDialog.exec", return_value=QDialog.DialogCode.Rejected):
            goal_module._open_objective_detail()
        goal_module.project_table.selectRow(0)
        with patch("app.modules.goal_module._DetailDialog.exec", return_value=QDialog.DialogCode.Rejected):
            goal_module._open_project_detail()

        no_project_dialog = TodoDialog()
        self.assertFalse(hasattr(no_project_dialog, "project_combo"))

        objective_dialog = ObjectiveDialog()
        kr_dialog = KeyResultDialog()
        standalone_project_dialog = ProjectDialog(db=db)
        self.assertEqual(objective_dialog.period_combo.findData("quarter") >= 0, True)
        self.assertEqual(kr_dialog.metric_combo.findData("percentage") >= 0, True)
        self.assertEqual(standalone_project_dialog.status_combo.findData("active") >= 0, True)
        goal_module.close()
        app.processEvents()

    def test_review_module_week_plan_and_export(self):
        app = QApplication.instance() or QApplication(["lifebutler-test"])
        db = DatabaseManager()
        today = date.today().isoformat()
        task_id = db.add_todo("周计划任务", "medium", today, "q2", "")
        year, week, _ = date.today().isocalendar()
        weekly_id = db.add_weekly_task(task_id, year, week)
        db.add_weekly_task(task_id, year, week)
        self.assertEqual(len(db.get_weekly_tasks(year, week)), 1)

        module = ReviewModule()
        self.assertFalse(hasattr(module, "refresh_btn"))
        self.assertGreaterEqual(module.week_table.rowCount(), 1)
        module.week_table.selectRow(0)
        module._mark_today()
        task = db.get_todo(task_id)
        weekly = db.get_weekly_tasks(year, week)[0]
        self.assertEqual(task["today_date"], today)
        self.assertEqual(weekly["today_task_date"], today)

        module.week_table.selectRow(0)
        module.completion_spin.setValue(60)
        module.progress_edit.setPlainText("推进到初稿")
        module._save_progress()
        weekly = db.get_weekly_tasks(year, week)[0]
        self.assertEqual(weekly["completion"], 60)
        self.assertEqual(weekly["progress_note"], "推进到初稿")

        module.proud_edit.setPlainText("完成了计划")
        module.change_edit.setPlainText("减少拖延")
        module.commit_edit.setPlainText("下周继续")
        db.save_weekly_review(year, week, "完成了计划", "减少拖延", "下周继续", "")
        path = module.export_markdown(self.temp_dir.name)
        self.assertTrue(path.exists())
        self.assertIn("LifeButler 周报", path.read_text(encoding="utf-8"))

        picker = WeekTaskPickerDialog(db=db)
        self.assertEqual(picker.table.columnCount(), 4)
        module.close()
        app.processEvents()

    def test_quick_capture_dialog_variants_construct(self):
        app = QApplication.instance() or QApplication(["lifebutler-test"])
        db = DatabaseManager()
        today = date.today().isoformat()
        samples = [
            ("午饭 28 元", "finance"),
            ("跑步 30 分钟", "exercise"),
            ("明天提交数据库报告", "task"),
            ("想到一个目标地图功能", "memo"),
        ]
        for text, kind in samples:
            dialog = QuickCaptureDialog(parsed=parse_quick_capture(text, today), db=db)
            self.assertEqual(dialog.get_kind(), kind)
            self.assertEqual(dialog.stack.currentIndex(), dialog.kind_combo.currentIndex())
            dialog.close()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
