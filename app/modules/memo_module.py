from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QTextEdit,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QSplitter, QListWidget,
    QListWidgetItem, QAbstractItemView,
)
from app.database import DatabaseManager
from app.widgets.selection_utils import enable_clear_selection_on_blur


class MemoDialog(QDialog):
    """备忘录编辑对话框——支持标题、内容、分类、标签"""

    def __init__(self, parent=None, memo: dict = None):
        super().__init__(parent)
        self.memo = memo
        self.setWindowTitle("编辑备忘录" if memo else "新建备忘录")
        self.setMinimumSize(620, 460)
        self._setup_ui()
        if memo:
            self._load_memo(memo)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)
        self.title_edit = QLineEdit()
        self.title_edit.setMinimumWidth(320)
        self.title_edit.setPlaceholderText("标题")
        form.addRow("标题:", self.title_edit)

        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(220)
        self.category_combo.addItems(["general", "生活", "工作", "学习", "其他"])
        self.category_combo.setEditable(True)
        form.addRow("分类:", self.category_combo)

        self.tags_edit = QLineEdit()
        self.tags_edit.setMinimumWidth(320)
        self.tags_edit.setPlaceholderText("以逗号分隔，如: 重要,待办")
        form.addRow("标签:", self.tags_edit)

        layout.addLayout(form)

        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("在此输入备忘录内容...")
        layout.addWidget(self.content_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_memo(self, memo: dict):
        self.title_edit.setText(memo["title"])
        self.content_edit.setText(memo["content"])
        self.category_combo.setCurrentText(memo["category"])
        self.tags_edit.setText(memo.get("tags", ""))

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "content": self.content_edit.toPlainText().strip(),
            "category": self.category_combo.currentText(),
            "tags": self.tags_edit.text().strip(),
        }


class MemoModule(QWidget):
    """备忘录模块——笔记管理、分类筛选、搜索、置顶"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager()
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)

        top_bar = QHBoxLayout()
        self.add_btn = QPushButton("➕ 新建笔记")
        self.edit_btn = QPushButton("✏️ 编辑")
        self.delete_btn = QPushButton("🗑️ 删除")
        self.pin_btn = QPushButton("📌 置顶/取消")
        self.add_btn.setObjectName("primaryActionButton")
        for btn in (self.add_btn, self.edit_btn, self.delete_btn, self.pin_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._add_memo)
        self.edit_btn.clicked.connect(self._edit_memo)
        self.delete_btn.clicked.connect(self._delete_memo)
        self.pin_btn.clicked.connect(self._toggle_pin)
        top_bar.addWidget(self.add_btn)
        top_bar.addWidget(self.edit_btn)
        top_bar.addWidget(self.delete_btn)
        top_bar.addWidget(self.pin_btn)
        top_bar.addStretch()

        self.category_filter = QComboBox()
        self.category_filter.addItems(["全部", "生活", "工作", "学习", "general", "其他"])
        self.category_filter.currentTextChanged.connect(self._on_filter_changed)
        top_bar.addWidget(QLabel("分类:"))
        top_bar.addWidget(self.category_filter)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索备忘录...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._on_search)
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self._on_search)
        top_bar.addWidget(self.search_input)
        top_bar.addWidget(self.search_btn)

        main_layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.memo_list = QListWidget()
        self.memo_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.memo_list.currentRowChanged.connect(self._on_selection_changed)
        enable_clear_selection_on_blur(self.memo_list)
        splitter.addWidget(self.memo_list)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("选择一条备忘录查看内容")
        splitter.addWidget(self.preview)

        splitter.setSizes([200, 400])
        main_layout.addWidget(splitter)

    def _on_filter_changed(self, category: str):
        self._refresh()

    def _on_search(self):
        keyword = self.search_input.text().strip()
        if keyword:
            memos = self.db.search_memos(keyword)
        else:
            memos = self._get_memos()
        self._populate_list(memos)

    def _get_memos(self) -> list:
        category = self.category_filter.currentText()
        if category == "全部":
            return self.db.get_memos()
        return self.db.get_memos(category)

    def _refresh(self):
        self.search_input.clear()
        memos = self._get_memos()
        self._populate_list(memos)

    def _populate_list(self, memos: list):
        self.memo_list.blockSignals(True)
        self.memo_list.clear()
        for m in memos:
            prefix = "📌 " if m["is_pinned"] else ""
            display_text = f"{prefix}{m['title']}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, m["id"])
            if m["is_pinned"]:
                item.setForeground(Qt.GlobalColor.darkBlue)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.memo_list.addItem(item)
        self.memo_list.blockSignals(False)
        self.preview.clear()
        if memos:
            self.memo_list.setCurrentRow(0)
            self._show_preview(memos[0])

    def _on_selection_changed(self, row: int):
        if row < 0:
            return
        item = self.memo_list.item(row)
        if not item:
            return
        mid = item.data(Qt.ItemDataRole.UserRole)
        memos = self.db.execute_query("SELECT * FROM memos WHERE id=?", (mid,))
        if memos:
            self._show_preview(memos[0])

    def _show_preview(self, memo: dict):
        tags = memo.get("tags", "")
        tags_display = f"🏷️ 标签: {tags}" if tags else ""
        content = f"""# {memo['title']}

📂 分类: {memo['category']}  {tags_display}

---
{memo['content']}

---
📅 创建: {memo['created_at'][:16]}  |  更新: {memo['updated_at'][:16]}
"""
        self.preview.setMarkdown(content)

    def _add_memo(self):
        dialog = MemoDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["title"]:
                QMessageBox.warning(self, "提示", "标题不能为空")
                return
            self.db.add_memo(data["title"], data["content"], data["category"], data["tags"])
            self._refresh()

    def _edit_memo(self):
        current = self.memo_list.currentItem()
        if not current:
            QMessageBox.information(self, "提示", "请先选择一条备忘录")
            return
        mid = current.data(Qt.ItemDataRole.UserRole)
        memo = self.db.execute_query("SELECT * FROM memos WHERE id=?", (mid,))
        if not memo:
            return
        dialog = MemoDialog(self, memo[0])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["title"]:
                QMessageBox.warning(self, "提示", "标题不能为空")
                return
            self.db.update_memo(mid, data["title"], data["content"], data["category"], data["tags"], memo[0]["is_pinned"])
            self._refresh()

    def _delete_memo(self):
        current = self.memo_list.currentItem()
        if not current:
            QMessageBox.information(self, "提示", "请先选择一条备忘录")
            return
        mid = current.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "确认删除", "确定要删除这条备忘录吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_memo(mid)
            self._refresh()

    def _toggle_pin(self):
        current = self.memo_list.currentItem()
        if not current:
            QMessageBox.information(self, "提示", "请先选择一条备忘录")
            return
        mid = current.data(Qt.ItemDataRole.UserRole)
        self.db.toggle_pin(mid)
        self._refresh()
