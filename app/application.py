import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QStyle

from app.database import DatabaseManager


def resource_path(relative_path: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return str(base / relative_path)


class LifeButlerApplication(QApplication):
    """主应用程序——全局配置、系统托盘、定时提醒"""

    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("智能生活管家")
        self.setApplicationDisplayName("LifeButler")
        self.setOrganizationName("LifeButler")
        self.setQuitOnLastWindowClosed(False)
        self.app_icon = QIcon(resource_path("resources/icon/LifeButler-icon.png"))
        if not self.app_icon.isNull():
            self.setWindowIcon(self.app_icon)

        self.db = DatabaseManager()
        self.aboutToQuit.connect(self.db.close)

        self._setup_tray()
        self._setup_timers()

        self.setStyle(self._default_style())

    def _setup_tray(self):
        """初始化系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("智能生活管家")
        tray_icon = self.app_icon if not self.app_icon.isNull() else self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(tray_icon)

        tray_menu = QMenu()
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self._on_show_window)
        tray_menu.addAction(show_action)

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _setup_timers(self):
        """设置定时提醒（饮水提醒每2小时）"""
        self.water_timer = QTimer(self)
        self.water_timer.timeout.connect(self._water_reminder)
        self.water_timer.setInterval(120 * 60 * 1000)
        self.water_timer.start()

    def _water_reminder(self):
        self.tray_icon.showMessage(
            "💧 饮水提醒",
            "该喝水啦！记得保持水分摄入哦～",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_show_window()

    def _on_show_window(self):
        main_window = self.activeWindow()
        if not main_window:
            main_window = next(
                (widget for widget in self.topLevelWidgets() if isinstance(widget, QMainWindow)),
                None,
            )
        if main_window:
            main_window.show()
            main_window.raise_()
            main_window.activateWindow()

    def _default_style(self):
        return """
            QWidget {
                font-size: 13px;
                font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
                color: #dfe7f3;
                background-color: #111827;
            }
            QTableWidget {
                background-color: #162033;
                border: 1px solid #2b3a55;
                gridline-color: #26364f;
                selection-background-color: #2563eb;
                selection-color: #f8fafc;
                alternate-background-color: #1b2940;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QHeaderView::section {
                background-color: #1f2d45;
                color: #cbd5e1;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #334155;
                font-weight: bold;
            }
            QPushButton {
                padding: 6px 16px;
                border: 1px solid #334155;
                border-radius: 4px;
                background-color: #1f2d45;
                color: #e2e8f0;
            }
            QPushButton:hover {
                background-color: #263b5e;
                border-color: #3b82f6;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #334155;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 16px;
                background-color: #121c2d;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #93c5fd;
            }
            QTabWidget::pane {
                border: 1px solid #334155;
                border-radius: 4px;
            }
            QTabBar::tab {
                padding: 8px 16px;
                border: 1px solid #334155;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #2563eb;
                color: #f8fafc;
            }
            QTabBar::tab:!selected {
                background-color: #172033;
                color: #94a3b8;
            }
            QLineEdit, QTextEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 6px;
            }
            QStatusBar {
                background-color: #0f172a;
                color: #94a3b8;
            }
        """
