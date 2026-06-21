# LifeButler 后续开发实施 Runbook

> 目的：交给另一个 Codex 会话直接落地完整项目更改。本文档是施工手册，不是讨论稿。按 Phase 顺序执行；功能完整实现并通过用户验收后，才进入 macOS `.app` 打包阶段。

## 0. 项目说明与执行规则

LifeButler 是一个本地桌面生活管理应用，技术栈为 PyQt6 + SQLite + matplotlib。当前已实现记账管理、待办事项、今日四象限、番茄钟、健康记录、备忘录、深浅主题、SQLite schema migration 和 smoke tests。

本轮目标是在不接入 AI API 的前提下，完整落地以下能力：

1. 目标 / KR / 项目：把任务从孤立事项升级为目标推进链路。
2. 今日驾驶舱：首页集中展示今日任务、专注、财务、健康、生活雷达和快速收集入口。
3. 周计划 / 周报复盘：把任务推进到本周和今日，并生成可保存、可导出的复盘。
4. 快速收集箱：用本地规则识别任务、账单、运动和备忘录。
5. 生活雷达：用本地规则发现任务过载、健康缺口、财务压力和目标停滞。
6. CLI JSON 层：提供最小 Agent 可操作接口。
7. 备份与导出：提供数据库备份入口和周报 Markdown 导出。
8. UI screenshot 验证：在用户验收前完成自动截图和人工快速检查。
9. macOS `.app` 打包：仅在用户确认功能验收通过后执行。

每个执行会话开始先读：

```text
AGENTS.md
skills/lifebutler-maintainer/SKILL.md
skills/lifebutler-maintainer/references/lessons.md
README.md
app/README.md
```

执行规则：

1. 不直接读取、修改、删除或重置 `data/lifebutler.db*`。
2. 数据库实验和测试必须使用临时库，沿用 `LIFEBUTLER_DB_PATH` 和 `DatabaseManager` singleton reset 模式。
3. 修改 schema 必须新增 migration，不能只改 `CREATE TABLE IF NOT EXISTS`。
4. 不接 AI API；“智能”能力全部使用本地规则、模板和已有数据。
5. 不重写旧模块；在现有 PyQt6 + SQLite + matplotlib 架构内增量扩展。
6. 新图表继续使用 `ChartWidget`；主题切换继续由 `MainWindow._apply_theme()` 统一传播。
7. 每个 Phase 完成后运行对应验证；UI Phase 必须留存 screenshot。
8. 不写“降级实现”。每个 Phase 都按完整功能验收。
9. 不在用户验收前执行 macOS `.app` 打包。

基础验证命令：

```bash
.venv/bin/python -m py_compile main.py app/*.py app/modules/*.py app/widgets/*.py tests/*.py
.venv/bin/python -m unittest discover -s tests -v
```

如果新增 `app/services/*.py`、`app/cli.py` 或 `scripts/*.py`，验证命令改为：

```bash
.venv/bin/python -m py_compile main.py app/*.py app/modules/*.py app/widgets/*.py app/services/*.py app/cli.py scripts/*.py tests/*.py
.venv/bin/python -m unittest discover -s tests -v
```

---

## Phase 1：Schema v4 + Service 层

目标：先补齐数据模型和无 UI 业务层，保证后续 GUI、CLI、测试共用同一套逻辑。

### 1.1 修改范围

修改：

```text
app/database.py
tests/test_lifebutler_smoke.py
```

新增：

```text
app/services/__init__.py
app/services/goal_service.py
app/services/week_service.py
app/services/overview_service.py
app/services/quick_capture_service.py
tests/test_lifebutler_services.py
```

### 1.2 Schema v4

将 `DatabaseManager.TARGET_SCHEMA_VERSION` 从 `3` 升到 `4`。

`init_tables()` 包含 v4 最新结构。`_migrate()` 按顺序执行：

```text
v1 -> v2 -> v3 -> v4
```

新增 `_migrate_to_v4()`，要求：

1. 在事务内执行。
2. 创建 `objectives`、`key_results`、`projects`、`weekly_tasks`、`weekly_reviews`。
3. 检查 `todos` 是否已有 `project_id`，没有则 `ALTER TABLE todos ADD COLUMN project_id INTEGER`。
4. 写入 `schema_meta.schema_version = 4`。
5. 出错 rollback。

新增表结构：

```sql
CREATE TABLE IF NOT EXISTS objectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    period TEXT NOT NULL DEFAULT 'quarter',
    year INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    weight INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(period IN ('month','quarter','year')),
    CHECK(status IN ('active','archived','abandoned')),
    CHECK(weight > 0)
);
```

```sql
CREATE TABLE IF NOT EXISTS key_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    objective_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    metric_type TEXT NOT NULL DEFAULT 'number',
    current_value REAL NOT NULL DEFAULT 0,
    target_value REAL NOT NULL DEFAULT 100,
    unit TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(objective_id) REFERENCES objectives(id) ON DELETE CASCADE,
    CHECK(metric_type IN ('number','percentage','boolean')),
    CHECK(status IN ('active','archived','abandoned'))
);
```

