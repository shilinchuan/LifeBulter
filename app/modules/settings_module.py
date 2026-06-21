import os

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QMessageBox, QPlainTextEdit, QSizePolicy,
)

from app.database import DatabaseManager


class SettingsModule(QWidget):
    """设置页：数据库信息、备份入口和应用说明。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager()
        self.last_backup_path = ""
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        data_group = QGroupBox("本地数据")
        data_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        data_layout = QVBoxLayout(data_group)
        data_layout.setSpacing(12)

        path_row = QHBoxLayout()
        path_row.setSpacing(10)
        path_title = QLabel("数据库路径:")
        self.path_edit = QPlainTextEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setFixedHeight(78)
        self.path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.path_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.path_label = self.path_edit
        path_row.addWidget(path_title)
        path_row.addWidget(self.path_edit, 1)
        data_layout.addLayout(path_row)

        schema_row = QHBoxLayout()
        schema_row.setSpacing(10)
        self.schema_label = QLabel()
        schema_row.addWidget(QLabel("Schema:"))
        schema_row.addWidget(self.schema_label)
        schema_row.addStretch()
        data_layout.addLayout(schema_row)

        button_row = QHBoxLayout()
        self.backup_btn = QPushButton("备份数据库")
        self.backup_btn.setObjectName("primaryActionButton")
        self.open_backup_dir_btn = QPushButton("打开备份目录")
        self.copy_path_btn = QPushButton("复制路径")
        self.backup_btn.clicked.connect(self._backup_database)
        self.open_backup_dir_btn.clicked.connect(self._open_backup_dir)
        self.copy_path_btn.clicked.connect(self._copy_database_path)
        button_row.addWidget(self.backup_btn)
        button_row.addWidget(self.open_backup_dir_btn)
        button_row.addWidget(self.copy_path_btn)
        button_row.addStretch()
        data_layout.addLayout(button_row)
        layout.addWidget(data_group)

        about_group = QGroupBox("关于 LifeButler")
        about_layout = QVBoxLayout(about_group)
        about = QLabel(
            "LifeButler 是本地运行的生活管理桌面应用，整合首页驾驶舱、记账、目标、待办、健康、备忘录、周计划和周报复盘。"
        )
        about.setWordWrap(True)
        about_layout.addWidget(about)
        layout.addWidget(about_group)
        layout.addStretch()

    def _refresh(self):
        self.path_edit.setPlainText(self.db.db_path)
        self.path_edit.setToolTip(self.db.db_path)
        self.schema_label.setText(str(DatabaseManager.TARGET_SCHEMA_VERSION))

    def _backup_database(self):
        try:
            self.last_backup_path = self.db.backup_data()
        except Exception as exc:
            QMessageBox.warning(self, "备份失败", str(exc))
            return
        QMessageBox.information(self, "备份成功", f"已备份到：{self.last_backup_path}")

    def _open_backup_dir(self):
        directory = os.path.dirname(self.last_backup_path or self.db.db_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(directory))

    def _copy_database_path(self):
        QApplication.clipboard().setText(self.db.db_path)
        QMessageBox.information(self, "提示", "数据库路径已复制")
