# LifeButler 智能生活管家

LifeButler 是一个本地生活管理桌面应用，使用 PyQt6 构建界面，SQLite 保存本地数据，并通过 matplotlib 绘制统计图表。项目围绕“计划 - 执行 - 记录 - 反馈”的生活管理闭环，整合记账、待办、今日四象限、番茄钟、健康记录和备忘录等功能。

当前项目是源码运行形态，不包含 Python 运行时和第三方依赖包。首次运行前需要在本机创建虚拟环境并安装依赖。

## 功能模块

- 首页驾驶舱：快速收集入口、今日三件事、今日专注、本月财务、近 7 天运动、今日四象限摘要和生活雷达。
- 记账管理：收支记录、月度收入/支出/结余统计、分类占比图。
- 目标管理：Objective、KR、Project 三级推进链路，KR 进度和项目状态管理。
- 待办事项：任务池、今日四象限、任务完成/恢复、逾期提示。
- 周计划 / 周报复盘：任务加入本周、标记今日、保存进展、三句复盘和 Markdown 导出。
- 快速收集箱：用本地规则识别任务、账单、运动和备忘录，可在保存前确认字段。
- 番茄钟：绑定今日任务，记录专注 session、番茄数和累计分钟。
- 健康记录：体重/BMI、运动打卡、趋势图和周统计。
- 备忘录：分类、搜索、置顶和 Markdown 预览。
- 设置与基础能力：数据库路径查看、手动备份、深浅主题切换、系统托盘、SQLite schema migration、迁移前自动备份、轻量 smoke tests。

## 三期功能说明

当前源码形态已经包含后续开发的核心三期能力：第一期补齐目标 / KR / 项目与周计划数据链路；第二期提供首页驾驶舱、生活雷达和快速收集；第三期提供 CLI JSON、备份与周报导出，供用户验收后再进入 macOS `.app` 打包。

## 环境要求

- Python 3.10 或更高版本。
- macOS / Windows / Linux 均可尝试运行；当前主要在 macOS 上测试。
- Python 依赖：
  - PyQt6 >= 6.5.0
  - matplotlib >= 3.7.0

依赖清单见根目录 `requirements.txt`。

## 安装依赖

在项目根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell 可使用：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 本地运行

终端启动：

```bash
source .venv/bin/activate
python main.py
```

或直接使用虚拟环境中的解释器：

```bash
.venv/bin/python main.py
```

macOS 也可以双击根目录中的启动脚本：

```text
启动 LifeButler.command
```

该脚本会使用项目内的 `.venv/bin/python` 启动应用。如果未创建虚拟环境，它会提示先安装依赖。

## 退出方式

- 在启动程序的 Terminal 窗口按 `Ctrl+C`。
- 或使用系统托盘菜单里的“退出”。

点窗口左上角关闭按钮会隐藏到托盘，不等于退出进程。

## 环境变量

默认数据库路径：

```text
data/lifebutler.db
```

测试或临时运行时可以通过 `LIFEBUTLER_DB_PATH` 指定数据库文件，避免污染正式本地数据：

```bash
LIFEBUTLER_DB_PATH=/tmp/lifebutler-test.db .venv/bin/python main.py
```

自动化测试已经使用临时数据库路径，不会写入 `data/lifebutler.db`。

## 常见命令

### 测试命令

语法检查：

```bash
.venv/bin/python -m py_compile main.py app/*.py app/modules/*.py app/widgets/*.py tests/*.py
```

运行测试：

```bash
.venv/bin/python -m unittest discover -s tests -v
```

查看依赖：

```bash
cat requirements.txt
```

## CLI JSON 接口

项目提供最小本地 JSON CLI，便于脚本或外部 Agent 读取今日概览、任务、目标和周报统计。测试或临时调用建议设置 `LIFEBUTLER_DB_PATH` 指向临时数据库，避免影响正式数据。