```sql
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    objective_id INTEGER,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(objective_id) REFERENCES objectives(id) ON DELETE SET NULL,
    CHECK(status IN ('planning','active','paused','completed'))
);
```

```sql
CREATE TABLE IF NOT EXISTS weekly_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    week INTEGER NOT NULL,
    today_task_date TEXT DEFAULT '',
    completion INTEGER NOT NULL DEFAULT 0,
    progress_note TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(task_id, year, week),
    FOREIGN KEY(task_id) REFERENCES todos(id) ON DELETE CASCADE,
    CHECK(week >= 1 AND week <= 53),
    CHECK(completion >= 0 AND completion <= 100)
);
```

```sql
CREATE TABLE IF NOT EXISTS weekly_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    week INTEGER NOT NULL,
    proud TEXT DEFAULT '',
    change TEXT DEFAULT '',
    commit TEXT DEFAULT '',
    auto_summary TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(year, week)
);
```

### 1.3 Database API

在 `DatabaseManager` 中新增 API；UI、CLI、service 不直接散落 SQL。

目标：

```python
add_objective(title, description="", period="quarter", year=None, weight=1) -> int
update_objective(oid, title, description, period, year, status, weight) -> None
delete_objective(oid) -> None
get_objective(oid) -> dict | None
get_objectives(status_filter="active") -> list[dict]
```

KR：

```python
add_key_result(objective_id, title, metric_type="number", current_value=0, target_value=100, unit="") -> int
update_key_result(kr_id, title, metric_type, current_value, target_value, unit, status) -> None
update_key_result_progress(kr_id, current_value) -> None
delete_key_result(kr_id) -> None
get_key_results(objective_id=None, status_filter="active") -> list[dict]
```

项目：

```python
add_project(title, description="", objective_id=None, status="active") -> int
update_project(project_id, title, description, objective_id, status) -> None
delete_project(project_id) -> None
get_project(project_id) -> dict | None
get_projects(objective_id=None, status_filter="active") -> list[dict]
```

任务绑定项目：

```python
bind_todo_project(tid, project_id: int | None) -> None
get_todos_by_project(project_id) -> list[dict]
```

周计划：

```python
add_weekly_task(task_id, year, week) -> int
remove_weekly_task(weekly_task_id) -> None
get_weekly_tasks(year, week) -> list[dict]
update_weekly_task(weekly_task_id, completion=None, progress_note=None, today_task_date=None) -> None
get_weekly_review(year, week) -> dict | None
save_weekly_review(year, week, proud, change, commit, auto_summary) -> int
```

`add_todo()` 和 `update_todo()` 增加可选 `project_id=None` 参数，保持旧调用兼容。

### 1.4 Service 职责

`goal_service.py`：

1. `calculate_kr_progress(kr)`：返回 0-100。
2. `get_project_task_stats(db, project_id)`：返回 total、done、pending。
3. `build_objective_detail(db, objective_id)`：返回 objective、krs、projects、task counts。

KR 进度规则：

1. `target_value <= 0` 返回 0。
2. `percentage`：`current_value / 100 * 100`，上限 100。
3. `boolean`：`current_value >= 1` 为 100，否则 0。
4. `number`：`current_value / target_value * 100`，上限 100。

`week_service.py`：

1. `current_year_week()`：使用 ISO week。
2. `week_date_range(year, week)`：返回周一、周日日期字符串。
3. `build_week_summary(db, year, week)`：统计任务数、完成数、完成率、番茄分钟、运动分钟、收入、支出、结余、顺延任务数。
4. `render_week_review_markdown(summary, review)`：返回 Markdown 字符串。

`overview_service.py`：

1. `build_today_overview(db, today=None)`：首页所有统计。
2. `build_life_radar(db, today=None)`：生活雷达规则提醒。

`quick_capture_service.py`：

1. `parse_quick_capture(text, today=None)`：只解析，不写库。
2. `commit_quick_capture(db, parsed, edited_fields)`：按确认后的类型写入。

### 1.5 自动化测试

新增 / 扩展测试：

1. 新库 schema version 为 `4`。
2. 手造 v3 旧库迁移到 v4 后：
   - 旧任务仍存在。
   - `todos.project_id` 存在。
   - 新表存在。
   - 旧记账、健康、备忘录表仍可读。
3. 新增目标、KR、项目、任务绑定项目后可读回。
4. 周计划同一任务同一周不会重复。
5. service 在空库下不崩溃。
6. `calculate_kr_progress()` 覆盖 number、percentage、boolean、target<=0。

### 1.6 Phase 1 验收

执行：

```bash
.venv/bin/python -m py_compile main.py app/*.py app/modules/*.py app/widgets/*.py app/services/*.py tests/*.py
.venv/bin/python -m unittest discover -s tests -v
```

通过标准：

1. 所有测试通过。
2. 新增 service 不 import PyQt。
3. 测试不读取真实 `data/`。
4. 旧功能 smoke tests 仍通过。

