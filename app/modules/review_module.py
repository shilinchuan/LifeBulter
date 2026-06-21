from pathlib import Path

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QSpinBox, QLabel, QTextEdit, QGroupBox,
    QSplitter, QMessageBox, QDialog, QDialogButtonBox, QFormLayout,
)

from app.database import DatabaseManager
from app.widgets.selection_utils import enable_clear_selection_on_blur
from app.services.week_service import (
    build_week_summary,
    current_year_week,
    render_week_review_markdown,
)


class WeekTaskPickerDialog(QDialog):
    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.db = db or DatabaseManager()
        self.setWindowTitle("从任务池加入本周")
        self.setMinimumSize(760, 520)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "任务", "象限", "截止日期"])
        self.table.setColumnHidden(0, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        enable_clear_selection_on_blur(self.table)
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh()

    def _refresh(self):
        todos = self.db.get_todos("pending")
        self.table.setRowCount(len(todos))
        for row, todo in enumerate(todos):
            values = [
                todo["id"],
                todo["title"],
                todo.get("quadrant", "q2"),
                todo.get("due_date", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col in (2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

    def selected_task_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None


class ReviewModule(QWidget):
    QUADRANT_LABELS = {
        "q1": "重要紧急",
        "q2": "重要不紧急",
        "q3": "不重要紧急",
        "q4": "不重要不紧急",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager()
        year, week = current_year_week()
        self._setup_ui(year, week)
        self._refresh()

    def _setup_ui(self, year: int, week: int):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(year)
        self.week_spin = QSpinBox()
        self.week_spin.setRange(1, 53)
        self.week_spin.setValue(week)
        self.year_spin.valueChanged.connect(self._refresh)
        self.week_spin.valueChanged.connect(self._refresh)
        top.addWidget(QLabel("ISO 年:"))
        top.addWidget(self.year_spin)
        top.addWidget(QLabel("周:"))
        top.addWidget(self.week_spin)
        top.addStretch()
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        action_bar = QHBoxLayout()
        self.add_week_btn = QPushButton("从任务池加入本周")
        self.remove_week_btn = QPushButton("移出本周")
        self.mark_today_btn = QPushButton("标记为今日")
        self.unmark_today_btn = QPushButton("取消今日")
        for btn in (self.add_week_btn, self.remove_week_btn, self.mark_today_btn, self.unmark_today_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_bar.addWidget(btn)
        action_bar.addStretch()
        left_layout.addLayout(action_bar)

        self.week_table = QTableWidget()
        self.week_table.setColumnCount(7)
        self.week_table.setHorizontalHeaderLabels(["ID", "任务", "象限", "状态", "今日日期", "完成度", "进展备注"])
        self.week_table.setColumnHidden(0, True)
        self.week_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.week_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.week_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.week_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5):
            self.week_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.week_table.itemSelectionChanged.connect(self._load_selected_progress)
        enable_clear_selection_on_blur(self.week_table)
        left_layout.addWidget(self.week_table, 1)

        progress = QFormLayout()
        self.completion_spin = QSpinBox()
        self.completion_spin.setRange(0, 100)
        self.progress_edit = QTextEdit()
        self.progress_edit.setFixedHeight(76)
        self.save_progress_btn = QPushButton("保存进展")
        self.save_progress_btn.clicked.connect(self._save_progress)
        progress.addRow("完成度:", self.completion_spin)
        progress.addRow("进展备注:", self.progress_edit)
        progress.addRow(self.save_progress_btn)
        left_layout.addLayout(progress)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        stats_group = QGroupBox("周报统计")
        stats_layout = QVBoxLayout(stats_group)
        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)
        right_layout.addWidget(stats_group)

        review_group = QGroupBox("三句复盘")
        review_layout = QFormLayout(review_group)
        self.proud_edit = QTextEdit()
        self.change_edit = QTextEdit()
        self.commit_edit = QTextEdit()
        for editor in (self.proud_edit, self.change_edit, self.commit_edit):
            editor.setFixedHeight(86)
        review_layout.addRow("本周做得好的:", self.proud_edit)
        review_layout.addRow("下周要改变的:", self.change_edit)
        review_layout.addRow("下周承诺:", self.commit_edit)
        right_layout.addWidget(review_group, 1)

        buttons = QGridLayout()
        self.generate_btn = QPushButton("生成周报")
        self.save_review_btn = QPushButton("保存复盘")
        self.export_btn = QPushButton("导出 Markdown")
        buttons.addWidget(self.generate_btn, 0, 0)
        buttons.addWidget(self.save_review_btn, 0, 1)
        buttons.addWidget(self.export_btn, 1, 0, 1, 2)
        right_layout.addLayout(buttons)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.add_week_btn.clicked.connect(self._add_from_pool)
        self.remove_week_btn.clicked.connect(self._remove_weekly_task)
        self.mark_today_btn.clicked.connect(self._mark_today)
        self.unmark_today_btn.clicked.connect(self._unmark_today)
        self.generate_btn.clicked.connect(self._generate_review)
        self.save_review_btn.clicked.connect(self._save_review)
        self.export_btn.clicked.connect(self._export_markdown)

    def _current_year_week(self) -> tuple[int, int]:
        return self.year_spin.value(), self.week_spin.value()

    def _selected_weekly_task_id(self) -> int | None:
        row = self.week_table.currentRow()
        if row < 0:
            return None
        item = self.week_table.item(row, 0)
        return int(item.text()) if item else None

    def _selected_weekly_task(self) -> dict | None:
        weekly_id = self._selected_weekly_task_id()
        if not weekly_id:
            return None
        year, week = self._current_year_week()
        return next((item for item in self.db.get_weekly_tasks(year, week) if item["id"] == weekly_id), None)

    def _refresh(self):
        year, week = self._current_year_week()
        tasks = self.db.get_weekly_tasks(year, week)
        self.week_table.setRowCount(len(tasks))
        for row, item in enumerate(tasks):
            values = [
                item["id"],
                item["title"],
                self.QUADRANT_LABELS.get(item.get("quadrant", "q2"), "重要不紧急"),
                "完成" if item.get("task_status") == "done" else "进行中",
                item.get("today_task_date", ""),
                f"{item.get('completion', 0)}%",
                item.get("progress_note", ""),
            ]
            for col, value in enumerate(values):
                table_item = QTableWidgetItem(str(value))
                if col in (2, 3, 4, 5):
                    table_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.week_table.setItem(row, col, table_item)
        review = self.db.get_weekly_review(year, week)
        if review:
            self.proud_edit.setPlainText(review.get("proud", ""))
            self.change_edit.setPlainText(review.get("change", ""))
            self.commit_edit.setPlainText(review.get("commit", ""))
        summary = build_week_summary(self.db, year, week)
        self.stats_label.setText(self._summary_text(summary))

    def _summary_text(self, summary: dict) -> str:
        return (
            f"本周任务：已完成 {summary['task_done']} / 总计 {summary['task_total']}，完成率 {summary['task_completion_rate']}%\n"
            f"专注时间：{summary['pomodoro_minutes']} 分钟\n"
            f"运动时间：{summary['exercise_minutes']} 分钟\n"
            f"收入：¥{summary['income']:.2f}  支出：¥{summary['expense']:.2f}  结余：¥{summary['balance']:.2f}\n"
            f"顺延任务：{summary['deferred_task_count']} 个"
        )

    def _load_selected_progress(self):
        item = self._selected_weekly_task()
        if not item:
            return
        self.completion_spin.setValue(int(item.get("completion") or 0))
        self.progress_edit.setPlainText(item.get("progress_note", ""))

    def _add_from_pool(self):
        dialog = WeekTaskPickerDialog(self, self.db)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            task_id = dialog.selected_task_id()
            if not task_id:
                QMessageBox.information(self, "提示", "请先选择一个任务")
                return
            year, week = self._current_year_week()
            before = len(self.db.get_weekly_tasks(year, week))
            self.db.add_weekly_task(task_id, year, week)
            after = len(self.db.get_weekly_tasks(year, week))
            if after == before:
                QMessageBox.information(self, "提示", "已在本周计划中")
            self._refresh()

    def _remove_weekly_task(self):
        weekly_id = self._selected_weekly_task_id()
        if not weekly_id:
            QMessageBox.information(self, "提示", "请先选择本周任务")
            return
        self.db.remove_weekly_task(weekly_id)
        self._refresh()

    def _mark_today(self):
        item = self._selected_weekly_task()
        if not item:
            QMessageBox.information(self, "提示", "请先选择本周任务")
            return
        today = QDate.currentDate().toString("yyyy-MM-dd")
        quadrant = item.get("quadrant") or "q2"
        self.db.mark_todo_today(item["task_id"], quadrant, today)
        self.db.update_weekly_task(item["id"], today_task_date=today)
        self._refresh()

    def _unmark_today(self):
        item = self._selected_weekly_task()
        if not item:
            QMessageBox.information(self, "提示", "请先选择本周任务")
            return
        self.db.update_weekly_task(item["id"], today_task_date="")
        self._refresh()

    def _save_progress(self):
        weekly_id = self._selected_weekly_task_id()
        if not weekly_id:
            QMessageBox.information(self, "提示", "请先选择本周任务")
            return
        self.db.update_weekly_task(
            weekly_id,
            completion=self.completion_spin.value(),
            progress_note=self.progress_edit.toPlainText().strip(),
        )
        self._refresh()

    def _review_data(self) -> dict:
        return {
            "proud": self.proud_edit.toPlainText().strip(),
            "change": self.change_edit.toPlainText().strip(),
            "commit": self.commit_edit.toPlainText().strip(),
        }

    def _generate_review(self):
        year, week = self._current_year_week()
        summary = build_week_summary(self.db, year, week)
        text = self._summary_text(summary)
        self.db.save_weekly_review(year, week, self.proud_edit.toPlainText().strip(), self.change_edit.toPlainText().strip(), self.commit_edit.toPlainText().strip(), text)
        QMessageBox.information(self, "提示", "周报已生成")
        self._refresh()

    def _save_review(self):
        year, week = self._current_year_week()
        summary = build_week_summary(self.db, year, week)
        data = self._review_data()
        self.db.save_weekly_review(year, week, data["proud"], data["change"], data["commit"], self._summary_text(summary))
        QMessageBox.information(self, "提示", "复盘已保存")
        self._refresh()

    def export_markdown(self, output_dir: str | Path = "outputs") -> Path:
        year, week = self._current_year_week()
        summary = build_week_summary(self.db, year, week)
        review = self.db.get_weekly_review(year, week) or self._review_data()
        path = Path(output_dir) / f"week-review-{year}-{week:02d}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_week_review_markdown(summary, review), encoding="utf-8")
        return path

    def _export_markdown(self):
        path = self.export_markdown()
        QMessageBox.information(self, "导出成功", f"已导出到：{path}")
