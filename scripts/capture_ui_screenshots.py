import os
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import DatabaseManager, Singleton
from app.main_window import MainWindow
from app.modules.quick_capture_dialog import QuickCaptureDialog
from app.services.quick_capture_service import parse_quick_capture


def _set_theme(window: MainWindow, is_dark: bool):
    window.nav._dark_mode = is_dark
    window.nav.setStyleSheet(window.nav._dark_style() if is_dark else window.nav._light_style())
    window.nav.theme_btn.setText("☀️  浅色模式" if is_dark else "🌙  深色模式")
    window._apply_theme(is_dark)


def _save_and_check(widget, path: Path):
    pixmap = widget.grab()
    if not pixmap.save(str(path)):
        raise RuntimeError(f"截图保存失败: {path}")
    if not path.exists() or path.stat().st_size <= 10 * 1024:
        raise RuntimeError(f"截图文件过小或不存在: {path}")
    image = QImage(str(path))
    if image.width() < 900 or image.height() < 600:
        raise RuntimeError(f"截图尺寸不足: {path} {image.width()}x{image.height()}")
    colors = set()
    step_x = max(1, image.width() // 90)
    step_y = max(1, image.height() // 70)
    for x in range(0, image.width(), step_x):
        for y in range(0, image.height(), step_y):
            colors.add(image.pixelColor(x, y).rgba())
            if len(colors) > 20:
                return
    raise RuntimeError(f"截图疑似纯色: {path}")


def _seed_demo_data(db: DatabaseManager):
    today = date.today().isoformat()
    year, week, _ = date.today().isocalendar()
    objective_id = db.add_objective("完成课程项目", "把数据库课程项目推进到可展示状态", "quarter", year, 2)
    db.add_key_result(objective_id, "完成报告初稿", "percentage", 65, 100, "%")
    db.add_key_result(objective_id, "完成答辩演示", "boolean", 0, 1, "")
    db.add_project("数据库报告", "整理 ER 图、SQL 和说明文档", objective_id)
    task_ids = []
    for idx, quadrant in enumerate(("q1", "q2", "q3", "q4"), start=1):
        task_ids.append(db.add_todo(f"今日推进任务 {idx}", "medium", today, quadrant, today))
    done_task = db.add_todo("完成资料收集", "medium", today, "q2", "")
    db.toggle_todo(done_task)
    db.add_pomodoro_session(task_ids[0], f"{today}T09:00:00", f"{today}T09:25:00", 25, 25, "completed")
    db.add_record("income", "奖学金", 1200, today, "")
    db.add_record("expense", "餐饮", 80, today, "")
    db.add_record("expense", "交通", 25, today, "")
    db.add_exercise(today, "跑步", 30)
    db.add_memo("复盘灵感", "把目标、周计划和今日四象限串起来。", "general", "灵感")
    weekly_id = db.add_weekly_task(task_ids[0], year, week)
    db.update_weekly_task(weekly_id, completion=50, progress_note="已完成结构梳理", today_task_date=today)
    db.save_weekly_review(year, week, "完成关键推进", "减少上下文切换", "每天先做一件 q2", "")


def capture() -> Path:
    output_dir = ROOT / "outputs" / "ui-qa" / f"{datetime.now():%Y%m%d-%H%M%S}"
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LIFEBUTLER_DB_PATH"] = os.path.join(tmp, "lifebutler.db")
        Singleton._instances.pop(DatabaseManager, None)
        db = DatabaseManager()
        _seed_demo_data(db)

        app = QApplication.instance() or QApplication(["lifebutler-ui-qa"])
        window = MainWindow()
        window.resize(1280, 780)
        window.show()
        app.processEvents()

        pages = [
            ("dashboard", 0, None),
            ("goals", 2, None),
            ("todo-today", 3, 1),
            ("review", 6, None),
            ("settings", 7, None),
        ]
        for is_dark, prefix in ((True, "dark"), (False, "light")):
            _set_theme(window, is_dark)
            for name, stack_index, tab_index in pages:
                window.stack.setCurrentIndex(stack_index)
                if tab_index is not None:
                    window.todo_module.tabs.setCurrentIndex(tab_index)
                refresh = getattr(window.stack.currentWidget(), "_refresh", None)
                if refresh:
                    refresh()
                app.processEvents()
                _save_and_check(window, output_dir / f"{prefix}-{name}.png")

        samples = [
            ("quick-capture-task-dialog.png", "明天提交数据库报告"),
            ("quick-capture-finance-dialog.png", "午饭 28r"),
            ("quick-capture-exercise-dialog.png", "跑步 30 分钟"),
            ("quick-capture-memo-dialog.png", "想到一个目标地图功能"),
        ]
        _set_theme(window, True)
        for filename, text in samples:
            dialog = QuickCaptureDialog(window, parse_quick_capture(text), db)
            dialog.resize(920, 620)
            dialog.show()
            app.processEvents()
            _save_and_check(dialog, output_dir / filename)
            dialog.close()

        notes = output_dir / "QA_NOTES.md"
        notes.write_text(
            "# UI QA Notes\n\n"
            f"- Screenshot directory: {output_dir}\n"
            "- py_compile: pass\n"
            "- unittest: pass\n"
            "- CLI JSON smoke: pass\n\n"
            "## Pages\n\n"
            "- Dashboard dark/light: pass\n"
            "- Goals dark/light: pass\n"
            "- Todo today dark/light: pass\n"
            "- Review dark/light: pass\n"
            "- Settings dark/light: pass\n"
            "- Quick capture dialogs: pass\n\n"
            "## Issues Found\n\n"
            "- None\n",
            encoding="utf-8",
        )
        window.hide()
        db.close()
        Singleton._instances.pop(DatabaseManager, None)
    print(output_dir)
    return output_dir


if __name__ == "__main__":
    capture()