---

## Phase 2：首页驾驶舱 + 生活雷达

目标：新增默认首页，集中呈现今日任务、专注、财务、健康、生活雷达和快速收集入口。

### 2.1 修改范围

修改：

```text
app/main_window.py
app/widgets/navigation_bar.py
tests/test_lifebutler_smoke.py
```

新增：

```text
app/modules/dashboard_module.py
```

### 2.2 导航结构

左侧导航顺序：

```text
首页
记账管理
目标管理
待办事项
健康记录
备忘录
周报复盘
设置
```

Phase 2 先接入首页；后续 Phase 接入目标、周报和设置。`MainWindow.stack` 顺序必须与导航一致，未实现页面不得留空按钮；每个新增页面完成后再打开对应导航。

启动后默认进入首页。

### 2.3 DashboardModule 功能

首页布局：

1. 顶部：快速收集输入框 + “收集”按钮。
2. 概览卡片：今日三件事、今日专注、本月财务、近 7 天运动。
3. 四象限摘要：q1-q4 今日 pending 数量。
4. 生活雷达：规则提醒列表。
5. 今日任务简表：pending 且 `today_date <= today`。

数据来自：

```python
overview_service.build_today_overview(db, today=None)
```

返回结构：

```python
{
    "today": "YYYY-MM-DD",
    "top_tasks": [todo, todo, todo],
    "quadrants": {"q1": 0, "q2": 0, "q3": 0, "q4": 0},
    "pomodoro": {"count": 0, "minutes": 0},
    "finance": {"income": 0.0, "expense": 0.0, "balance": 0.0},
    "health": {"exercise_minutes_7d": 0},
    "radar": [{"level": "warning", "title": "...", "detail": "...", "suggestion": "..."}],
}
```

今日三件事排序：

1. q1 优先。
2. q2 次之。
3. 截止日期更早优先。
4. `updated_at` 更晚优先。
5. 最多 3 条。

空状态：

1. 没有今日任务时显示“暂无今日任务”。
2. 没有雷达提醒时显示“暂无风险提醒”。
3. 财务、健康、番茄统计显示 0，不显示异常堆栈。

### 2.4 生活雷达规则

`overview_service.build_life_radar()` 实现：

1. 今日 q1 pending 任务 > 3：任务过载。
2. pending 今日任务存在 `today_date <= today - 3 days`：顺延风险。
3. 最近 7 天运动分钟 = 0：健康缺口。
4. 本月收入 > 0 且支出 / 收入 >= 0.8：财务压力。
5. active 目标存在，但其项目下 7 天内没有完成任务：目标停滞。

提醒格式：

```python
{
    "level": "info" | "warning",
    "title": "任务过载",
    "detail": "...",
    "suggestion": "..."
}
```

### 2.5 UI 设计要求

1. 首页不能只是表格，必须使用清晰分区和概览卡片。
2. 卡片文字不能超出边界。
3. 今日任务表格标题列需要 stretch。
4. 深浅主题下背景、文字、边框对比度足够。
5. 快速收集输入框不能挤压概览卡片。

### 2.6 自动化测试

新增测试：

1. `DashboardModule` 可构造。
2. `MainWindow.stack` 默认 index 0 是首页。
3. 空库 `build_today_overview()` 字段完整。
4. 构造 q1 > 3 后，雷达出现任务过载。
5. 构造 7 天无运动后，雷达出现健康缺口。
6. 深浅主题切换后首页仍可刷新。

### 2.7 Screenshot 验证

Phase 2 完成后必须先临时或手动生成首页截图，后续 Phase 8 再统一脚本化。

截图要求：

1. 深色首页一张。
2. 浅色首页一张。
3. 截图中必须能看到快速收集、今日三件事、四象限摘要、生活雷达。
4. 页面不得出现明显重叠、截断、空白大块。

### 2.8 Phase 2 验收

通过标准：

1. App 启动默认首页。
2. 首页不直接写散落 SQL。
3. 空库、有 demo 数据两种状态都可显示。
4. 自动化测试通过。
5. 深浅主题截图留存到 `outputs/ui-qa/...` 或临时记录路径。

---

## Phase 3：目标 / KR / 项目管理

目标：实现目标推进链路，任务可以绑定项目，目标详情能看到 KR 和项目进展。

### 3.1 修改范围

新增：

```text
app/modules/goal_module.py
```

修改：

```text
app/main_window.py
app/widgets/navigation_bar.py
app/modules/todo_module.py
app/database.py
tests/test_lifebutler_smoke.py
tests/test_lifebutler_services.py
```

### 3.2 GoalModule UI

使用 `QSplitter`：

1. 左侧：目标列表。
2. 右侧：目标详情。

目标详情分三块：

1. Objective 基本信息。
2. KR 表格。
3. Project 表格。

工具按钮：

```text
新增目标
编辑目标
删除目标
新增 KR
编辑 KR
更新 KR 进度
新增项目
编辑项目
删除项目
刷新
```

