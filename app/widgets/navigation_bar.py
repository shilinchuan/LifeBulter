from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy


class NavigationBar(QWidget):
    """左侧导航栏——包含功能模块切换按钮与主题切换"""

    module_changed = pyqtSignal(int)
    theme_changed = pyqtSignal(bool)

    MODULES = [
        ("🏠  首页", 0),
        ("📊  记账管理", 1),
        ("🎯  目标管理", 2),
        ("✅  待办事项", 3),
        ("❤️  健康记录", 4),
        ("📝  备忘录", 5),
        ("📅  周报复盘", 6),
        ("⚙️  设置", 7),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(180)
        self.current_index = 0
        self.buttons = []
        self._collapsed = False
        self._dark_mode = True
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 12, 6, 12)
        layout.setSpacing(6)

        for text, idx in self.MODULES:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(48)
            btn.clicked.connect(lambda checked, i=idx: self._on_click(i))
            self.buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        self.theme_btn = QPushButton("☀️  浅色模式")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setMinimumHeight(40)
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

        self.buttons[0].setChecked(True)
        self.setStyleSheet(self._dark_style())

    def _on_click(self, idx: int):
        self.current_index = idx
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == idx)
        self.module_changed.emit(idx)

    def _toggle_theme(self):
        self._dark_mode = not self._dark_mode
        if self._dark_mode:
            self.setStyleSheet(self._dark_style())
            self.theme_btn.setText("☀️  浅色模式")
        else:
            self.setStyleSheet(self._light_style())
            self.theme_btn.setText("🌙  深色模式")
        self.theme_changed.emit(self._dark_mode)

    def _light_style(self) -> str:
        return """
            QWidget { background-color: #f5f5f5; }
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 14px;
                text-align: left;
                color: #333;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:checked {
                background-color: #4a90d9;
                color: #fff;
                font-weight: bold;
            }
        """

    def _dark_style(self) -> str:
        return """
            QWidget { background-color: #2b2b2b; }
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 14px;
                text-align: left;
                color: #ccc;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
            QPushButton:checked {
                background-color: #4a90d9;
                color: #fff;
                font-weight: bold;
            }
        """

    @property
    def is_dark(self) -> bool:
        return self._dark_mode
