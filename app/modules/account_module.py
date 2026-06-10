from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QComboBox, QMessageBox, QFormLayout, QLineEdit,
    QDialog, QDialogButtonBox, QDateEdit, QDoubleSpinBox, QGroupBox, QGridLayout,
)
from app.database import DatabaseManager
from app.widgets.chart_widget import ChartWidget


class RecordDialog(QDialog):
    """记账记录编辑对话框——新增/编辑一条收支记录"""

    def __init__(self, parent=None, record: dict = None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle("编辑记录" if record else "新增记录")
        self.setMinimumWidth(520)
        self._setup_ui()
        if record:
            self._load_record(record)

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(14)

        self.type_combo = QComboBox()
        self.type_combo.setMinimumWidth(220)
        self.type_combo.addItem("支出", "expense")
        self.type_combo.addItem("收入", "income")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addRow("类型:", self.type_combo)

        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(220)
        self.category_combo.setEditable(True)
        layout.addRow("类别:", self.category_combo)
        self._on_type_changed()

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setMinimumWidth(220)
        self.amount_spin.setRange(0.01, 999999.99)
        self.amount_spin.setPrefix("¥ ")
        self.amount_spin.setDecimals(2)
        layout.addRow("金额:", self.amount_spin)

        self.date_edit = QDateEdit()
        self.date_edit.setMinimumWidth(220)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        layout.addRow("日期:", self.date_edit)

        self.note_edit = QLineEdit()
        self.note_edit.setMinimumWidth(260)
        self.note_edit.setPlaceholderText("备注（可选）")
        layout.addRow("备注:", self.note_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_type_changed(self, *_):
        self.category_combo.clear()
        rec_type = self.type_combo.currentData()
        if rec_type == "expense":
            self.category_combo.addItems(["餐饮", "交通", "购物", "娱乐", "住房", "通讯", "医疗", "教育", "其他"])
        else:
            self.category_combo.addItems(["工资", "奖金", "兼职", "投资", "红包", "其他"])

    def _load_record(self, record: dict):
        index = self.type_combo.findData(record["type"])
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        self.category_combo.setCurrentText(record["category"])
        self.amount_spin.setValue(record["amount"])
        self.date_edit.setDate(QDate.fromString(record["date"], "yyyy-MM-dd"))
        self.note_edit.setText(record["note"])

    def get_data(self) -> dict:
        return {
            "type": self.type_combo.currentData(),
            "category": self.category_combo.currentText().strip(),
            "amount": self.amount_spin.value(),
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "note": self.note_edit.text().strip(),
        }


class AccountModule(QWidget):
    """记账管理模块——收支记录管理与月度统计图表"""

    EXPENSE_CATEGORIES = ["餐饮", "交通", "购物", "娱乐", "住房", "通讯", "医疗", "教育", "其他"]
    INCOME_CATEGORIES = ["工资", "奖金", "兼职", "投资", "红包", "其他"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager()
        self.current_year = QDate.currentDate().year()
        self.current_month = QDate.currentDate().month()
        self.current_chart_type = "expense"
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        top_bar = QHBoxLayout()
        self.add_btn = QPushButton("➕ 新增记录")
        self.edit_btn = QPushButton("✏️ 编辑")
        self.delete_btn = QPushButton("🗑️ 删除")
        self.add_btn.setObjectName("primaryActionButton")
        for btn in (self.add_btn, self.edit_btn, self.delete_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._add_record)
        self.edit_btn.clicked.connect(self._edit_record)
        self.delete_btn.clicked.connect(self._delete_record)
        top_bar.addWidget(self.add_btn)
        top_bar.addWidget(self.edit_btn)
        top_bar.addWidget(self.delete_btn)
        top_bar.addStretch()

        self.month_combo = QComboBox()
        for m in range(1, 13):
            self.month_combo.addItem(f"{m}月", m)
        self.month_combo.setCurrentIndex(self.current_month - 1)
        self.month_combo.currentIndexChanged.connect(self._on_month_changed)
        top_bar.addWidget(QLabel("月份:"))
        top_bar.addWidget(self.month_combo)

        main_layout.addLayout(top_bar)

        content = QHBoxLayout()

        left_col = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "类型", "类别", "金额", "日期", "备注"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnHidden(0, True)
        self.table.doubleClicked.connect(self._edit_record)
        left_col.addWidget(self.table)

        right_col = QVBoxLayout()
        stats_group = QGroupBox("月度统计")
        stats_layout = QVBoxLayout(stats_group)
        self.stats_label = QLabel("加载中...")
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)

        chart_toggle = QHBoxLayout()
        self.expense_chart_btn = QPushButton("支出")
        self.income_chart_btn = QPushButton("收入")
        for btn in (self.expense_chart_btn, self.income_chart_btn):
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumWidth(84)
        self.expense_chart_btn.setChecked(True)
        self.expense_chart_btn.clicked.connect(self._show_expense_chart)
        self.income_chart_btn.clicked.connect(self._show_income_chart)
        chart_toggle.addWidget(self.expense_chart_btn)
        chart_toggle.addWidget(self.income_chart_btn)
        chart_toggle.addStretch()
        stats_layout.addLayout(chart_toggle)

        self.chart = ChartWidget()
        stats_layout.addWidget(self.chart)
        right_col.addWidget(stats_group)

        content.addLayout(left_col, 3)
        content.addLayout(right_col, 2)
        main_layout.addLayout(content)

    def _on_month_changed(self, idx: int):
        self.current_month = self.month_combo.itemData(idx)
        self._refresh()

    def _refresh(self):
        self._refresh_table()
        self._refresh_stats()

    def _refresh_table(self):
        records = self.db.get_records(self.current_year, self.current_month)
        self.table.setRowCount(len(records))
        for row, rec in enumerate(records):
            self.table.setItem(row, 0, QTableWidgetItem(str(rec["id"])))
            type_text = "收入" if rec["type"] == "income" else "支出"
            self.table.setItem(row, 1, QTableWidgetItem(type_text))
            self.table.setItem(row, 2, QTableWidgetItem(rec["category"]))
            amount_item = QTableWidgetItem(f"¥{rec['amount']:.2f}")
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, amount_item)
            self.table.setItem(row, 4, QTableWidgetItem(rec["date"]))
            self.table.setItem(row, 5, QTableWidgetItem(rec["note"]))

    def _refresh_stats(self):
        stats = self.db.get_monthly_stats(self.current_year, self.current_month)
        income_total = stats["income_total"]
        expense_total = stats["expense_total"]
        balance = income_total - expense_total

        stats_text = (
            f"📈 收入: ¥{income_total:.2f}\n"
            f"📉 支出: ¥{expense_total:.2f}\n"
            f"💰 结余: ¥{balance:.2f}"
        )

        self.stats_label.setText(stats_text)

        self._refresh_chart(stats)

    def _show_expense_chart(self):
        self.current_chart_type = "expense"
        self._refresh_stats()

    def _show_income_chart(self):
        self.current_chart_type = "income"
        self._refresh_stats()

    def _refresh_chart(self, stats: dict):
        self.expense_chart_btn.setChecked(self.current_chart_type == "expense")
        self.income_chart_btn.setChecked(self.current_chart_type == "income")
        if self.current_chart_type == "income":
            self.chart.draw_pie_chart(stats["income"], "收入分布")
        else:
            self.chart.draw_pie_chart(stats["expense"], "支出分布")

    def _add_record(self):
        dialog = RecordDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["category"]:
                QMessageBox.warning(self, "提示", "类别不能为空")
                return
            self.db.add_record(data["type"], data["category"], data["amount"], data["date"], data["note"])
            self._refresh()

    def _edit_record(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条记录")
            return
        rec_id = int(self.table.item(row, 0).text())
        record = self.db.execute_query("SELECT * FROM records WHERE id=?", (rec_id,))
        if not record:
            return
        dialog = RecordDialog(self, record[0])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["category"]:
                QMessageBox.warning(self, "提示", "类别不能为空")
                return
            self.db.update_record(rec_id, data["type"], data["category"], data["amount"], data["date"], data["note"])
            self._refresh()

    def _delete_record(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条记录")
            return
        rec_id = int(self.table.item(row, 0).text())
        reply = QMessageBox.question(self, "确认删除", "确定要删除这条记录吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_record(rec_id)
            self._refresh()
