from datetime import datetime

from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QComboBox, QMessageBox, QFormLayout, QLineEdit, QDialog,
    QDialogButtonBox, QDateEdit, QTabWidget, QGroupBox, QGridLayout,
    QHeaderView, QSplitter,
)

from app.database import DatabaseManager
from app.widgets.selection_utils import enable_clear_selection_on_blur


class TodoDialog(QDialog):
    """待办事项编辑对话框"""

    QUADRANTS = [
        ("q1", "重要紧急"),
        ("q2", "重要不紧急"),
        ("q3", "不重要紧急"),
        ("q4", "不重要不紧急"),
    ]

    def __init__(self, parent=None, todo: dict = None):
        super().__init__(parent)
        self.todo = todo
        self.db = DatabaseManager()
        self.setWindowTitle("编辑任务" if todo else "新增任务")
        self.setMinimumWidth(540)
        self._setup_ui()
        if todo:
            self._load_todo(todo)

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(14)

        self.title_edit = QLineEdit()
        self.title_edit.setMinimumWidth(280)
        self.title_edit.setPlaceholderText("任务内容")
        layout.addRow("标题:", self.title_edit)

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setMinimumWidth(220)
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDate(QDate.currentDate().addDays(1))
        layout.addRow("截止日期:", self.due_date_edit)

        self.quadrant_combo = QComboBox()
        self.quadrant_combo.setMinimumWidth(220)
        for value, label in self.QUADRANTS:
            self.quadrant_combo.addItem(label, value)
        layout.addRow("今日象限:", self.quadrant_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _load_todo(self, todo: dict):
        self.title_edit.setText(todo["title"])
        if todo["due_date"]:
            self.due_date_edit.setDate(QDate.fromString(todo["due_date"], "yyyy-MM-dd"))
        quadrant = todo.get("quadrant", "q2")
        index = self.quadrant_combo.findData(quadrant)
        if index >= 0:
            self.quadrant_combo.setCurrentIndex(index)

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "due_date": self.due_date_edit.date().toString("yyyy-MM-dd"),
            "quadrant": self.quadrant_combo.currentData(),
        }


