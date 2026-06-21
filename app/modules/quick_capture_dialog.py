from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QLineEdit, QPlainTextEdit, QSpinBox, QStackedWidget, QWidget,
)

from app.database import DatabaseManager


class QuickCaptureDialog(QDialog):
    KIND_OPTIONS = [
        ("task", "任务"),
        ("finance", "账单"),
        ("exercise", "运动"),
        ("memo", "备忘录"),
    ]
    QUADRANTS = [("q1", "重要紧急"), ("q2", "重要不紧急"), ("q3", "不重要紧急"), ("q4", "不重要不紧急")]

    def __init__(self, parent=None, parsed: dict | None = None, db=None):
        super().__init__(parent)
        self.parsed = parsed or {"kind": "memo", "raw": "", "fields": {}}
        self.db = db or DatabaseManager()
        self.setWindowTitle("快速收集确认")
        self.setMinimumWidth(560)
        self._setup_ui()
        self._load_parsed()

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(12)

        self.kind_combo = QComboBox()
        for value, label in self.KIND_OPTIONS:
            self.kind_combo.addItem(label, value)
        self.kind_combo.currentIndexChanged.connect(self._sync_stack)
        layout.addRow("保存为:", self.kind_combo)

        self.stack = QStackedWidget()
        self.task_page = self._build_task_page()
        self.finance_page = self._build_finance_page()
        self.exercise_page = self._build_exercise_page()
        self.memo_page = self._build_memo_page()
        for page in (self.task_page, self.finance_page, self.exercise_page, self.memo_page):
            self.stack.addWidget(page)
        layout.addRow(self.stack)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _build_task_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.task_title_edit = QLineEdit()
        self.task_due_edit = QDateEdit()
        self.task_due_edit.setCalendarPopup(True)
        self.task_due_edit.setDate(QDate.currentDate())
        self.task_quadrant_combo = QComboBox()
        for value, label in self.QUADRANTS:
            self.task_quadrant_combo.addItem(label, value)
        self.task_today_check = QCheckBox("加入今日")
        form.addRow("标题:", self.task_title_edit)
        form.addRow("截止日期:", self.task_due_edit)
        form.addRow("象限:", self.task_quadrant_combo)
        form.addRow("", self.task_today_check)
        return page

    def _build_finance_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.finance_type_combo = QComboBox()
        self.finance_type_combo.addItem("支出", "expense")
        self.finance_type_combo.addItem("收入", "income")
        self.finance_category_edit = QLineEdit("其他")
        self.finance_amount_spin = QDoubleSpinBox()
        self.finance_amount_spin.setRange(0, 1_000_000)
        self.finance_amount_spin.setDecimals(2)
        self.finance_date_edit = QDateEdit()
        self.finance_date_edit.setCalendarPopup(True)
        self.finance_date_edit.setDate(QDate.currentDate())
        self.finance_note_edit = QLineEdit()
        form.addRow("类型:", self.finance_type_combo)
        form.addRow("类别:", self.finance_category_edit)
        form.addRow("金额:", self.finance_amount_spin)
        form.addRow("日期:", self.finance_date_edit)
        form.addRow("备注:", self.finance_note_edit)
        return page

    def _build_exercise_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.exercise_date_edit = QDateEdit()
        self.exercise_date_edit.setCalendarPopup(True)
        self.exercise_date_edit.setDate(QDate.currentDate())
        self.exercise_type_edit = QLineEdit("其他")
        self.exercise_duration_spin = QSpinBox()
        self.exercise_duration_spin.setRange(1, 1440)
        self.exercise_duration_spin.setValue(30)
        form.addRow("日期:", self.exercise_date_edit)
        form.addRow("运动类型:", self.exercise_type_edit)
        form.addRow("时长:", self.exercise_duration_spin)
        return page

    def _build_memo_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.memo_title_edit = QLineEdit()
        self.memo_category_edit = QLineEdit("general")
        self.memo_tags_edit = QLineEdit()
        self.memo_content_edit = QPlainTextEdit()
        self.memo_content_edit.setFixedHeight(120)
        form.addRow("标题:", self.memo_title_edit)
        form.addRow("分类:", self.memo_category_edit)
        form.addRow("标签:", self.memo_tags_edit)
        form.addRow("内容:", self.memo_content_edit)
        return page

    def _load_parsed(self):
        kind = self.parsed.get("kind") if self.parsed.get("kind") != "invalid" else "memo"
        index = self.kind_combo.findData(kind)
        if index >= 0:
            self.kind_combo.setCurrentIndex(index)
        fields = self.parsed.get("fields") or {}
        raw = self.parsed.get("raw", "")

        self.task_title_edit.setText(fields.get("title") or raw)
        self.task_due_edit.setDate(QDate.fromString(fields.get("due_date", QDate.currentDate().toString("yyyy-MM-dd")), "yyyy-MM-dd"))
        quadrant_index = self.task_quadrant_combo.findData(fields.get("quadrant", "q2"))
        if quadrant_index >= 0:
            self.task_quadrant_combo.setCurrentIndex(quadrant_index)
        self.task_today_check.setChecked(bool(fields.get("add_to_today")))

        self.finance_type_combo.setCurrentIndex(max(0, self.finance_type_combo.findData(fields.get("type", "expense"))))
        self.finance_category_edit.setText(fields.get("category", "其他"))
        self.finance_amount_spin.setValue(float(fields.get("amount") or 0))
        self.finance_date_edit.setDate(QDate.fromString(fields.get("date", QDate.currentDate().toString("yyyy-MM-dd")), "yyyy-MM-dd"))
        self.finance_note_edit.setText(fields.get("note", raw))

        self.exercise_date_edit.setDate(QDate.fromString(fields.get("date", QDate.currentDate().toString("yyyy-MM-dd")), "yyyy-MM-dd"))
        self.exercise_type_edit.setText(fields.get("type", "其他"))
        self.exercise_duration_spin.setValue(max(1, int(fields.get("duration") or 30)))

        self.memo_title_edit.setText(fields.get("title", raw[:20]))
        self.memo_category_edit.setText(fields.get("category", "general"))
        self.memo_tags_edit.setText(fields.get("tags", ""))
        self.memo_content_edit.setPlainText(fields.get("content", raw))
        self._sync_stack()

    def _sync_stack(self):
        self.stack.setCurrentIndex(max(0, self.kind_combo.currentIndex()))

    def get_kind(self) -> str:
        return self.kind_combo.currentData()

    def get_fields(self) -> dict:
        kind = self.get_kind()
        if kind == "task":
            return {
                "title": self.task_title_edit.text().strip(),
                "due_date": self.task_due_edit.date().toString("yyyy-MM-dd"),
                "priority": "medium",
                "quadrant": self.task_quadrant_combo.currentData(),
                "add_to_today": self.task_today_check.isChecked(),
            }
        if kind == "finance":
            return {
                "type": self.finance_type_combo.currentData(),
                "category": self.finance_category_edit.text().strip() or "其他",
                "amount": self.finance_amount_spin.value(),
                "date": self.finance_date_edit.date().toString("yyyy-MM-dd"),
                "note": self.finance_note_edit.text().strip(),
            }
        if kind == "exercise":
            return {
                "date": self.exercise_date_edit.date().toString("yyyy-MM-dd"),
                "type": self.exercise_type_edit.text().strip() or "其他",
                "duration": self.exercise_duration_spin.value(),
            }
        return {
            "title": self.memo_title_edit.text().strip(),
            "category": self.memo_category_edit.text().strip() or "general",
            "tags": self.memo_tags_edit.text().strip(),
            "content": self.memo_content_edit.toPlainText(),
        }
