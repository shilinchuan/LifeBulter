import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QStatusBar

from app.widgets.navigation_bar import NavigationBar
from app.widgets.chart_widget import ChartWidget
from app.modules.account_module import AccountModule
from app.modules.todo_module import TodoModule
from app.modules.health_module import HealthModule
from app.modules.memo_module import MemoModule


class MainWindow(QMainWindow):
    """主窗口——组装导航栏与四个功能模块页面"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("智能生活管家 - LifeButler")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav = NavigationBar()
        self.nav.module_changed.connect(self._switch_module)
        self.nav.theme_changed.connect(self._apply_theme)
        layout.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.account_module = AccountModule()
        self.todo_module = TodoModule()
        self.health_module = HealthModule()
        self.memo_module = MemoModule()

        self.stack.addWidget(self.account_module)  # index 0
        self.stack.addWidget(self.todo_module)     # index 1
        self.stack.addWidget(self.health_module)    # index 2
        self.stack.addWidget(self.memo_module)      # index 3

        layout.addWidget(self.stack, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("欢迎使用智能生活管家 💡 左侧导航栏切换功能")

        self._apply_theme()

    def _switch_module(self, index: int):
        """切换到对应模块页面"""
        self.stack.setCurrentIndex(index)
        names = ["记账管理", "待办事项", "健康记录", "备忘录"]
        if 0 <= index < len(names):
            self.status_bar.showMessage(f"当前模块: {names[index]}")

    def _apply_theme(self, is_dark: bool | None = None):
        """根据导航栏当前主题更新全局界面。"""
        if is_dark is None:
            is_dark = self.nav.is_dark
        QApplication.instance().setStyleSheet(self._dark_theme() if is_dark else self._light_theme())
        # Qt stylesheet updates ordinary widgets, but matplotlib canvases need
        # an explicit palette update and redraw.
        for chart in self.findChildren(ChartWidget):
            chart.set_theme(is_dark)
        # Account/health own the current chart data, so refreshing them after a
        # theme switch keeps charts and text panels visually consistent.
        for module in (self.account_module, self.health_module):
            refresh = getattr(module, "_refresh", None)
            if refresh:
                refresh()

    def _dark_theme(self) -> str:
        down = self._asset_url("chevron-down-dark.svg")
        up = self._asset_url("chevron-up-dark.svg")
        return """
            QWidget {
                background-color: #111827;
                color: #dbeafe;
                font-size: 13px;
                font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
            }
            QMainWindow, QDialog { background-color: #111827; }
            QGroupBox {
                background-color: #121c2d;
                border: 1px solid #334155;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 16px;
                font-weight: 600;
            }
            QGroupBox::title {
                color: #93c5fd;
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QTableWidget {
                background-color: #162033;
                alternate-background-color: #1b2940;
                color: #e2e8f0;
                border: 1px solid #2b3a55;
                border-radius: 4px;
                gridline-color: #26364f;
                selection-background-color: #2563eb;
                selection-color: #f8fafc;
            }
            QHeaderView::section {
                background-color: #1f2d45;
                color: #cbd5e1;
                padding: 7px;
                border: none;
                border-bottom: 1px solid #334155;
                font-weight: 600;
            }
            QPushButton {
                background-color: #1f2d45;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 6px 14px;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #263b5e;
                border-color: #60a5fa;
            }
            QPushButton:pressed { background-color: #1d4ed8; }
            QPushButton#primaryActionButton {
                background-color: #2563eb;
                color: #f8fafc;
                border: 1px solid #60a5fa;
                font-weight: 600;
            }
            QPushButton#primaryActionButton:hover {
                background-color: #1d4ed8;
                border-color: #93c5fd;
            }
            QPushButton#primaryActionButton:pressed {
                background-color: #1e40af;
            }
            QLineEdit, QTextEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                min-height: 32px;
                min-width: 150px;
                padding: 4px 42px 4px 10px;
                selection-background-color: #2563eb;
            }
            QComboBox::drop-down, QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 40px;
                border-left: 1px solid #334155;
                background-color: #142033;
            }
            QComboBox QAbstractItemView {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                outline: 0;
                min-width: 180px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 32px;
                padding: 6px 10px;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
            QSpinBox::up-button, QSpinBox::down-button {
                width: 34px;
                background-color: #142033;
                border-left: 1px solid #334155;
            }
            QDateEdit::down-arrow, QComboBox::down-arrow {
                image: url(__DOWN__);
                width: 16px;
                height: 16px;
            }
            QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
                image: url(__UP__);
                width: 12px;
                height: 12px;
            }
            QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
                image: url(__DOWN__);
                width: 12px;
                height: 12px;
            }
            QTabWidget::pane {
                border: 1px solid #334155;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #172033;
                color: #94a3b8;
                padding: 8px 16px;
                border: 1px solid #334155;
                border-bottom: none;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #2563eb;
                color: #f8fafc;
            }
            QStatusBar {
                background-color: #0f172a;
                color: #94a3b8;
            }
            QLabel#timerLabel {
                color: #bfdbfe;
                font-size: 42px;
                font-weight: 700;
                padding: 10px;
            }
        """.replace("__DOWN__", down).replace("__UP__", up)

    def _light_theme(self) -> str:
        down = self._asset_url("chevron-down-light.svg")
        up = self._asset_url("chevron-up-light.svg")
        return """
            QWidget {
                background-color: #f8fafc;
                color: #1e293b;
                font-size: 13px;
                font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #d8dee9;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 16px;
                font-weight: 600;
            }
            QGroupBox::title {
                color: #2563eb;
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f1f5f9;
                border: 1px solid #d8dee9;
                gridline-color: #e2e8f0;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #e2e8f0;
                padding: 7px;
                border: none;
                border-bottom: 1px solid #cbd5e1;
                font-weight: 600;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 6px 14px;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #eff6ff;
                border-color: #3b82f6;
            }
            QPushButton#primaryActionButton {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #2563eb;
                font-weight: 600;
            }
            QPushButton#primaryActionButton:hover {
                background-color: #1d4ed8;
                border-color: #1d4ed8;
            }
            QPushButton#primaryActionButton:pressed {
                background-color: #1e40af;
            }
            QLineEdit, QTextEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                min-height: 32px;
                min-width: 150px;
                padding: 4px 42px 4px 10px;
                selection-background-color: #3b82f6;
            }
            QComboBox::drop-down, QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 40px;
                border-left: 1px solid #cbd5e1;
                background-color: #f1f5f9;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
                outline: 0;
                min-width: 180px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 32px;
                padding: 6px 10px;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
            QSpinBox::up-button, QSpinBox::down-button {
                width: 34px;
                background-color: #f1f5f9;
                border-left: 1px solid #cbd5e1;
            }
            QDateEdit::down-arrow, QComboBox::down-arrow {
                image: url(__DOWN__);
                width: 16px;
                height: 16px;
            }
            QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
                image: url(__UP__);
                width: 12px;
                height: 12px;
            }
            QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
                image: url(__DOWN__);
                width: 12px;
                height: 12px;
            }
            QLabel#timerLabel {
                color: #1d4ed8;
                font-size: 42px;
                font-weight: 700;
                padding: 10px;
            }
        """.replace("__DOWN__", down).replace("__UP__", up)

    def _asset_url(self, filename: str) -> str:
        # Qt stylesheet image URLs need plain filesystem paths; normalize the
        # separator so this also works if the project is moved to another OS.
        path = os.path.join(os.path.dirname(__file__), "assets", filename)
        return path.replace("\\", "/")

    def closeEvent(self, event):
        """关闭时最小化到托盘而非退出"""
        event.ignore()
        self.hide()
