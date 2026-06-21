from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QMessageBox, QFormLayout, QLineEdit, QDoubleSpinBox,
    QDialog, QDialogButtonBox, QDateEdit, QGroupBox, QSpinBox, QComboBox, QTabWidget,
)
from app.database import DatabaseManager
from app.widgets.chart_widget import ChartWidget
from app.widgets.selection_utils import enable_clear_selection_on_blur


class WeightDialog(QDialog):
    """体重记录对话框"""

    def __init__(self, parent=None, record: dict = None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle("编辑体重" if record else "新增体重记录")
        self.setMinimumWidth(520)
        self._setup_ui()
        if record:
            self._load_record(record)

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(14)

        self.date_edit = QDateEdit()
        self.date_edit.setMinimumWidth(220)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        layout.addRow("日期:", self.date_edit)

        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setMinimumWidth(220)
        self.weight_spin.setRange(20, 300)
        self.weight_spin.setSuffix(" kg")
        self.weight_spin.setDecimals(1)
        layout.addRow("体重:", self.weight_spin)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setMinimumWidth(220)
        self.height_spin.setRange(100, 250)
        self.height_spin.setSuffix(" cm")
        self.height_spin.setDecimals(1)
        self.height_spin.setValue(170)
        layout.addRow("身高:", self.height_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _load_record(self, record: dict):
        self.date_edit.setDate(QDate.fromString(record["date"], "yyyy-MM-dd"))
        self.weight_spin.setValue(record["weight"])
        self.height_spin.setValue(record["height"])

    def get_data(self) -> dict:
        return {
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "weight": self.weight_spin.value(),
            "height": self.height_spin.value(),
        }


class ExerciseDialog(QDialog):
    """运动记录对话框"""

    def __init__(self, parent=None, record: dict = None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle("编辑运动记录" if record else "新增运动记录")
        self.setMinimumWidth(520)
        self._setup_ui()
        if record:
            self._load_record(record)

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(14)

        self.date_edit = QDateEdit()
        self.date_edit.setMinimumWidth(220)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        layout.addRow("日期:", self.date_edit)

        self.type_combo = QComboBox()
        self.type_combo.setMinimumWidth(220)
        self.type_combo.addItems(["跑步", "步行", "骑行", "游泳", "健身", "瑜伽", "球类", "其他"])
        layout.addRow("运动类型:", self.type_combo)

        self.duration_spin = QSpinBox()
        self.duration_spin.setMinimumWidth(220)
        self.duration_spin.setRange(1, 600)
        self.duration_spin.setSuffix(" 分钟")
        layout.addRow("时长:", self.duration_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _load_record(self, record: dict):
        self.date_edit.setDate(QDate.fromString(record["date"], "yyyy-MM-dd"))
        self.type_combo.setCurrentText(record["type"])
        self.duration_spin.setValue(record["duration"])

    def get_data(self) -> dict:
        return {
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "type": self.type_combo.currentText(),
            "duration": self.duration_spin.value(),
        }


class HealthModule(QWidget):
    """健康记录模块——体重管理、运动打卡、BMI计算、健康周报"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager()
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        self.tabs = QTabWidget()

        # ===== 体重管理标签页 =====
        weight_tab = QWidget()
        wt_layout = QVBoxLayout(weight_tab)

        wt_toolbar = QHBoxLayout()
        self.add_weight_btn = QPushButton("➕ 记录体重")
        self.edit_weight_btn = QPushButton("✏️ 编辑")
        self.delete_weight_btn = QPushButton("🗑️ 删除")
        self.add_weight_btn.setObjectName("primaryActionButton")
        self.add_weight_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_weight_btn.clicked.connect(self._add_weight)
        self.edit_weight_btn.clicked.connect(self._edit_weight)
        self.delete_weight_btn.clicked.connect(self._delete_weight)
        wt_toolbar.addWidget(self.add_weight_btn)
        wt_toolbar.addWidget(self.edit_weight_btn)
        wt_toolbar.addWidget(self.delete_weight_btn)
        wt_toolbar.addStretch()
        wt_layout.addLayout(wt_toolbar)

        wt_content = QHBoxLayout()
        self.weight_table = QTableWidget()
        self.weight_table.setColumnCount(4)
        self.weight_table.setHorizontalHeaderLabels(["日期", "体重(kg)", "身高(cm)", "BMI"])
        self.weight_table.setAlternatingRowColors(True)
        self.weight_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.weight_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.weight_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.weight_table.horizontalHeader().setStretchLastSection(True)
        self.weight_table.doubleClicked.connect(self._edit_weight)
        enable_clear_selection_on_blur(self.weight_table)
        wt_content.addWidget(self.weight_table, 3)

        right_wt = QVBoxLayout()
        self.bmi_label = QLabel("BMI 指数")
        self.bmi_label.setWordWrap(True)
        right_wt.addWidget(self.bmi_label)
        self.weight_chart = ChartWidget()
        right_wt.addWidget(self.weight_chart)
        wt_content.addLayout(right_wt, 2)

        wt_layout.addLayout(wt_content)
        self.tabs.addTab(weight_tab, "⚖️ 体重管理")

        # ===== 运动打卡标签页 =====
        exercise_tab = QWidget()
        ex_layout = QVBoxLayout(exercise_tab)

        ex_toolbar = QHBoxLayout()
        self.add_exercise_btn = QPushButton("➕ 运动打卡")
        self.edit_exercise_btn = QPushButton("✏️ 编辑")
        self.delete_exercise_btn = QPushButton("🗑️ 删除")
        self.add_exercise_btn.setObjectName("primaryActionButton")
        self.add_exercise_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_exercise_btn.clicked.connect(self._add_exercise)
        self.edit_exercise_btn.clicked.connect(self._edit_exercise)
        self.delete_exercise_btn.clicked.connect(self._delete_exercise)
        ex_toolbar.addWidget(self.add_exercise_btn)
        ex_toolbar.addWidget(self.edit_exercise_btn)
        ex_toolbar.addWidget(self.delete_exercise_btn)
        ex_toolbar.addStretch()
        ex_layout.addLayout(ex_toolbar)

        ex_content = QHBoxLayout()
        self.exercise_table = QTableWidget()
        self.exercise_table.setColumnCount(4)
        self.exercise_table.setHorizontalHeaderLabels(["ID", "日期", "类型", "时长(分钟)"])
        self.exercise_table.setColumnHidden(0, True)
        self.exercise_table.setAlternatingRowColors(True)
        self.exercise_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.exercise_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.exercise_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.exercise_table.horizontalHeader().setStretchLastSection(True)
        self.exercise_table.doubleClicked.connect(self._edit_exercise)
        enable_clear_selection_on_blur(self.exercise_table)
        ex_content.addWidget(self.exercise_table, 3)

        right_ex = QVBoxLayout()
        self.report_label = QLabel("健康周报")
        self.report_label.setWordWrap(True)
        right_ex.addWidget(self.report_label)
        self.exercise_chart = ChartWidget()
        right_ex.addWidget(self.exercise_chart)
        ex_content.addLayout(right_ex, 2)

        ex_layout.addLayout(ex_content)
        self.tabs.addTab(exercise_tab, "🏃 运动打卡")

        main_layout.addWidget(self.tabs)

    def _refresh(self):
        self._refresh_weight()
        self._refresh_exercise()

    def _refresh_weight(self):
        records = self.db.get_weight_records(30)
        self.weight_table.setRowCount(len(records))
        for row, rec in enumerate(records):
            self.weight_table.setItem(row, 0, QTableWidgetItem(rec["date"]))
            self.weight_table.setItem(row, 1, QTableWidgetItem(f'{rec["weight"]:.1f}'))
            self.weight_table.setItem(row, 2, QTableWidgetItem(f'{rec["height"]:.1f}'))
            bmi = rec["bmi"]
            bmi_text = f"{bmi:.1f}"
            bmi_item = QTableWidgetItem(bmi_text)
            if bmi < 18.5:
                bmi_item.setForeground(Qt.GlobalColor.blue)
            elif bmi > 24:
                bmi_item.setForeground(Qt.GlobalColor.red)
            else:
                bmi_item.setForeground(Qt.GlobalColor.darkGreen)
            self.weight_table.setItem(row, 3, bmi_item)

        if records:
            latest = records[0]
            bmi = latest["bmi"]
            if bmi < 18.5:
                status = "偏瘦 🟦"
            elif bmi < 24:
                status = "正常 ✅"
            elif bmi < 28:
                status = "偏重 🟧"
            else:
                status = "肥胖 🔴"
            self.bmi_label.setText(
                f"📊 最新 BMI: {bmi:.1f} ({status})\n"
                f"   体重: {latest['weight']:.1f} kg\n"
                f"   身高: {latest['height']:.1f} cm"
            )

            dates = [r["date"][-5:] for r in reversed(records)]
            weights = [r["weight"] for r in reversed(records)]
            self.weight_chart.draw_line_chart(dates, weights, "体重变化趋势", "日期", "体重(kg)")
        else:
            self.weight_chart.draw_line_chart([], [], "体重变化趋势")

    def _refresh_exercise(self):
        records = self.db.get_exercise_records(30)
        self.exercise_table.setRowCount(len(records))
        for row, rec in enumerate(records):
            self.exercise_table.setItem(row, 0, QTableWidgetItem(str(rec["id"])))
            self.exercise_table.setItem(row, 1, QTableWidgetItem(rec["date"]))
            self.exercise_table.setItem(row, 2, QTableWidgetItem(rec["type"]))
            self.exercise_table.setItem(row, 3, QTableWidgetItem(str(rec["duration"])))

        report = self.db.get_weekly_report()
        if report:
            total = sum(report.values())
            report_text = f"📅 本周运动总结\n总时长: {total} 分钟\n\n"
            for ex_type, duration in report.items():
                report_text += f"  {ex_type}: {duration} 分钟\n"
            self.report_label.setText(report_text)
            self.exercise_chart.draw_bar_chart(
                list(report.keys()), list(report.values()), "本周运动分布", "#50b080"
            )
        else:
            self.report_label.setText("📅 本周暂无运动记录")
            self.exercise_chart.draw_bar_chart([], [], "本周运动分布")

    def _add_weight(self):
        dialog = WeightDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.db.add_weight_record(data["date"], data["weight"], data["height"])
            self._refresh()

    def _edit_weight(self):
        row = self.weight_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条体重记录")
            return
        record = {
            "date": self.weight_table.item(row, 0).text(),
            "weight": float(self.weight_table.item(row, 1).text()),
            "height": float(self.weight_table.item(row, 2).text()),
        }
        dialog = WeightDialog(self, record)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.db.add_weight_record(data["date"], data["weight"], data["height"])
            self._refresh()

    def _delete_weight(self):
        row = self.weight_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条体重记录")
            return
        date = self.weight_table.item(row, 0).text()
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除这条体重记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_weight_record(date)
            self._refresh()

    def _add_exercise(self):
        dialog = ExerciseDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.db.add_exercise(data["date"], data["type"], data["duration"])
            self._refresh()

    def _edit_exercise(self):
        row = self.exercise_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条运动记录")
            return
        record = {
            "id": int(self.exercise_table.item(row, 0).text()),
            "date": self.exercise_table.item(row, 1).text(),
            "type": self.exercise_table.item(row, 2).text(),
            "duration": int(self.exercise_table.item(row, 3).text()),
        }
        dialog = ExerciseDialog(self, record)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.db.update_exercise(record["id"], data["date"], data["type"], data["duration"])
            self._refresh()

    def _delete_exercise(self):
        row = self.exercise_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条运动记录")
            return
        ex_id = int(self.exercise_table.item(row, 0).text())
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除这条运动记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_exercise(ex_id)
            self._refresh()
