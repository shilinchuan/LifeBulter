# LifeButler Codex Guide

LifeButler is a local desktop life-management app built with PyQt6, SQLite, and matplotlib. Treat this repository as a desktop GUI project, not a web app.

## Before Work

- For LifeButler maintenance, optimization, refactoring, debugging, tests, packaging, or documentation tasks, read `skills/lifebutler-maintainer/SKILL.md` first.
- Prefer existing module boundaries:
  - `app/database.py` owns SQLite connections, schema migrations, and data APIs.
  - `app/main_window.py` owns the main window, global stylesheet, and theme propagation.
  - `app/modules/` owns feature pages: account, todo, health, memo.
  - `app/widgets/chart_widget.py` owns matplotlib chart rendering.

## Data Safety

- Do not directly edit, inspect with SQL, reset, delete, or overwrite the user's real database files under `data/`.
- Tests and experiments must use temporary databases, usually through the existing test setup or `LIFEBUTLER_DB_PATH`.
- If changing schema, add a forward migration instead of only editing `CREATE TABLE`, and add or update migration coverage.
- Current-version compatibility is the default target. Historical local databases from older development versions are not important unless the user explicitly asks to preserve them.
- Be conservative when deleting current fields, tables, data APIs, UI entries, tests, or documentation. If user-visible behavior or current-version data could be affected, stop and ask first.
- Keep `data/*.db`, WAL/SHM files, generated reports, virtualenvs, caches, and local secrets out of version control.

## Implementation Rules

- Keep changes scoped to the requested behavior; avoid unrelated refactors.
- Before changing code, identify the impact surface: UI, database, tests, docs, packaging, or shared infrastructure.
- Do not make implicit product decisions. If a change affects feature scope, data meaning, user workflow, deletion, or other material behavior, stop and ask the user.
- If any material uncertainty remains about scope, behavior, data, tests, or delivery, explain the issue and ask before deciding.
- Reuse `ChartWidget` for new charts so dark/light theme switching stays consistent.
- Keep broad Qt stylesheet changes centralized in `app/main_window.py` unless a widget-local style is clearly isolated.
- Preserve the today-task model: `todos.today_date`, `todos.quadrant`, and `pomodoro_sessions` are the source of truth for today's quadrants and focus stats.
- New or changed UI must work in both dark and light themes.
- Button, dialog, status-bar, and empty-state text should stay concise and match the existing Chinese desktop-app tone.
- Avoid adding large dependencies unless the user explicitly accepts the tradeoff.

## Verification

After code changes, prefer running:

```bash
.venv/bin/python -m py_compile main.py app/*.py app/modules/*.py app/widgets/*.py tests/*.py
.venv/bin/python -m unittest discover -s tests -v
```

If a command cannot be run, explain why and name the residual risk.

For PyQt UI changes, include a short manual acceptance path in the final response: what to open, where to click, and what the user should see.

## Learning Loop

- At the end of each task, check whether a reusable LifeButler lesson was discovered.
- Do not turn one-off user preferences, temporary tradeoffs, or uncertain interpretations into permanent rules.
