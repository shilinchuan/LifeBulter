from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QGroupBox, QFormLayout, QLineEdit, QTextEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QDialog, QDialogButtonBox,
    QMessageBox, QLabel,
)

from app.database import DatabaseManager
from app.services.goal_service import build_objective_detail, calculate_kr_progress
from app.widgets.selection_utils import enable_clear_selection_on_blur


class ObjectiveDialog(QDialog):
    PERIODS = [("month", "月度"), ("quarter", "季度"), ("year", "年度")]
    STATUSES = [("active", "进行中"), ("archived", "已归档"), ("abandoned", "已放弃")]

    def __init__(self, parent=None, objective: dict | None = None):
        super().__init__(parent)
        self.objective = objective
        self.setWindowTitle("编辑目标" if objective else "新增目标")
        self.setMinimumWidth(520)
        layout = QFormLayout(self)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(12)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("目标标题")
        layout.addRow("标题:", self.title_edit)

        self.description_edit = QTextEdit()
        self.description_edit.setFixedHeight(90)
        layout.addRow("描述:", self.description_edit)

        self.period_combo = QComboBox()
        for value, label in self.PERIODS:
            self.period_combo.addItem(label, value)
        layout.addRow("周期:", self.period_combo)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(date.today().year)
        layout.addRow("年份:", self.year_spin)

        self.status_combo = QComboBox()
        for value, label in self.STATUSES:
            self.status_combo.addItem(label, value)
        layout.addRow("状态:", self.status_combo)

        self.weight_spin = QSpinBox()
        self.weight_spin.setRange(1, 10)
        self.weight_spin.setValue(1)
        layout.addRow("权重:", self.weight_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        if objective:
            self.title_edit.setText(objective["title"])
            self.description_edit.setPlainText(objective.get("description", ""))
            self.period_combo.setCurrentIndex(max(0, self.period_combo.findData(objective.get("period"))))
            self.year_spin.setValue(objective.get("year", date.today().year))
            self.status_combo.setCurrentIndex(max(0, self.status_combo.findData(objective.get("status"))))
            self.weight_spin.setValue(objective.get("weight", 1))

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "period": self.period_combo.currentData(),
            "year": self.year_spin.value(),
            "status": self.status_combo.currentData(),
            "weight": self.weight_spin.value(),
        }


class KeyResultDialog(QDialog):
    TYPES = [("number", "数字"), ("percentage", "百分比"), ("boolean", "是否完成")]
    STATUSES = [("active", "进行中"), ("archived", "已归档"), ("abandoned", "已放弃")]

    def __init__(self, parent=None, kr: dict | None = None):
        super().__init__(parent)
        self.kr = kr
        self.setWindowTitle("编辑 KR" if kr else "新增 KR")
        self.setMinimumWidth(500)
        layout = QFormLayout(self)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(12)

        self.title_edit = QLineEdit()
        layout.addRow("标题:", self.title_edit)

        self.metric_combo = QComboBox()
        for value, label in self.TYPES:
            self.metric_combo.addItem(label, value)
        self.metric_combo.currentIndexChanged.connect(self._sync_defaults)
        layout.addRow("类型:", self.metric_combo)

        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(0, 1_000_000)
        self.current_spin.setDecimals(2)
        layout.addRow("当前值:", self.current_spin)

        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(0, 1_000_000)
        self.target_spin.setDecimals(2)
        self.target_spin.setValue(100)
        layout.addRow("目标值:", self.target_spin)

        self.unit_edit = QLineEdit()
        layout.addRow("单位:", self.unit_edit)

        self.status_combo = QComboBox()
        for value, label in self.STATUSES:
            self.status_combo.addItem(label, value)
        layout.addRow("状态:", self.status_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        if kr:
            self.title_edit.setText(kr["title"])
            self.metric_combo.setCurrentIndex(max(0, self.metric_combo.findData(kr.get("metric_type"))))
            self.current_spin.setValue(float(kr.get("current_value") or 0))
            self.target_spin.setValue(float(kr.get("target_value") or 0))
            self.unit_edit.setText(kr.get("unit", ""))
            self.status_combo.setCurrentIndex(max(0, self.status_combo.findData(kr.get("status"))))
        else:
            self._sync_defaults()

    def _sync_defaults(self):
        metric_type = self.metric_combo.currentData()
        if metric_type == "percentage":
            self.target_spin.setValue(100)
            self.unit_edit.setText("%")
        elif metric_type == "boolean":
            self.target_spin.setValue(1)
            self.unit_edit.clear()

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "metric_type": self.metric_combo.currentData(),
            "current_value": self.current_spin.value(),
            "target_value": self.target_spin.value(),
            "unit": self.unit_edit.text().strip(),
            "status": self.status_combo.currentData(),
        }