目标列表列：

```text
标题 | 周期 | 年份 | 状态 | 权重
```

KR 表格列：

```text
标题 | 当前值 | 目标值 | 单位 | 进度 | 状态
```

项目表格列：

```text
标题 | 状态 | 任务总数 | 已完成 | 进行中
```

### 3.3 Dialog 行为

`ObjectiveDialog`：

1. title 必填。
2. period 选项：`month`、`quarter`、`year`，UI 文案中文。
3. year 默认当前年。
4. weight 默认 1，范围 1-10。

`KeyResultDialog`：

1. title 必填。
2. metric_type 选项：`number`、`percentage`、`boolean`。
3. percentage 自动 target 默认 100，unit 默认 `%`。
4. boolean 自动 target 默认 1，unit 默认空。

`ProjectDialog`：

1. title 必填。
2. objective 可为空。
3. status 选项：`planning`、`active`、`paused`、`completed`。

### 3.4 任务绑定项目

修改 `TodoDialog`：

1. 新增项目下拉框。
2. 第一项“无项目”，data 为 `None`。
3. 其余项来自 `db.get_projects(status_filter="active")`。
4. 编辑任务时回显 `project_id`。

修改 `TodoModule._refresh_pool()`：

1. 任务池表格新增“项目”列。
2. 无项目显示空字符串。
3. 表格列宽保持可读，标题列 stretch。

### 3.5 自动化测试

新增测试：

1. `GoalModule` 可构造。
2. 新建 objective、KR、project 后 detail 统计正确。
3. 任务绑定 project 后，项目任务总数 +1。
4. 完成任务后，项目 done 数 +1。
5. `TodoDialog` 在无项目和有项目两种情况下都能构造。

### 3.6 Screenshot 验证

截图：

1. 深色目标管理页。
2. 浅色目标管理页。
3. 新增目标弹窗。
4. 新增 KR 弹窗。
5. 新增项目弹窗。
6. 带项目列的任务池页面。

验收点：

1. 左右分栏宽度合理。
2. KR 进度列可见。
3. 项目任务统计列可见。
4. 弹窗表单控件无截断。
5. 任务池新增“项目”列后没有挤爆工具条。

### 3.7 Phase 3 验收

通过标准：

1. 可通过 UI 创建、编辑、删除目标。
2. 可创建、编辑、更新 KR。
3. 可创建、编辑、删除项目。
4. 可把任务绑定项目。
5. 目标详情能看到 KR 进度和项目任务统计。
6. 自动化测试和截图验证通过。

---

## Phase 4：周计划 + 周报复盘

目标：实现从任务池到本周计划，再到今日执行和周报复盘的闭环。

### 4.1 修改范围

新增：

```text
app/modules/review_module.py
```

修改：

```text
app/main_window.py
app/widgets/navigation_bar.py
app/modules/todo_module.py
app/database.py
app/services/week_service.py
tests/test_lifebutler_smoke.py
tests/test_lifebutler_services.py
```

### 4.2 ReviewModule UI

页面分三块：

1. 顶部：ISO 年 / 周选择器、刷新按钮。
2. 左侧：本周任务列表。
3. 右侧：周报统计、三句复盘、保存 / 导出按钮。

本周任务表格列：

```text
任务 | 项目 | 象限 | 状态 | 今日日期 | 完成度 | 进展备注
```

按钮：

```text
从任务池加入本周
移出本周
标记为今日
取消今日
保存进展
生成周报
保存复盘
导出 Markdown
```

复盘输入框：

```text
本周做得好的
下周要改变的
下周承诺
```

### 4.3 加入本周

实现选择弹窗：

1. 列出所有 pending 任务。
2. 可按项目过滤。
3. 选择一条任务加入当前周。
4. 如果已存在同周记录，提示“已在本周计划中”，不重复插入。

### 4.4 标记为今日

从本周任务标记今日：

1. 调用 `db.mark_todo_today(task_id, quadrant, today)`。
2. quadrant 使用任务已有 `quadrant`，没有则 `q2`。
3. 调用 `db.update_weekly_task(..., today_task_date=today)`。

取消今日：

1. 只清空 `weekly_tasks.today_task_date`。
2. 不清空 `todos.today_date`，避免破坏用户今日四象限已有安排。

### 4.5 周报统计

`week_service.build_week_summary(db, year, week)` 返回：

```python
{
    "year": 2026,
    "week": 25,
    "task_total": 0,
    "task_done": 0,
    "task_completion_rate": 0,
    "pomodoro_minutes": 0,
    "exercise_minutes": 0,
    "income": 0.0,
    "expense": 0.0,
    "balance": 0.0,
    "deferred_task_count": 0,
    "radar": []
}
```

日期范围：

1. ISO week 周一到周日。
2. `pomodoro_sessions.started_at` 落在范围内。
3. `health_exercise.date` 落在范围内。
4. `records.date` 落在范围内。
5. 顺延任务：本周任务对应 todo 未完成，且 `today_date` 早于本周任一天或早于今天 3 天以上。

