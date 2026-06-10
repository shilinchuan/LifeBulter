# LifeButler App 包说明

LifeButler 是一个本地生活管理桌面应用，使用 PyQt6 构建界面，SQLite 保存数据，matplotlib 绘制图表。

## 目录结构

```
app/
├── __init__.py
├── application.py           # QApplication 子类：托盘、全局定时器、数据库生命周期
├── database.py              # SQLite 连接、schema 迁移、所有模块的数据 API
├── main_window.py           # 主窗口、左侧导航、全局深浅主题、图表主题联动
├── assets/                  # Qt stylesheet 使用的 SVG 小图标
├── modules/
│   ├── account_module.py    # 记账：收支记录、月度统计
│   ├── todo_module.py       # 待办：任务池、今日四象限、番茄钟
│   ├── health_module.py     # 健康：体重/BMI、运动记录、健康周报
│   └── memo_module.py       # 备忘录：分类、搜索、置顶、Markdown 预览
└── widgets/
    ├── navigation_bar.py    # 左侧导航栏与主题切换按钮
    └── chart_widget.py      # 支持深浅主题的 matplotlib 图表封装
```

## 核心设计

### 数据库与迁移

`DatabaseManager` 是单例，所有模块共享同一个 SQLite 连接。数据库文件默认位于：

```text
data/lifebutler.db
```

测试时可以通过环境变量覆盖路径：

```bash
LIFEBUTLER_DB_PATH=/tmp/test.db .venv/bin/python -m unittest discover -s tests -v
```

数据库当前目标版本为 `schema_version = 3`：

- version 1：旧基础表结构。
- version 2：给任务增加 `quadrant`、`today_date`、`updated_at`，新增 `pomodoro_sessions`。
- version 3：兼容旧预算表约束迁移；预算功能当前已从界面和公开数据 API 移除。

迁移前会自动备份旧数据库。不要跳过迁移直接改表，否则已有用户数据可能因为缺列或约束不匹配而无法打开。

### 今日四象限与番茄钟

任务仍保存在 `todos` 表中：

- `quadrant` 表示今日四象限：`q1` / `q2` / `q3` / `q4`。
- `today_date` 表示任务加入今日清单的日期。
- 今日四象限显示规则是：未完成且 `today_date <= 今天`。

这个规则让未完成任务可以自动顺延。已完成任务不再显示在今日四象限。

番茄钟记录保存在 `pomodoro_sessions`：

- 完成一次 25 分钟专注会记录 `completed`。
- 手动结束会记录 `stopped`。
- 今日四象限和象限大屏中的“番茄/分钟”只统计当天 `completed` 的记录。

### 主题与图表

全局深浅主题由 `MainWindow._apply_theme()` 控制。它会：

1. 切换 Qt 全局 stylesheet。
2. 遍历所有 `ChartWidget`，调用 `set_theme()`。
3. 刷新包含图表的模块，让 matplotlib 画布重新绘制。

`ChartWidget` 会记住上一次绘制的图表类型和数据，所以主题切换后可以自动用新配色重绘。

## 运行

### 第一次安装依赖

这个项目的 Python 依赖写在根目录 `requirements.txt`：

```text
PyQt6>=6.5.0
matplotlib>=3.7.0
```

从零运行时先创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 双击启动

Finder 中双击项目根目录的 `启动 LifeButler.command`。它会打开一个 Terminal 窗口并使用项目内的 `.venv/bin/python` 启动程序。

退出方式：

- 在启动程序的 Terminal 窗口按 `Ctrl+C`。
- 或使用系统托盘菜单里的“退出”。

点窗口左上角关闭按钮会隐藏到托盘，这是当前设计，不等于退出进程。

### 终端启动

从项目根目录运行：

```bash
source .venv/bin/activate
python main.py
```

或：

```bash
.venv/bin/python main.py
```

### 为什么需要 `.venv`

`.venv` 是 Python 虚拟环境，不是虚拟机；它不会运行另一套操作系统，只是在本项目目录里隔离保存 PyQt6、matplotlib 等 Python 包，避免和系统 Python 或其他项目的依赖互相影响。

普通 macOS 应用看起来不需要额外下载依赖，是因为发布者通常已经把运行时和依赖打包进 `.app` 里。当前 LifeButler 仍是源码运行形态，所以需要本机 `.venv`。如果后续做 PyInstaller/py2app 打包，就可以把 Python 和依赖一起放进 App 包，用户双击运行时不需要再手动安装依赖。

## 测试

测试目录在项目根目录的 `tests/`，使用临时数据库，不会污染正式数据。

```bash
.venv/bin/python -m py_compile main.py app/*.py app/modules/*.py app/widgets/*.py tests/*.py
.venv/bin/python -m unittest discover -s tests -v
```

当前测试覆盖：

- 新数据库初始化。
- 旧数据库迁移。
- 今日任务和番茄钟记录。
- 主窗口构造。
- 图表深浅主题切换。
- 任务池与四象限同步。
- 象限大屏弹窗构造。

## 维护注意事项

- 新增或修改数据库字段时，要增加 migration，不要只改 `CREATE TABLE`。
- UI 全局样式在 `main_window.py`，不要在各模块里重复写大段 stylesheet。
- 新增图表时使用 `ChartWidget`，避免直接创建 matplotlib canvas 导致主题不联动。
- 今日四象限小卡片只做概览；完整信息放在象限大屏里。
- 番茄钟分钟数来自 `pomodoro_sessions`，不是手动编辑字段。
