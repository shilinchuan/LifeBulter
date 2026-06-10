"""
智能生活管家 (LifeButler) —— 生活管理桌面应用

功能模块:
  1. 记账管理 — 收支记录、月度统计
  2. 待办事项 — 任务管理、今日四象限、番茄钟
  3. 健康记录 — 体重/BMI、运动打卡、周报
  4. 备忘录   — 富文本笔记、分类、标签、搜索、置顶

启动方式:  python main.py

环境要求:  Python 3.10+, PyQt6, matplotlib
安装依赖:  pip install -r requirements.txt
"""

import sys
import os
import signal

from PyQt6.QtCore import QTimer

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.application import LifeButlerApplication
from app.main_window import MainWindow


def main():
    app = LifeButlerApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())

    # macOS/PyQt 的 GUI 事件循环有时会延迟处理 Ctrl+C；这个轻量
    # 定时器让解释器定期获得处理信号的机会，终端试用时退出更可靠。
    app.sigint_timer = QTimer(app)
    app.sigint_timer.timeout.connect(lambda: None)
    app.sigint_timer.start(200)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
