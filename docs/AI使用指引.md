# LifeButler AI / Agent 使用指引

本文档给 AI Agent 或脚本使用 LifeButler 当前源码版 CLI。所有命令都应返回 JSON，便于稳定解析。

## 基本规则

- 必须带 `--json`。
- 写操作建议先加 `--dry-run` 看返回结构，再正式执行。
- 不要直接读取、修改、删除或重置 `data/lifebutler.db`、`data/lifebutler.db-wal`、`data/lifebutler.db-shm`。
- 临时演示或测试请设置 `LIFEBUTLER_DB_PATH` 指向临时数据库。
- 当前 schema version 为 5。
- 从 schema v5 开始，任务不绑定项目；Project 只属于目标管理。

## CLI 入口

在项目根目录运行：

```bash
.venv/bin/python lifebutler system capabilities --json
```

也可以使用模块入口：

```bash
.venv/bin/python -m app.cli system capabilities --json
```

## 当前可用命令

以 `system capabilities --json` 为准，当前包括：

```text
system capabilities
today
task list
task quick-capture
goal list
review week
```

## 常用命令示例

查看能力：

```bash
.venv/bin/python lifebutler system capabilities --json
```

查看今日概览：

```bash
.venv/bin/python lifebutler today --json
```

查看任务：

```bash
.venv/bin/python lifebutler task list --json
.venv/bin/python lifebutler task list --status pending --json
.venv/bin/python lifebutler task list --status done --json
```

创建任务前 dry-run：

```bash
.venv/bin/python lifebutler task quick-capture \
  --title "明天提交数据库报告" \
  --due-date 2026-06-19 \
  --quadrant q2 \
  --dry-run \
  --json
```

正式创建任务：

```bash
.venv/bin/python lifebutler task quick-capture \
  --title "明天提交数据库报告" \
  --due-date 2026-06-19 \
  --quadrant q2 \
  --json
```

查看目标：

```bash
.venv/bin/python lifebutler goal list --json
.venv/bin/python lifebutler goal list --status all --json
```

查看本周统计：

```bash
.venv/bin/python lifebutler review week --json
```

查看指定周：

```bash
.venv/bin/python lifebutler review week --year 2026 --week 25 --json
```

## 输出结构

成功：

```json
{
  "ok": true,
  "data": {},
  "meta": {
    "appVersion": "0.3.0",
    "schemaVersion": 5
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
    "schemaVersion": 5
  }
}
```

## 枚举值

任务状态：

```text
pending
done
all
```

今日四象限：

```text
q1
q2
q3
q4
```

目标状态：

```text
active
archived
abandoned
all
```

## 临时库演示

如果需要不污染本机数据：

```bash
tmpdir=$(mktemp -d)
export LIFEBUTLER_DB_PATH="$tmpdir/lifebutler-demo.db"
.venv/bin/python lifebutler system capabilities --json
.venv/bin/python lifebutler task quick-capture --title "演示任务" --dry-run --json
```

## Agent 注意事项

- 不要假设存在全局 `rzb` 命令；当前压缩包内的稳定入口是 `.venv/bin/python lifebutler`。
- 不要传 `--project` 给任务命令；任务和项目已经解耦。
- 如果返回 `INVALID_ARGUMENT`，修正参数后重试。
- 如果返回 `DATABASE_ERROR`，把原始错误报告给用户，不要直接修数据库文件。