### 4.6 周报 Markdown

导出路径：

```text
outputs/week-review-YYYY-WW.md
```

不存在 `outputs/` 时自动创建。

Markdown 模板必须包含：

```markdown
# LifeButler 周报 YYYY-WW

## 自动统计

- 本周任务：已完成 A / 总计 B，完成率 C%
- 专注时间：X 分钟
- 运动时间：Y 分钟
- 收入：¥I
- 支出：¥E
- 结余：¥B
- 顺延任务：N 个

## 本周做得好的

...

## 下周要改变的

...

## 下周承诺

...

## 生活雷达

- ...
```

### 4.7 自动化测试

新增测试：

1. `ReviewModule` 可构造。
2. 同一任务同一周重复加入不会产生两条记录。
3. 标记今日后 `todos.today_date` 和 `weekly_tasks.today_task_date` 同步。
4. 周报 summary 在空库返回完整字段。
5. Markdown 渲染包含统计和三句复盘。
6. Markdown 导出能创建文件。

### 4.8 Screenshot 验证

截图：

1. 深色周报复盘页。
2. 浅色周报复盘页。
3. 从任务池加入本周弹窗。
4. 导出成功提示。

验收点：

1. 本周任务列表可读。
2. 统计卡片或统计文本不重叠。
3. 三个复盘输入框高度足够。
4. 导出按钮可见。
5. 空周和有数据周都能显示。

### 4.9 Phase 4 验收

通过标准：

1. 用户可从任务池加入本周。
2. 用户可从本周任务标记今日。
3. 用户可保存周复盘。
4. 用户可导出 Markdown。
5. 自动化测试和截图验证通过。

---

## Phase 5：快速收集箱

目标：用规则解析实现无 AI 的统一输入入口。

### 5.1 修改范围

修改：

```text
app/modules/dashboard_module.py
app/services/quick_capture_service.py
app/database.py
tests/test_lifebutler_services.py
```

新增：

```text
app/modules/quick_capture_dialog.py
```

### 5.2 解析规则

`parse_quick_capture(text, today)` 返回：

```python
{
    "raw": "...",
    "kind": "task" | "finance" | "exercise" | "memo",
    "confidence": "rule",
    "fields": {...}
}
```

规则优先级：

1. 含金额模式优先识别为 finance。
2. 含运动关键词和分钟识别为 exercise。
3. 含任务关键词识别为 task。
4. 其他识别为 memo。

金额模式：

```text
28元
28 元
¥28
￥28
28.5
```

运动关键词：

```text
跑步
步行
骑行
游泳
健身
瑜伽
运动
```

任务关键词：

```text
明天
今天
截止
完成
提交
复习
作业
报告
开发
修复
整理
```

### 5.3 确认弹窗

弹窗允许用户修改类型：

```text
保存为：任务 / 账单 / 运动 / 备忘录
```

不同类型字段：

任务：

```text
标题
截止日期
项目
象限
是否加入今日
```

账单：

```text
类型：支出 / 收入
类别
金额
日期
备注
```

运动：

```text
日期
运动类型
时长
```

备忘录：

```text
标题
分类
标签
内容
```

### 5.4 写入规则

任务：

1. 调用 `db.add_todo()`。
2. 默认 priority `medium`。
3. 用户勾选“加入今日”时调用 `mark_todo_today()`。

账单：

1. 默认 type `expense`。
2. category 默认“其他”。
3. amount 必须 > 0。

运动：

1. type 从关键词推断；无法推断则“其他”。
2. duration 默认解析到的分钟；无分钟时要求用户填写。

备忘录：

1. title 默认取原文前 20 个字符。
2. content 默认原文。
3. category 默认 `general`。

### 5.5 自动化测试

测试输入：

```text
午饭 28 元
跑步 30 分钟
明天提交数据库报告
想到一个目标地图功能
```

要求：

1. 四个示例解析正确。
2. 空字符串返回 invalid，不写库。
3. `commit_quick_capture()` 对四类记录都能写入临时库。
4. 加入今日的任务能出现在今日任务查询中。

### 5.6 Screenshot 验证

截图：

1. 首页快速收集输入框。
2. 任务确认弹窗。
3. 账单确认弹窗。
4. 运动确认弹窗。
5. 备忘录确认弹窗。

验收点：

1. 类型切换后字段正确变化。
2. 金额、日期、项目、象限控件完整显示。
3. 弹窗按钮可见。
4. 保存后首页统计能刷新。

### 5.7 Phase 5 验收

通过标准：

1. 首页输入框可完成四类收集。
2. 识别结果可人工修改。
3. 保存失败时内容不丢失，并给出明确提示。
4. 自动化测试和截图验证通过。

---

## Phase 6：CLI JSON 层

目标：实现最小“狗子式”本地可操作接口，供外部 Agent 使用。

### 6.1 修改范围

新增：

```text
app/cli.py
tests/test_lifebutler_cli.py
```

修改：

```text
README.md
```

