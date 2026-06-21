# LifeButler 技术审阅与二期实现报告

生成日期：2026-06-03

## 结论摘要

LifeButler 已从一个基础 PyQt6 本地生活管理 App 升级为更适合长期使用的版本。本次二期完成：

- 新增四象限今日任务清单，并支持未完成任务自动顺延显示。
- 新增番茄钟，支持绑定今日任务、开始、暂停、继续、停止，并记录专注 session。
- 增加 schema 迁移机制，旧数据库启动时会自动备份并升级。
- 预算功能已从记账界面移除，旧预算表仅保留为历史数据库兼容。
- 重做整体深色主题和图表视觉。
- 补齐健康记录编辑/删除、输入校验、退出关闭数据库连接。
- 增加轻量自动化测试。

## Schema 迁移为什么必要

旧版应用启动时只执行 `CREATE TABLE IF NOT EXISTS`。这个语句只能在表不存在时创建表，不能修改已经存在的表。

这次二期需要做三类旧结构无法自动获得的变化：

- 给 `todos` 增加 `quadrant`、`today_date`、`updated_at` 字段。
- 新增 `pomodoro_sessions` 表保存番茄钟历史。
- 兼容旧 `budgets` 表迁移；当前版本不再暴露预算功能。

如果没有迁移机制，老用户已有数据库打开新版时会遇到缺字段、缺表或唯一约束不匹配；最粗暴的解决办法是删库重建，但会丢掉已有账单、任务、健康记录和备忘录。

现在的机制是：

1. 数据库保存 `schema_meta.schema_version`。
2. 应用启动时读取版本。
3. 如果旧版本低于目标版本，先自动备份数据库。
4. 按版本顺序执行迁移，并在事务内提交。
5. 迁移完成后更新版本号到 3。

这让结构升级变成可控流程，而不是靠手工删库。

## 当前架构

- 入口：`main.py`
- 应用生命周期与托盘：`app/application.py`
- 主窗口和全局主题：`app/main_window.py`
- SQLite、迁移、CRUD：`app/database.py`
- 记账：`app/modules/account_module.py`
- 待办、今日四象限、番茄钟：`app/modules/todo_module.py`
- 健康：`app/modules/health_module.py`
- 备忘录：`app/modules/memo_module.py`
- 图表：`app/widgets/chart_widget.py`

数据库目标版本为 3，包含：

- `schema_meta`
- `records`
- `budgets`（旧库兼容表，当前界面不使用）
- `todos`
- `pomodoro_sessions`
- `health_weight`
- `health_exercise`
- `memos`

## 二期功能说明

### 今日四象限任务

任务仍保存在 `todos` 表中，通过 `today_date` 和 `quadrant` 进入今日清单。

四象限：

- `q1`：重要紧急
- `q2`：重要不紧急
- `q3`：不重要紧急
- `q4`：不重要不紧急

显示规则：`status='pending'` 且 `today_date <= 今天` 的任务会显示在今日四象限，所以昨天未完成的今日任务会自动顺延；已完成任务不会继续显示。

### 番茄钟

番茄钟 v1 使用固定节奏：

- 专注 25 分钟
- 休息 5 分钟
- 不做长休息和自动多轮循环

完成一次专注会写入 `pomodoro_sessions`，今日清单会显示每个任务当天完成番茄数和累计专注分钟。手动停止也会记录为 `stopped`，便于后续追踪中断。

### 深色主题与图表

全局主题现在由导航栏驱动，不再只改变导航栏本身。深色主题覆盖主窗口、表格、状态栏、输入框、对话框和标签页。

图表重做为深色仪表盘风格：

- 饼图改为 donut 图。
- 折线图使用柔和填充和细网格。
- 柱状图使用低饱和亮色和清晰数据标签。
- 保留中文字体回退链，避免图表中文缺字。

## 已修复风险

- PyQt6 托盘图标枚举错误已修复。
- 窗口关闭后隐藏到托盘，并可通过托盘恢复。
- 应用退出时关闭数据库连接。
- 记账类别、任务标题、备忘录标题增加校验。
- 健康模块支持体重和运动记录编辑/删除。
- 预算设置和预算提醒已从记账模块移除。
- 新增迁移前自动备份。
- 新增临时库测试，不污染正式数据库。

## 近期迭代日志

完整日志见 `CHANGELOG.md`。本轮 UI 迭代已同步记录，包括：

- 弹窗控件显示不完整、右侧箭头不可见的修复。
- 任务池工具条拥挤的修复。
- 四象限概览可读性优化，以及象限大屏查看能力。
- 图表深浅主题联动。
- 番茄钟按钮最终布局：第一排 `开始 / 暂停 / 结束`，第二排 `完成任务`。

## 验证方式

语法检查：

```bash
.venv/bin/python -m py_compile main.py app/*.py app/modules/*.py app/widgets/*.py
```

自动化测试：

```bash
.venv/bin/python -m unittest discover -s tests -v
```

测试覆盖：

- 新数据库创建、schema version、今日任务、番茄钟记录。
- 旧数据库迁移，确认旧任务仍可读取。
- 主窗口构造和图表绘制 smoke test。

## 本机运行方式

Finder 双击：

```text
/Users/shilinchuan/Desktop/LifeButler/启动 LifeButler.command
```

该启动器会打开 Terminal，并使用项目内 `.venv/bin/python` 启动程序。退出时可在 Terminal 按 `Ctrl+C`，或使用系统托盘菜单“退出”。

终端运行：

```bash
cd /Users/shilinchuan/Desktop/LifeButler
source .venv/bin/activate
python main.py
```

或：

```bash
cd /Users/shilinchuan/Desktop/LifeButler
.venv/bin/python main.py
```

`.venv` 是 Python 虚拟环境，不是虚拟机；它只隔离本项目需要的 Python 包。普通正式 App 通常已经把 Python 运行时和依赖打包进 `.app`，所以用户看不到安装依赖这一步。

## 后续建议

- 番茄钟可以继续扩展长休息、自动多轮循环和每日专注统计图。
- 今日任务可以扩展历史日期查看。
- 如果要正式分发，下一步应做 PyInstaller 或 macOS `.app` 打包。