class QuadrantDetailDialog(QDialog):
    """四象限任务大屏查看"""

    def __init__(self, parent, title: str, tasks: list[dict], stats: dict):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(900, 620)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        summary = QLabel(f"{title} · {len(tasks)} 个未完成任务")
        layout.addWidget(summary)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["任务", "截止日期", "番茄", "分钟"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            stat = stats.get(task["id"], {"count": 0, "minutes": 0})
            values = [
                task["title"],
                task.get("due_date", ""),
                str(stat["count"]),
                str(stat["minutes"]),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class TodoModule(QWidget):
    """待办事项模块——任务池、四象限今日任务与番茄钟"""

    QUADRANT_LABELS = {
        "q1": "重要紧急",
        "q2": "重要不紧急",
        "q3": "不重要紧急",
        "q4": "不重要不紧急",
    }
    FOCUS_SECONDS = 25 * 60
    BREAK_SECONDS = 5 * 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager()
        self.selected_today_task_id = None
        # Cached after _refresh_today(); used by the compact quadrant cards and
        # the full-screen detail dialog so both views show the same data.
        self._today_tasks_by_quadrant = {}
        self._today_stats = {}
        # Timer state is kept in the widget rather than the database. The DB
        # only receives a pomodoro_sessions row when a focus session ends.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick_timer)
        self.timer_seconds_left = self.FOCUS_SECONDS
        self.timer_total_seconds = self.FOCUS_SECONDS
        self.timer_started_at = None
        self.timer_task_id = None
        self.timer_mode = "focus"
        self.timer_running = False
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_pool_tab(), "任务池")
        self.tabs.addTab(self._build_today_tab(), "今日四象限")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.tabs)

    def _build_pool_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        action_bar = QHBoxLayout()
        action_bar.setSpacing(12)
        self.add_btn = QPushButton("➕ 新增任务")
        self.edit_btn = QPushButton("✏️ 编辑")
        self.delete_btn = QPushButton("🗑️ 删除")
        self.toggle_btn = QPushButton("✅ 完成/恢复")
        self.add_btn.setObjectName("primaryActionButton")
        for btn in (self.add_btn, self.edit_btn, self.delete_btn, self.toggle_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._add_todo)
        self.edit_btn.clicked.connect(self._edit_todo)
        self.delete_btn.clicked.connect(self._delete_todo)
        self.toggle_btn.clicked.connect(self._toggle_todo)
        action_bar.addWidget(self.add_btn)
        action_bar.addWidget(self.edit_btn)
        action_bar.addWidget(self.delete_btn)
        action_bar.addWidget(self.toggle_btn)
        action_bar.addStretch()
        layout.addLayout(action_bar)

        today_bar = QHBoxLayout()
        today_bar.setSpacing(12)
        self.today_quadrant_combo = QComboBox()
        self.today_quadrant_combo.setMinimumWidth(220)
        for value, label in self.QUADRANT_LABELS.items():
            self.today_quadrant_combo.addItem(label, value)
        self.mark_today_btn = QPushButton("加入今日")
        self.mark_today_btn.setMinimumWidth(128)
        self.mark_today_btn.clicked.connect(self._mark_selected_today)
        today_bar.addWidget(QLabel("今日象限:"))
        today_bar.addWidget(self.today_quadrant_combo)
        today_bar.addWidget(self.mark_today_btn)
        today_bar.addStretch()

        self.status_filter = QComboBox()
        self.status_filter.setMinimumWidth(160)
        self.status_filter.addItems(["全部", "进行中", "已完成"])
        self.status_filter.currentTextChanged.connect(self._refresh)
        today_bar.addWidget(QLabel("筛选:"))
        today_bar.addWidget(self.status_filter)
        layout.addLayout(today_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "标题", "截止日期", "状态", "今日象限", "今日日期", "创建时间"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5, 6):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnHidden(0, True)
        self.table.doubleClicked.connect(self._edit_todo)
        enable_clear_selection_on_blur(self.table)
        layout.addWidget(self.table)

        self.summary_label = QLabel("统计信息")
        layout.addWidget(self.summary_label)
        return tab

    def _build_today_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        self.today_label = QLabel()
        layout.addWidget(self.today_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        quadrant_panel = QWidget()
        # The left side is a dashboard overview. Each quadrant remains compact;
        # users open QuadrantDetailDialog when they need a full-width task list.
        grid = QGridLayout(quadrant_panel)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        self.quadrant_tables = {}
        positions = {"q1": (0, 0), "q2": (0, 1), "q3": (1, 0), "q4": (1, 1)}
        for quadrant, (row, col) in positions.items():
            group = QGroupBox(self.QUADRANT_LABELS[quadrant])
            group.setMinimumHeight(280)
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(8)
            open_btn = QPushButton("放大查看")
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.clicked.connect(lambda checked=False, q=quadrant: self._open_quadrant_detail(q))
            table = QTableWidget()
            table.setMinimumHeight(220)
            table.setColumnCount(3)
            table.setHorizontalHeaderLabels(["ID", "任务", "专注"])
            table.setColumnHidden(0, True)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            table.itemSelectionChanged.connect(lambda q=quadrant: self._on_today_selection_changed(q))
            table.doubleClicked.connect(lambda _, q=quadrant: self._open_quadrant_detail(q))
            enable_clear_selection_on_blur(table)
            self.quadrant_tables[quadrant] = table
            group_layout.addWidget(open_btn)
            group_layout.addWidget(table)
            grid.addWidget(group, row, col)

        timer_group = QGroupBox("番茄钟")
        timer_group.setMinimumWidth(320)
        timer_group.setMaximumWidth(420)
        timer_layout = QVBoxLayout(timer_group)
        timer_layout.setSpacing(12)
        self.selected_task_label = QLabel("未选择今日任务")
        self.selected_task_label.setWordWrap(True)
        self.timer_label = QLabel("25:00")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setObjectName("timerLabel")
        self.timer_state_label = QLabel("专注 25 分钟 / 休息 5 分钟")
        self.timer_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_layout.addWidget(self.selected_task_label)
        timer_layout.addWidget(self.timer_label)
        timer_layout.addWidget(self.timer_state_label)

        timer_buttons = QGridLayout()
        timer_buttons.setHorizontalSpacing(10)
        timer_buttons.setVerticalSpacing(10)
        self.start_btn = QPushButton("开始")
        self.pause_btn = QPushButton("暂停")
        self.stop_btn = QPushButton("结束")
        self.complete_task_btn = QPushButton("完成任务")
        for btn in (self.start_btn, self.pause_btn, self.stop_btn, self.complete_task_btn):
            btn.setMinimumHeight(40)
            btn.setMinimumWidth(82)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self._start_focus)
        self.pause_btn.clicked.connect(self._pause_resume)
        self.stop_btn.clicked.connect(self._stop_timer)
        self.complete_task_btn.clicked.connect(self._complete_selected_today_task)
        timer_buttons.addWidget(self.start_btn, 0, 0)
        timer_buttons.addWidget(self.pause_btn, 0, 1)
        timer_buttons.addWidget(self.stop_btn, 0, 2)
        # "完成任务" is a task action, not a timer control, so it gets its own
        # full-width row below the timer buttons.
        timer_buttons.addWidget(self.complete_task_btn, 1, 0, 1, 3)
        timer_layout.addLayout(timer_buttons)
        timer_layout.addStretch()

        splitter.addWidget(quadrant_panel)
        splitter.addWidget(timer_group)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([980, 360])
        layout.addWidget(splitter, 1)
        return tab

    def _filter_status(self) -> str:
        return {"全部": "all", "进行中": "pending", "已完成": "done"}.get(
            self.status_filter.currentText(), "all"
        )

    def _refresh(self, *_):
        self._refresh_pool()
        self._refresh_today()

    def _on_tab_changed(self, index: int):
        self._refresh()
        if index == 1:
            self._sync_selected_label()

    def _refresh_pool(self):
        todos = self.db.get_todos(self._filter_status())
        self.table.setRowCount(len(todos))
        today = QDate.currentDate()
        for row, todo in enumerate(todos):
            values = [
                str(todo["id"]),
                todo["title"],
                todo.get("due_date", ""),
                "完成" if todo["status"] == "done" else "进行中",
                self.QUADRANT_LABELS.get(todo.get("quadrant", "q2"), "重要不紧急"),
                todo.get("today_date", ""),
                todo["created_at"][:10] if todo["created_at"] else "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (2, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)
            if todo["status"] == "pending" and todo.get("due_date"):
                due = QDate.fromString(todo["due_date"], "yyyy-MM-dd")
                if due.isValid() and due < today:
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        if item:
                            item.setBackground(Qt.GlobalColor.darkRed)
                            item.setForeground(Qt.GlobalColor.white)

        all_todos = self.db.get_todos("all")
        done_count = sum(1 for todo in all_todos if todo["status"] == "done")
        pending_count = len(all_todos) - done_count
        self.summary_label.setText(f"总计: {len(all_todos)}  |  进行中: {pending_count}  |  已完成: {done_count}")

    def _refresh_today(self):
        today = QDate.currentDate().toString("yyyy-MM-dd")
        self.today_label.setText(f"今天：{today}  |  未完成任务会自动顺延到今天显示")
        todos = self.db.get_today_todos(today)
        stats = self.db.get_pomodoro_stats_for_tasks([todo["id"] for todo in todos], today)
        by_quadrant = {key: [] for key in self.QUADRANT_LABELS}
        for todo in todos:
            by_quadrant.get(todo.get("quadrant", "q2"), by_quadrant["q2"]).append(todo)
        self._today_tasks_by_quadrant = by_quadrant
        self._today_stats = stats

        for quadrant, table in self.quadrant_tables.items():
            table.blockSignals(True)
            items = by_quadrant[quadrant]
            table.setRowCount(len(items))
            for row, todo in enumerate(items):
                stat = stats.get(todo["id"], {"count": 0, "minutes": 0})
                # Compact cards show only the task name and a focus summary.
                # The full detail dialog contains due date, tomatoes, and
                # minutes without truncating the overview.
                values = [
                    str(todo["id"]),
                    todo["title"],
                    f"{stat['count']} / {stat['minutes']}m",
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col == 2:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setToolTip(todo["title"] if col == 1 else value)
                    table.setItem(row, col, item)
            table.blockSignals(False)

        if self.selected_today_task_id:
            selected = self.db.get_todo(self.selected_today_task_id)
            if (
                not selected
                or selected["status"] != "pending"
                or not selected.get("today_date", "")
                or selected.get("today_date", "") > today
            ):
                self.selected_today_task_id = None
        self._sync_selected_label()

    def _selected_pool_task_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def _selected_today_id_from_tables(self, preferred_quadrant: str = "") -> int | None:
        tables = []
        if preferred_quadrant:
            tables.append(self.quadrant_tables[preferred_quadrant])
        tables.extend(table for key, table in self.quadrant_tables.items() if key != preferred_quadrant)
        for table in tables:
            row = table.currentRow()
            if row >= 0:
                return int(table.item(row, 0).text())
        return None

    def _on_today_selection_changed(self, quadrant: str):
        table = self.quadrant_tables[quadrant]
        if table.currentRow() < 0:
            return
        # Only one quadrant selection is meaningful at a time because the
        # pomodoro timer binds to a single current task.
        for key, other in self.quadrant_tables.items():
            if key != quadrant:
                other.blockSignals(True)
                other.clearSelection()
                other.setCurrentCell(-1, -1)
                other.blockSignals(False)
        task_id = self._selected_today_id_from_tables(quadrant)
        if task_id:
            self.selected_today_task_id = task_id
            self._sync_selected_label()

    def _sync_selected_label(self):
        todo = self.db.get_todo(self.selected_today_task_id) if self.selected_today_task_id else None
        if todo and todo["status"] == "pending":
            self.selected_task_label.setText(f"当前任务：{todo['title']}")
        else:
            self.selected_task_label.setText("未选择今日任务")

    def _open_quadrant_detail(self, quadrant: str):
        # Refresh just before opening so the large view reflects edits made in
        # the task pool or by the timer moments earlier.
        self._refresh_today()
        dialog = QuadrantDetailDialog(
            self,
            self.QUADRANT_LABELS[quadrant],
            self._today_tasks_by_quadrant.get(quadrant, []),
            self._today_stats,
        )
        dialog.exec()

    def _add_todo(self):
        dialog = TodoDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["title"]:
                QMessageBox.warning(self, "提示", "任务标题不能为空")
                return
            self.db.add_todo(data["title"], "medium", data["due_date"], data["quadrant"], "")
            self._refresh()

    def _edit_todo(self):
        tid = self._selected_pool_task_id()
        if not tid:
            QMessageBox.information(self, "提示", "请先选择一个任务")
            return
        todo = self.db.get_todo(tid)
        if not todo:
            return
        dialog = TodoDialog(self, todo)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["title"]:
                QMessageBox.warning(self, "提示", "任务标题不能为空")
                return
            self.db.update_todo(
                tid,
                data["title"],
                todo.get("priority", "medium"),
                data["due_date"],
                todo["status"],
                data["quadrant"],
                todo.get("today_date", ""),
            )
            self._refresh()

    def _delete_todo(self):
        tid = self._selected_pool_task_id()
        if not tid:
            QMessageBox.information(self, "提示", "请先选择一个任务")
            return
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除这个任务吗？相关番茄钟记录会保留但不再绑定任务。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_todo(tid)
            if self.selected_today_task_id == tid:
                self.selected_today_task_id = None
            self._refresh()

    def _toggle_todo(self):
        tid = self._selected_pool_task_id()
        if not tid:
            QMessageBox.information(self, "提示", "请先选择一个任务")
            return
        self.db.toggle_todo(tid)
        self._refresh()

    def _mark_selected_today(self):
        tid = self._selected_pool_task_id()
        if not tid:
            QMessageBox.information(self, "提示", "请先在任务池选择一个任务")
            return
        self.db.mark_todo_today(
            tid,
            self.today_quadrant_combo.currentData(),
            QDate.currentDate().toString("yyyy-MM-dd"),
        )
        self.tabs.setCurrentIndex(1)
        self._refresh()

    def _complete_selected_today_task(self):
        task_id = self.selected_today_task_id or self._selected_today_id_from_tables()
        if not task_id:
            QMessageBox.information(self, "提示", "请先选择一个今日任务")
            return
        todo = self.db.get_todo(task_id)
        if todo and todo["status"] != "done":
            self.db.toggle_todo(task_id)
        self.selected_today_task_id = None
        self._refresh()

    def _start_focus(self):
        if self.timer_running:
            return
        if self.timer_mode == "break" and self.timer_seconds_left < self.BREAK_SECONDS:
            self.timer.start(1000)
            self.timer_running = True
            return
        task_id = self.selected_today_task_id or self._selected_today_id_from_tables()
        todo = self.db.get_todo(task_id) if task_id else None
        if not todo or todo["status"] != "pending":
            QMessageBox.information(self, "提示", "请先选择一个未完成的今日任务")
            return
        self.timer_mode = "focus"
        self.timer_task_id = task_id
        self.timer_started_at = datetime.now()
        self.timer_total_seconds = self.FOCUS_SECONDS
        self.timer_seconds_left = self.FOCUS_SECONDS
        self.timer_running = True
        self.timer.start(1000)
        self._update_timer_labels()

    def _pause_resume(self):
        if not self.timer_started_at and self.timer_mode == "focus":
            return
        if self.timer_running:
            self.timer.stop()
            self.timer_running = False
            self.pause_btn.setText("继续")
        else:
            self.timer.start(1000)
            self.timer_running = True
            self.pause_btn.setText("暂停")

    def _stop_timer(self):
        if not self.timer_started_at and self.timer_mode != "break":
            return
        self.timer.stop()
        if self.timer_mode == "focus" and self.timer_started_at:
            # Store partial sessions as stopped for audit/history, but they are
            # excluded from the completed pomodoro count in DatabaseManager.
            actual = max(0, round((self.timer_total_seconds - self.timer_seconds_left) / 60))
            self.db.add_pomodoro_session(
                self.timer_task_id,
                self.timer_started_at.isoformat(timespec="seconds"),
                datetime.now().isoformat(timespec="seconds"),
                25,
                actual,
                "stopped",
                "手动停止",
            )
        self._reset_timer()
        self._refresh()

    def _tick_timer(self):
        self.timer_seconds_left -= 1
        if self.timer_seconds_left <= 0:
            self.timer.stop()
            if self.timer_mode == "focus":
                self.db.add_pomodoro_session(
                    self.timer_task_id,
                    self.timer_started_at.isoformat(timespec="seconds"),
                    datetime.now().isoformat(timespec="seconds"),
                    25,
                    25,
                    "completed",
                )
                self.timer_mode = "break"
                self.timer_task_id = None
                self.timer_started_at = None
                self.timer_total_seconds = self.BREAK_SECONDS
                self.timer_seconds_left = self.BREAK_SECONDS
                self.timer_running = True
                self.timer.start(1000)
            else:
                self._reset_timer()
            self._refresh()
        self._update_timer_labels()

    def _reset_timer(self):
        self.timer.stop()
        self.timer_mode = "focus"
        self.timer_task_id = None
        self.timer_started_at = None
        self.timer_total_seconds = self.FOCUS_SECONDS
        self.timer_seconds_left = self.FOCUS_SECONDS
        self.timer_running = False
        self.pause_btn.setText("暂停")
        self._update_timer_labels()

    def _update_timer_labels(self):
        minutes = self.timer_seconds_left // 60
        seconds = self.timer_seconds_left % 60
        self.timer_label.setText(f"{minutes:02d}:{seconds:02d}")
        mode_text = "专注中" if self.timer_mode == "focus" else "休息中"
        state = "运行" if self.timer_running else "暂停"
        self.timer_state_label.setText(f"{mode_text} · {state}")