新增根目录可执行脚本：

```text
lifebutler
```

脚本调用：

```python
from app.cli import main
```

### 6.2 命令范围

必须实现：

```bash
.venv/bin/python -m app.cli system capabilities --json
.venv/bin/python -m app.cli today --json
.venv/bin/python -m app.cli task list --json
.venv/bin/python -m app.cli task quick-capture --title "..." --json
.venv/bin/python -m app.cli goal list --json
.venv/bin/python -m app.cli review week --json
```

写操作支持：

```bash
--dry-run
```

`task quick-capture` 必须支持 `--dry-run`。

### 6.3 JSON 输出

成功：

```json
{
  "ok": true,
  "data": {},
  "meta": {
    "appVersion": "0.3.0",
    "schemaVersion": 4
  }
}
```

失败：

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "..."
  },
  "meta": {
    "appVersion": "0.3.0",
    "schemaVersion": 4
  }
}
```

错误码：

```text
INVALID_ARGUMENT
NOT_FOUND
DATABASE_ERROR
UNSUPPORTED_COMMAND
```

### 6.4 capabilities 输出

`system capabilities` 返回：

```python
{
    "commands": [
        "system capabilities",
        "today",
        "task list",
        "task quick-capture",
        "goal list",
        "review week"
    ],
    "enums": {
        "task_status": ["pending", "done"],
        "task_quadrant": ["q1", "q2", "q3", "q4"],
        "objective_status": ["active", "archived", "abandoned"],
        "project_status": ["planning", "active", "paused", "completed"]
    }
}
```

### 6.5 命令行为

`today`：

1. 调用 `overview_service.build_today_overview()`。
2. 不写库。

`task list`：

1. 支持 `--status pending|done|all`。
2. 默认 `all`。
3. 返回 `data.items` 和 `data.total`。

`task quick-capture`：

1. `--title` 必填。
2. 可选 `--due-date`、`--quadrant`、`--project`。
3. `--dry-run` 返回即将创建的数据，不写库。
4. 正式执行调用 `db.add_todo()`。

`goal list`：

1. 支持 `--status active|archived|abandoned|all`。
2. 返回目标列表。

`review week`：

1. 可选 `--year`、`--week`。
2. 默认当前 ISO 年周。
3. 返回 `week_service.build_week_summary()`。

### 6.6 自动化测试

使用 subprocess 或直接调用 `app.cli.main(argv)`，必须设置临时 `LIFEBUTLER_DB_PATH`。

测试：

1. capabilities JSON 可解析。
2. today 空库 JSON 字段完整。
3. task quick-capture dry-run 不写库。
4. task quick-capture 正式执行后 task list 能看到任务。
5. goal list 返回 `items` 和 `total`。
6. review week 返回 summary 字段。
7. 无效命令返回 `ok=false`。

### 6.7 Phase 6 验收

通过标准：

1. 所有 CLI 命令稳定输出 JSON。
2. CLI 不依赖 PyQt UI。
3. CLI 不触碰真实数据库。
4. README 记录 CLI 用法。
5. CLI 测试通过。

---

## Phase 7：备份、导出、README 更新

目标：实现用户验收前需要的备份、导出和说明文档。此阶段不执行 macOS `.app` 打包。

### 7.1 修改范围

新增：

```text
app/modules/settings_module.py
```

修改：

```text
app/main_window.py
app/widgets/navigation_bar.py
app/database.py
README.md
tests/test_lifebutler_smoke.py
```

### 7.2 设置模块

新增导航项：

```text
设置
```

设置模块包含：

1. 当前数据库路径。
2. schema version。
3. “备份数据库”按钮。
4. “打开备份目录”按钮。
5. “关于 LifeButler”信息。

备份按钮：

1. 调用现有 `db.backup_data()`。
2. 成功后弹窗显示备份路径。
3. 失败时弹窗显示错误。

### 7.3 周报 Markdown 导出补齐

确认：

1. `outputs/` 不存在时自动创建。
2. 导出成功后提示路径。
3. README 说明导出文件位置。

### 7.4 README 更新

README 必须新增：

1. 三期功能说明。
2. 首页驾驶舱说明。
3. 目标 / KR / 项目说明。
4. 周计划 / 周报说明。
5. 快速收集说明。
6. CLI 用法。
7. 备份和 Markdown 导出说明。
8. 测试命令。
9. 说明 `.app` 打包在用户验收后执行。

### 7.5 自动化测试

新增测试：

1. `SettingsModule` 可构造。
2. 备份 API 在临时库下生成备份文件。
3. README 中包含 CLI、测试、验收后打包说明关键词。

### 7.6 Screenshot 验证

截图：

1. 深色设置页。
2. 浅色设置页。
3. 备份成功提示。

验收点：

1. 数据库路径显示不挤压页面。
2. 备份按钮可见。
3. 关于信息可读。

### 7.7 Phase 7 验收

通过标准：

1. 设置页可用。
2. 备份按钮可在临时库下生成备份。
3. README 更新完整。
4. 自动化测试和截图验证通过。
5. 未执行打包。

---

## Phase 8：功能验收准备与 Screenshot 验证

目标：在交给用户验收前，完成自动化验证、CLI 验证、UI screenshot 验证和验收材料整理，尽量减少用户最后排查工作量。

### 8.1 修改范围

新增：

```text
scripts/capture_ui_screenshots.py
tests/test_lifebutler_ui_screenshots.py
```

可能修改：

```text
README.md
```

### 8.2 Screenshot 脚本要求

`scripts/capture_ui_screenshots.py` 必须：

1. 设置 `QT_QPA_PLATFORM=offscreen`，可在无真实窗口时运行。
2. 使用 `tempfile.TemporaryDirectory()` 和 `LIFEBUTLER_DB_PATH` 创建临时数据库。
3. 清理 `DatabaseManager` singleton。
4. 注入 demo 数据：
   - 至少 1 个 objective。
   - 至少 2 个 KR。
   - 至少 1 个 project。
   - 至少 4 个今日任务，覆盖 q1-q4。
   - 至少 1 条 completed pomodoro session。
   - 至少 1 条收入和 2 条支出。
   - 至少 1 条运动记录。
   - 至少 1 条备忘录。
   - 至少 1 条 weekly_task 和 weekly_review。
5. 构造 `MainWindow`。
6. 分别切换深色和浅色主题。
7. 切换主要页面并调用 `QWidget.grab()` 保存 PNG。
8. 输出目录：

```text
outputs/ui-qa/YYYYMMDD-HHMMSS/
```

截图文件名：

```text
dark-dashboard.png
light-dashboard.png
dark-goals.png
light-goals.png
dark-todo-today.png
light-todo-today.png
dark-review.png
light-review.png
dark-settings.png
light-settings.png
quick-capture-task-dialog.png
quick-capture-finance-dialog.png
quick-capture-exercise-dialog.png
quick-capture-memo-dialog.png
```

### 8.3 Screenshot 自动检查

脚本保存每张图后检查：

1. 文件存在。
2. 文件大小 > 10 KB。
3. 图片宽度 >= 900，高度 >= 600。
4. 图片不是纯色：采样像素颜色数量 > 20。

自动检查失败时，脚本 exit code 非 0。

### 8.4 Screenshot 人工检查清单

开发者必须打开截图目录，逐项确认：

1. 页面主标题可见。
2. 关键按钮可见。
3. 表格、卡片、输入框不重叠。
4. 文字没有明显截断。
5. 深色主题对比度足够。
6. 浅色主题对比度足够。
7. 图表不是空白。
8. 快速收集弹窗字段完整。
9. 设置页数据库路径不会挤爆布局。

检查结果写入：

```text
outputs/ui-qa/YYYYMMDD-HHMMSS/QA_NOTES.md
```

`QA_NOTES.md` 模板：

```markdown
# UI QA Notes