class ProjectDialog(QDialog):
    STATUSES = [("planning", "规划中"), ("active", "进行中"), ("paused", "暂停"), ("completed", "已完成")]

    def __init__(self, parent=None, db=None, project: dict | None = None, objective_id: int | None = None):
        super().__init__(parent)
        self.db = db or DatabaseManager()
        self.project = project
        self.setWindowTitle("编辑项目" if project else "新增项目")
        self.setMinimumWidth(520)
        layout = QFormLayout(self)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(12)

        self.title_edit = QLineEdit()
        layout.addRow("标题:", self.title_edit)

        self.description_edit = QTextEdit()
        self.description_edit.setFixedHeight(90)
        layout.addRow("描述:", self.description_edit)

        self.objective_combo = QComboBox()
        self.objective_combo.addItem("无目标", None)
        for objective in self.db.get_objectives("all"):
            self.objective_combo.addItem(objective["title"], objective["id"])
        layout.addRow("目标:", self.objective_combo)

        self.status_combo = QComboBox()
        for value, label in self.STATUSES:
            self.status_combo.addItem(label, value)
        layout.addRow("状态:", self.status_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        if project:
            self.title_edit.setText(project["title"])
            self.description_edit.setPlainText(project.get("description", ""))
            self.objective_combo.setCurrentIndex(max(0, self.objective_combo.findData(project.get("objective_id"))))
            self.status_combo.setCurrentIndex(max(0, self.status_combo.findData(project.get("status"))))
        elif objective_id:
            self.objective_combo.setCurrentIndex(max(0, self.objective_combo.findData(objective_id)))

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "objective_id": self.objective_combo.currentData(),
            "status": self.status_combo.currentData(),
        }


