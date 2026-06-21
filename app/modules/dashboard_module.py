from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGridLayout, QFrame, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QScrollArea, QDialog,
)

from app.database import DatabaseManager
from app.services.overview_service import build_today_overview
from app.services.quick_capture_service import commit_quick_capture, parse_quick_capture
from app.modules.quick_capture_dialog import QuickCaptureDialog
from app.widgets.selection_utils import enable_clear_selection_on_blur


class DashboardModule(QWidget):
    """首页驾驶舱：今日任务、专注、财务、健康与生活雷达。"""

    QUADRANT_LABELS = {
        "q1": "重要紧急",
        "q2": "重要不紧急",
        "q3": "不重要紧急",
        "q4": "不重要不紧急",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager()
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        capture_bar = QHBoxLayout()
        capture_bar.setSpacing(10)
        self.capture_edit = QLineEdit()
        self.capture_edit.setPlaceholderText("快速收集任务、账单、运动或备忘")
        self.capture_edit.returnPressed.connect(self._quick_capture)
        self.capture_btn = QPushButton("收集")
        self.capture_btn.setObjectName("primaryActionButton")
        self.capture_btn.clicked.connect(self._quick_capture)
        capture_bar.addWidget(self.capture_edit, 1)
        capture_bar.addWidget(self.capture_btn)
        layout.addLayout(capture_bar)

        self.card_grid = QGridLayout()
        self.card_grid.setHorizontalSpacing(12)
        self.card_grid.setVerticalSpacing(12)
        self.task_card = self._make_card("今日三件事", "0 件")
        self.focus_card = self._make_card("今日专注", "0 分钟")
        self.finance_card = self._make_card("本月财务", "¥0.00")
        self.health_card = self._make_card("近 7 天运动", "0 分钟")
        for index, card in enumerate((self.task_card, self.focus_card, self.finance_card, self.health_card)):
            self.card_grid.addWidget(card["frame"], index // 2, index % 2)
        layout.addLayout(self.card_grid)

        mid = QGridLayout()
        mid.setHorizontalSpacing(12)
        mid.setVerticalSpacing(12)
        self.quadrant_group = QGroupBox("四象限摘要")
        quadrant_layout = QGridLayout(self.quadrant_group)
        self.quadrant_labels = {}
        for index, key in enumerate(("q1", "q2", "q3", "q4")):
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumHeight(56)
            label.setObjectName("dashboardMetric")
            self.quadrant_labels[key] = label
            quadrant_layout.addWidget(label, index // 2, index % 2)
        mid.addWidget(self.quadrant_group, 0, 0)

        self.radar_group = QGroupBox("生活雷达")
        self.radar_layout = QVBoxLayout(self.radar_group)
        self.radar_layout.setSpacing(8)
        mid.addWidget(self.radar_group, 0, 1)
        mid.setColumnStretch(0, 1)
        mid.setColumnStretch(1, 1)
        layout.addLayout(mid)

        self.today_group = QGroupBox("今日任务简表")
        today_layout = QVBoxLayout(self.today_group)
        self.today_table = QTableWidget()
        self.today_table.setColumnCount(4)
        self.today_table.setHorizontalHeaderLabels(["任务", "象限", "截止日期", "今日日期"])
        self.today_table.setAlternatingRowColors(True)
        self.today_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.today_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.today_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            self.today_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        enable_clear_selection_on_blur(self.today_table)
        self.today_empty_label = QLabel("暂无今日任务")
        self.today_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        today_layout.addWidget(self.today_table)
        today_layout.addWidget(self.today_empty_label)
        layout.addWidget(self.today_group, 1)

        root.addWidget(scroll)

    def _make_card(self, title: str, value: str) -> dict:
        frame = QFrame()
        frame.setObjectName("overviewCard")
        frame.setMinimumHeight(92)
        card_layout = QVBoxLayout(frame)
        card_layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        value_label = QLabel(value)
        value_label.setObjectName("cardValue")
        value_label.setWordWrap(True)
        detail_label = QLabel("")
        detail_label.setWordWrap(True)
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        card_layout.addWidget(detail_label)
        return {"frame": frame, "value": value_label, "detail": detail_label}

    def _refresh(self):
        overview = build_today_overview(self.db)
        top_tasks = overview["top_tasks"]
        self.task_card["value"].setText(f"{len(top_tasks)} 件")
        self.task_card["detail"].setText("、".join(task["title"] for task in top_tasks) if top_tasks else "暂无今日任务")
        self.focus_card["value"].setText(f"{overview['pomodoro']['minutes']} 分钟")
        self.focus_card["detail"].setText(f"{overview['pomodoro']['count']} 个番茄")
        finance = overview["finance"]
        self.finance_card["value"].setText(f"¥{finance['balance']:.2f}")
        self.finance_card["detail"].setText(f"收入 ¥{finance['income']:.2f}  支出 ¥{finance['expense']:.2f}")
        self.health_card["value"].setText(f"{overview['health']['exercise_minutes_7d']} 分钟")
        self.health_card["detail"].setText("最近 7 天累计")

        for key, count in overview["quadrants"].items():
            self.quadrant_labels[key].setText(f"{self.QUADRANT_LABELS.get(key, key)}\n{count} 个")

        self._set_radar_items(overview["radar"])
        self._set_today_tasks(self.db.get_today_todos(overview["today"]))

    def _set_radar_items(self, radar: list[dict]):
        while self.radar_layout.count():
            item = self.radar_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not radar:
            empty = QLabel("暂无风险提醒")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.radar_layout.addWidget(empty)
            self.radar_layout.addStretch()
            return
        for alert in radar:
            label = QLabel(f"{alert['title']}：{alert['detail']}\n{alert['suggestion']}")
            label.setWordWrap(True)
            self.radar_layout.addWidget(label)
        self.radar_layout.addStretch()

    def _set_today_tasks(self, todos: list[dict]):
        self.today_table.setRowCount(len(todos))
        self.today_table.setVisible(bool(todos))
        self.today_empty_label.setVisible(not todos)
        for row, todo in enumerate(todos):
            values = [
                todo["title"],
                self.QUADRANT_LABELS.get(todo.get("quadrant", "q2"), "重要不紧急"),
                todo.get("due_date", ""),
                todo.get("today_date", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.today_table.setItem(row, col, item)

    def _quick_capture(self):
        text = self.capture_edit.text().strip()
        parsed = parse_quick_capture(text)
        if parsed["kind"] == "invalid":
            QMessageBox.information(self, "提示", "请输入要收集的内容")
            return
        dialog = QuickCaptureDialog(self, parsed, self.db)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        parsed = dict(parsed)
        parsed["kind"] = dialog.get_kind()
        try:
            commit_quick_capture(self.db, parsed, dialog.get_fields())
        except Exception as exc:
            QMessageBox.warning(self, "收集失败", str(exc))
            return
        self.capture_edit.clear()
        self._refresh()