```bash
.venv/bin/python -m app.cli system capabilities --json
.venv/bin/python -m app.cli today --json
.venv/bin/python -m app.cli task list --json
.venv/bin/python -m app.cli task quick-capture --title "复盘本周目标" --dry-run --json
.venv/bin/python -m app.cli goal list --json
.venv/bin/python -m app.cli review week --json
```

根目录也提供 `lifebutler` 脚本，等价调用 `app.cli`：

```bash
./lifebutler system capabilities --json
```

## 周报导出与备份

周报复盘页的“导出 Markdown”会写入：

```text
outputs/week-review-YYYY-WW.md
```

设置页的“备份数据库”会在当前数据库同目录生成 `lifebutler_backup_YYYYMMDD_HHMMSS.db`。开发和测试时请继续使用 `LIFEBUTLER_DB_PATH` 指向临时库，不要直接操作 `data/lifebutler.db*`。

## 打包说明

macOS `.app` 打包必须在用户验收后执行。当前交付目标是源码运行验收：

```bash
.venv/bin/python main.py
```

用户明确确认“可以打包”后，才进入后续打包阶段。

## 目录结构

```text
LifeButler/
├── main.py                    # 应用入口
├── requirements.txt           # Python 依赖
├── 启动 LifeButler.command      # macOS 双击启动脚本
├── app/
│   ├── application.py         # QApplication 子类、托盘、生命周期
│   ├── database.py            # SQLite 连接、schema 迁移、数据 API
│   ├── main_window.py         # 主窗口、导航、全局主题
│   ├── assets/                # Qt stylesheet 使用的 SVG 图标
│   ├── modules/               # 记账、待办、健康、备忘录模块
│   └── widgets/               # 导航栏和图表组件
├── tests/                     # smoke tests
├── docs/
│   ├── 功能简明手册.md          # 用户测试说明
│   ├── AI使用指引.md            # Agent/CLI 使用说明
│   ├── Windows打包说明.md       # Windows 便携包构建说明
│   └── reports/               # 阶段报告与演示材料
├── CHANGELOG.md               # 变更日志
└── app/README.md              # 更细的 app 内部结构说明
```

运行后会自动创建或更新 `data/lifebutler.db`。该文件包含本地用户数据，不应提交到 GitHub。

## 数据库与迁移

`DatabaseManager` 是单例，所有业务模块共享同一个 SQLite 连接。数据库当前目标 schema version 为 5：

- version 1：基础表结构。
- version 2：增加今日四象限任务字段和 `pomodoro_sessions`。
- version 3：兼容旧预算表约束迁移；预算界面当前已移除。
- version 4：增加目标、KR、项目、周计划和周复盘表。
- version 5：移除任务与项目的绑定字段，项目不再作为任务容器。

旧数据库升级前会自动备份到 `data/lifebutler_backup_before_migration_*.db`。维护数据库结构时应新增 migration，不要直接修改已上线表结构后跳过迁移。

## 版本控制注意事项

仓库会提交源码、测试、SVG assets、说明文档、启动脚本和依赖清单。以下内容不会提交：

- `.venv/` 等本地虚拟环境。
- `.env`、`.env.*` 等本地环境变量文件。
- `data/*.db`、`data/*.db-wal`、`data/*.db-shm` 等本地数据库和运行时文件。
- `outputs/` 目录下的生成报告、PPT 或临时导出。
- `__pycache__/`、`.DS_Store`、构建产物和编辑器缓存。

如需共享配置模板，请使用 `.env.example`，不要提交真实密钥、token、密码或个人数据。

## 维护建议

- 新增或修改数据库字段时，补充 migration 和测试。
- 新增图表优先使用 `ChartWidget`，保持深浅主题联动。
- UI 全局样式优先在 `main_window.py` 统一维护。
- 今日四象限的完整数据逻辑来自 `todos.today_date`、`todos.quadrant` 和 `pomodoro_sessions`，不要用手工统计字段替代。