- Screenshot directory: ...
- py_compile: pass/fail
- unittest: pass/fail
- CLI JSON smoke: pass/fail

## Pages

- Dashboard dark/light: pass/fail
- Goals dark/light: pass/fail
- Todo today dark/light: pass/fail
- Review dark/light: pass/fail
- Settings dark/light: pass/fail
- Quick capture dialogs: pass/fail

## Issues Found

- None
```

### 8.5 全量验证命令

执行：

```bash
git status --short
.venv/bin/python -m py_compile main.py app/*.py app/modules/*.py app/widgets/*.py app/services/*.py app/cli.py scripts/*.py tests/*.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m app.cli system capabilities --json
.venv/bin/python -m app.cli today --json
.venv/bin/python scripts/capture_ui_screenshots.py
```

CLI 输出需要人工确认：

1. 是合法 JSON。
2. `ok` 为 true。
3. `meta.schemaVersion` 为 4。

### 8.6 Phase 8 验收

通过标准：

1. 全量验证命令通过。
2. screenshot 目录存在。
3. `QA_NOTES.md` 存在且无未解决问题。
4. 没有运行 macOS `.app` 打包。

---

## Phase 9：用户验收

目标：将完整功能成果交给用户检查。用户确认前不得进入打包阶段。

### 9.1 验收前交付材料

开发者最终回复必须包含：

1. 功能完成说明。
2. 自动化测试命令和结果摘要。
3. CLI 示例命令和结果摘要。
4. screenshot 目录路径。
5. `QA_NOTES.md` 路径。
6. 本地运行命令：

```bash
.venv/bin/python main.py
```

7. 用户重点验收页面列表：
   - 首页驾驶舱。
   - 目标管理。
   - 待办任务池和今日四象限。
   - 周报复盘。
   - 快速收集弹窗。
   - 设置 / 备份。

### 9.2 用户验收清单

请用户检查：

1. 首页是否符合“今日入口”的预期。
2. 目标 / KR / 项目是否能表达真实目标推进。
3. 任务绑定项目是否顺手。
4. 周计划到今日四象限是否自然。
5. 周报统计是否清楚。
6. 快速收集识别是否符合直觉。
7. 深浅主题是否都能接受。
8. 是否存在 UI 重叠、截断、按钮不可见。

### 9.3 验收阻塞处理

如果用户提出问题：

1. 修复问题。
2. 重新运行 Phase 8 全量验证。
3. 更新 screenshot 和 `QA_NOTES.md`。
4. 再次提交用户验收。

只有用户明确表示“可以打包”或等价确认后，才能进入 Phase 10。

---

## Phase 10：用户确认后再打包 macOS `.app`

目标：在用户验收功能成果后，生成最终可双击运行的 macOS `.app`。

### 10.1 进入条件

必须同时满足：

1. Phase 8 全量验证通过。
2. Phase 9 用户验收通过。
3. 用户明确要求或确认可以打包。

未满足以上条件，不执行打包。

### 10.2 修改范围

新增：

```text
scripts/package_macos.sh
requirements-dev.txt
```

修改：

```text
app/database.py
README.md
.gitignore
```

如果提交 `LifeButler.spec`，需要从 `.gitignore` 移除 `*.spec` 或增加例外。

### 10.3 打包数据库路径适配

修改 `DatabaseManager` 路径选择：

1. 如果存在 `LIFEBUTLER_DB_PATH`，优先使用该路径。
2. 如果检测到 PyInstaller 环境，使用：

```text
~/Library/Application Support/LifeButler/lifebutler.db
```

3. 否则源码运行继续使用仓库内：

```text
data/lifebutler.db
```

PyInstaller 检测方式：

```python
getattr(sys, "frozen", False)
```

要求：

1. 自动创建用户目录。
2. 测试仍可通过 `LIFEBUTLER_DB_PATH` 覆盖。
3. 不自动迁移仓库内旧数据到用户目录。

### 10.4 requirements-dev

新增：

```text
requirements-dev.txt
```

内容：

```text
-r requirements.txt
pyinstaller>=6.0
```

### 10.5 package_macos.sh

脚本路径：

```text
scripts/package_macos.sh
```

脚本要求：

1. 使用项目 `.venv/bin/python` 和 `.venv/bin/pyinstaller`。
2. 如果 `.venv/bin/pyinstaller` 不存在，提示：

```bash
.venv/bin/pip install -r requirements-dev.txt
```

3. 清理 `build/` 和 `dist/`。
4. 打包入口 `main.py`。
5. App 名称 `LifeButler`。
6. 包含 `app/assets`。
7. 输出 `dist/LifeButler.app`。

建议命令：

```bash
.venv/bin/pyinstaller \
  --name LifeButler \
  --windowed \
  --noconfirm \
  --clean \
  --add-data "app/assets:app/assets" \
  main.py
```

### 10.6 README 打包说明

README 新增：

1. 打包发生在用户验收后。
2. 安装打包依赖：

```bash
.venv/bin/pip install -r requirements-dev.txt
```

3. 打包：

```bash
./scripts/package_macos.sh
```

4. 产物：

```text
dist/LifeButler.app
```

5. 打包 App 数据库位置：

```text
~/Library/Application Support/LifeButler/lifebutler.db
```

### 10.7 打包验证

执行：

```bash
.venv/bin/python -m py_compile main.py app/*.py app/modules/*.py app/widgets/*.py app/services/*.py app/cli.py scripts/*.py tests/*.py
.venv/bin/python -m unittest discover -s tests -v
./scripts/package_macos.sh
```

手动验证：

1. 双击 `dist/LifeButler.app`。
2. 首页可打开。
3. 记账、目标、待办、健康、备忘录、周报、设置都可切换。
4. 新建一条任务，退出后重开仍存在。
5. 图表和 SVG 箭头显示正常。
6. 备份按钮可生成备份。

打包后截图：

```text
outputs/app-qa/YYYYMMDD-HHMMSS/
```

至少保存：

```text
app-dashboard.png
app-goals.png
app-todo.png
app-review.png
app-settings.png
```

### 10.8 Phase 10 验收

通过标准：

1. `dist/LifeButler.app` 存在。
2. `.app` 可双击运行。
3. App 内新增数据重启后仍存在。
4. 打包 App 截图留存。
5. 打包产物不提交 Git。
6. 打包脚本、README、必要配置提交。

---

## 最终交付清单

功能验收前必须完成：

1. Phase 1-8 全部完成。
2. 自动化测试通过。
3. CLI JSON 验证通过。
4. UI screenshot 验证通过。
5. `QA_NOTES.md` 无未解决问题。
6. 用户可通过 `.venv/bin/python main.py` 运行验收。

功能验收后、用户确认打包时完成：

1. Phase 10 打包。
2. `dist/LifeButler.app` 双击运行验证。
3. 打包 App 截图留存。

禁止事项：

1. 不提交 `data/*.db*`。
2. 不提交 `outputs/`。
3. 不提交 `.venv/`。
4. 不提交 `build/`、`dist/`。
5. 不在用户验收前打包。