class ProgressDialog(QDialog):
    def __init__(self, parent=None, kr: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("更新 KR 进度")
        layout = QFormLayout(self)
        self.value_spin = QDoubleSpinBox()
        self.value_spin.setRange(0, 1_000_000)
        self.value_spin.setDecimals(2)
        if kr:
            self.value_spin.setValue(float(kr.get("current_value") or 0))
        layout.addRow("当前值:", self.value_spin)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class _DetailDialog(QDialog):
    def __init__(self, parent=None, title: str = "", body: str = "", actions: tuple[str, ...] = ("edit", "delete")):
        super().__init__(parent)
        self.action = ""
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        label = QLabel(body)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        buttons = QHBoxLayout()
        buttons.addStretch()
        action_labels = {
            "edit": "编辑",
            "delete": "删除",
            "progress": "更新进度",
            "close": "关闭",
        }
        for action in actions + ("close",):
            button = QPushButton(action_labels[action])
            button.clicked.connect(lambda checked=False, value=action: self._choose(value))
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def _choose(self, action: str):
        self.action = action
        if action == "close":
            self.reject()
        else:
            self.accept()


class GoalModule(QWidget):
    """目标 / KR / 项目管理模块。"""

    PERIOD_LABELS = {"month": "月度", "quarter": "季度", "year": "年度"}
    STATUS_LABELS = {"active": "进行中", "archived": "已归档", "abandoned": "已放弃"}
    PROJECT_STATUS_LABELS = {"planning": "规划中", "active": "进行中", "paused": "暂停", "completed": "已完成"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager()
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        action_bar = QHBoxLayout()
        self.add_objective_btn = QPushButton("新增目标")
        self.add_kr_btn = QPushButton("新增 KR")
        self.add_project_btn = QPushButton("新增项目")
        for btn in (self.add_objective_btn, self.add_kr_btn, self.add_project_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_bar.addWidget(btn)
        action_bar.addStretch()
        layout.addLayout(action_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.objective_table = QTableWidget()
        self.objective_table.setMinimumWidth(430)
        self.objective_table.setColumnCount(5)
        self.objective_table.setHorizontalHeaderLabels(["标题", "周期", "年份", "状态", "权重"])
        self.objective_table.verticalHeader().setVisible(False)
        self.objective_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.objective_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.objective_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.objective_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.objective_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            self.objective_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.objective_table.itemSelectionChanged.connect(lambda: self._on_table_selected(self.objective_table))
        self.objective_table.doubleClicked.connect(self._open_objective_detail)
        enable_clear_selection_on_blur(self.objective_table)
        splitter.addWidget(self.objective_table)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.detail_label = QLabel("请选择目标")
        self.detail_label.setWordWrap(True)
        right_layout.addWidget(self.detail_label)

        kr_group = QGroupBox("KR")
        kr_layout = QVBoxLayout(kr_group)
        self.kr_table = QTableWidget()
        self.kr_table.setColumnCount(4)
        self.kr_table.setHorizontalHeaderLabels(["标题", "数值", "进度", "状态"])
        self.kr_table.verticalHeader().setVisible(False)
        self.kr_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.kr_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.kr_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.kr_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.kr_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            self.kr_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.kr_table.itemSelectionChanged.connect(lambda: self._on_table_selected(self.kr_table))
        self.kr_table.doubleClicked.connect(self._open_kr_detail)
        enable_clear_selection_on_blur(self.kr_table)
        kr_layout.addWidget(self.kr_table)
        right_layout.addWidget(kr_group, 1)

        project_group = QGroupBox("Project")
        project_layout = QVBoxLayout(project_group)
        self.project_table = QTableWidget()
        self.project_table.setColumnCount(2)
        self.project_table.setHorizontalHeaderLabels(["标题", "状态"])
        self.project_table.verticalHeader().setVisible(False)
        self.project_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.project_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.project_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.project_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.project_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.project_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.project_table.itemSelectionChanged.connect(lambda: self._on_table_selected(self.project_table))
        self.project_table.doubleClicked.connect(self._open_project_detail)
        enable_clear_selection_on_blur(self.project_table)
        project_layout.addWidget(self.project_table)
        right_layout.addWidget(project_group, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([430, 760])
        layout.addWidget(splitter, 1)

        self.add_objective_btn.clicked.connect(self._add_objective)
        self.add_kr_btn.clicked.connect(self._add_kr)
        self.add_project_btn.clicked.connect(self._add_project)

    def _refresh(self):
        objectives = self.db.get_objectives("all")
        self.objective_table.setRowCount(len(objectives))
        for row, objective in enumerate(objectives):
            values = [
                objective["title"],
                self.PERIOD_LABELS.get(objective["period"], objective["period"]),
                objective["year"],
                self.STATUS_LABELS.get(objective["status"], objective["status"]),
                objective["weight"],
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, objective["id"])
                if col in (2, 3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.objective_table.setItem(row, col, item)
        self._refresh_detail()

    def _row_id(self, table: QTableWidget) -> int | None:
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, 0)
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return int(value) if value is not None else None

    def _selected_objective_id(self) -> int | None:
        return self._row_id(self.objective_table)

    def _selected_kr_id(self) -> int | None:
        return self._row_id(self.kr_table)

    def _selected_project_id(self) -> int | None:
        return self._row_id(self.project_table)

    def _on_table_selected(self, source: QTableWidget):
        if source.currentRow() < 0:
            if source is self.objective_table:
                self._refresh_detail()
            return
        for table in (self.objective_table, self.kr_table, self.project_table):
            if table is source:
                continue
            table.blockSignals(True)
            table.clearSelection()
            table.setCurrentCell(-1, -1)
            table.blockSignals(False)
        if source is self.objective_table:
            self._refresh_detail()

    def _refresh_detail(self, objective_id: int | None = None):
        oid = objective_id or self._selected_objective_id()
        if not oid:
            self.detail_label.setText("请选择目标")
            self.kr_table.setRowCount(0)
            self.project_table.setRowCount(0)
            return
        detail = build_objective_detail(self.db, oid)
        objective = detail["objective"]
        if not objective:
            return
        self.detail_label.setText(
            f"{objective['title']} · {self.PERIOD_LABELS.get(objective['period'], objective['period'])} "
            f"{objective['year']} · 权重 {objective['weight']}\n{objective.get('description', '')}"
        )
        self.kr_table.setRowCount(len(detail["krs"]))
        for row, kr in enumerate(detail["krs"]):
            values = [
                kr["title"],
                self._kr_value_text(kr),
                f"{calculate_kr_progress(kr)}%",
                self.STATUS_LABELS.get(kr["status"], kr["status"]),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, kr["id"])
                if col >= 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.kr_table.setItem(row, col, item)
        self.project_table.setRowCount(len(detail["projects"]))
        for row, project in enumerate(detail["projects"]):
            values = [
                project["title"],
                self.PROJECT_STATUS_LABELS.get(project["status"], project["status"]),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, project["id"])
                if col >= 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.project_table.setItem(row, col, item)

    def _kr_value_text(self, kr: dict) -> str:
        unit = f" {kr.get('unit')}" if kr.get("unit") else ""
        return f"{float(kr.get('current_value') or 0):g}/{float(kr.get('target_value') or 0):g}{unit}"

    def _get_kr(self, kr_id: int) -> dict | None:
        return next((item for item in self.db.get_key_results(status_filter="all") if item["id"] == kr_id), None)

    def _open_objective_detail(self):
        oid = self._selected_objective_id()
        objective = self.db.get_objective(oid) if oid else None
        if not objective:
            return
        body = (
            f"标题：{objective['title']}\n"
            f"周期：{self.PERIOD_LABELS.get(objective['period'], objective['period'])}\n"
            f"年份：{objective['year']}\n"
            f"状态：{self.STATUS_LABELS.get(objective['status'], objective['status'])}\n"
            f"权重：{objective['weight']}\n\n"
            f"{objective.get('description', '')}"
        )
        dialog = _DetailDialog(self, "目标详情", body)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.action == "edit":
                self._edit_objective(oid)
            elif dialog.action == "delete":
                self._delete_objective(oid)

    def _open_kr_detail(self):
        kr_id = self._selected_kr_id()
        kr = self._get_kr(kr_id) if kr_id else None
        if not kr:
            return
        body = (
            f"标题：{kr['title']}\n"
            f"类型：{kr['metric_type']}\n"
            f"数值：{self._kr_value_text(kr)}\n"
            f"进度：{calculate_kr_progress(kr)}%\n"
            f"状态：{self.STATUS_LABELS.get(kr['status'], kr['status'])}"
        )
        dialog = _DetailDialog(self, "KR 详情", body, ("edit", "progress", "delete"))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.action == "edit":
                self._edit_kr(kr_id)
            elif dialog.action == "progress":
                self._update_kr_progress(kr_id)
            elif dialog.action == "delete":
                self._delete_kr(kr_id)

    def _open_project_detail(self):
        project_id = self._selected_project_id()
        project = self.db.get_project(project_id) if project_id else None
        if not project:
            return
        body = (
            f"标题：{project['title']}\n"
            f"状态：{self.PROJECT_STATUS_LABELS.get(project['status'], project['status'])}\n\n"
            f"{project.get('description', '')}"
        )
        dialog = _DetailDialog(self, "项目详情", body)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.action == "edit":
                self._edit_project(project_id)
            elif dialog.action == "delete":
                self._delete_project(project_id)

    def _add_objective(self):
        dialog = ObjectiveDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["title"]:
                QMessageBox.warning(self, "提示", "目标标题不能为空")
                return
            self.db.add_objective(data["title"], data["description"], data["period"], data["year"], data["weight"])
            self._refresh()

    def _edit_objective(self, oid: int | None = None):
        oid = oid or self._selected_objective_id()
        if not oid:
            QMessageBox.information(self, "提示", "请先选择目标")
            return
        objective = self.db.get_objective(oid)
        dialog = ObjectiveDialog(self, objective)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["title"]:
                QMessageBox.warning(self, "提示", "目标标题不能为空")
                return
            self.db.update_objective(oid, data["title"], data["description"], data["period"], data["year"], data["status"], data["weight"])
            self._refresh()

    def _delete_objective(self, oid: int | None = None):
        oid = oid or self._selected_objective_id()
        if not oid:
            QMessageBox.information(self, "提示", "请先选择目标")
            return
        if QMessageBox.question(self, "确认删除", "确定要删除这个目标吗？相关 KR 会同步删除。") == QMessageBox.StandardButton.Yes:
            self.db.delete_objective(oid)
            self._refresh()

    def _add_kr(self):
        oid = self._selected_objective_id()
        if not oid:
            QMessageBox.information(self, "提示", "请先选择目标")
            return
        dialog = KeyResultDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["title"]:
                QMessageBox.warning(self, "提示", "KR 标题不能为空")
                return
            self.db.add_key_result(oid, data["title"], data["metric_type"], data["current_value"], data["target_value"], data["unit"])
            self._refresh_detail(oid)

    def _edit_kr(self, kr_id: int | None = None):
        kr_id = kr_id or self._selected_kr_id()
        if not kr_id:
            QMessageBox.information(self, "提示", "请先选择 KR")
            return
        kr = self._get_kr(kr_id)
        dialog = KeyResultDialog(self, kr)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["title"]:
                QMessageBox.warning(self, "提示", "KR 标题不能为空")
                return
            self.db.update_key_result(kr_id, data["title"], data["metric_type"], data["current_value"], data["target_value"], data["unit"], data["status"])
            self._refresh_detail(kr.get("objective_id") if kr else None)

    def _update_kr_progress(self, kr_id: int | None = None):
        kr_id = kr_id or self._selected_kr_id()
        if not kr_id:
            QMessageBox.information(self, "提示", "请先选择 KR")
            return
        kr = self._get_kr(kr_id)
        dialog = ProgressDialog(self, kr)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.db.update_key_result_progress(kr_id, dialog.value_spin.value())
            self._refresh_detail(kr.get("objective_id") if kr else None)

    def _delete_kr(self, kr_id: int | None = None):
        kr_id = kr_id or self._selected_kr_id()
        if not kr_id:
            QMessageBox.information(self, "提示", "请先选择 KR")
            return
        kr = self._get_kr(kr_id)
        if QMessageBox.question(self, "确认删除", "确定要删除这个 KR 吗？") == QMessageBox.StandardButton.Yes:
            self.db.delete_key_result(kr_id)
            self._refresh_detail(kr.get("objective_id") if kr else None)

    def _add_project(self):
        oid = self._selected_objective_id()
        dialog = ProjectDialog(self, self.db, objective_id=oid)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["title"]:
                QMessageBox.warning(self, "提示", "项目标题不能为空")
                return
            self.db.add_project(data["title"], data["description"], data["objective_id"], data["status"])
            self._refresh_detail(data["objective_id"])

    def _edit_project(self, project_id: int | None = None):
        project_id = project_id or self._selected_project_id()
        if not project_id:
            QMessageBox.information(self, "提示", "请先选择项目")
            return
        project = self.db.get_project(project_id)
        dialog = ProjectDialog(self, self.db, project=project)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["title"]:
                QMessageBox.warning(self, "提示", "项目标题不能为空")
                return
            self.db.update_project(project_id, data["title"], data["description"], data["objective_id"], data["status"])
            self._refresh_detail(data["objective_id"] or project.get("objective_id"))

    def _delete_project(self, project_id: int | None = None):
        project_id = project_id or self._selected_project_id()
        if not project_id:
            QMessageBox.information(self, "提示", "请先选择项目")
            return
        project = self.db.get_project(project_id)
        if QMessageBox.question(self, "确认删除", "确定要删除这个项目吗？") == QMessageBox.StandardButton.Yes:
            self.db.delete_project(project_id)
            self._refresh_detail(project.get("objective_id") if project else None)
