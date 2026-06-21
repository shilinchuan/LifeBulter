---
name: lifebutler-maintainer
description: Maintain, optimize, refactor, debug, test, package, or document the LifeButler PyQt6 desktop app. Use for work touching LifeButler's PyQt UI, SQLite data layer, migrations, matplotlib charts, todo quadrants, pomodoro flow, local data safety, smoke tests, packaging, or project documentation.
---

# LifeButler Maintainer

Use this skill before making substantive changes to the LifeButler repository.

## Core Context

LifeButler is a local PyQt6 desktop application backed by SQLite and matplotlib. The app is source-run from `main.py`; the user's real local data lives under `data/` and must not be touched during development or tests.

Read `references/lessons.md` at the start of each task. Add to it only when a lesson is reusable and grounded in verified repository behavior.

## Workflow

1. Read the smallest useful context:
   - Start with `README.md`, `app/README.md`, and the files directly related to the request.
   - For database work, read `app/database.py` and relevant migration tests.
   - For UI work, read the target module plus `app/main_window.py` and `app/widgets/chart_widget.py` when theme or chart behavior is involved.
2. Locate the impact surface:
   - Identify whether the change touches data schema, data APIs, one feature module, shared widgets, global theme, tests, packaging, or docs.
   - Keep edits inside existing ownership boundaries unless the request requires a cross-cutting change.
3. Pass the uncertainty gate:
   - If scope, product behavior, data meaning, current-version compatibility, tests, delivery impact, or deletion safety is materially unclear, stop and ask the user.
   - Do not make implicit product decisions about feature tradeoffs, user workflows, data semantics, or irreversible deletion.
4. Make small, reversible changes:
   - Avoid unrelated refactors.
   - Do not edit or query the real `data/lifebutler.db`.
   - Use temporary database paths for experiments.
5. Validate:
   - Prefer `py_compile` plus unittest smoke tests:
     ```bash
     .venv/bin/python -m py_compile main.py app/*.py app/modules/*.py app/widgets/*.py tests/*.py
     .venv/bin/python -m unittest discover -s tests -v
     ```
   - If GUI visual behavior changed and screenshot tooling is available, capture or inspect the affected window when practical.
6. Report:
   - Summarize changed behavior, verification commands, and remaining risks.
   - Mention any command that could not be run.
   - For PyQt UI changes, include a manual acceptance path: what to open, where to click, and what the user should see.

## LifeButler Guardrails

- `DatabaseManager` is a singleton; tests that change `LIFEBUTLER_DB_PATH` must reset the singleton.
- Current-version compatibility is the default target. Historical local databases from older development versions are not important unless the user asks to preserve them.
- Schema changes require updating current creation logic, data APIs, and tests as needed. Add a migration when current-version local databases need to move forward.
- Be conservative when deleting current fields, tables, data APIs, UI entries, tests, or documentation. If user-visible behavior or current-version data could be affected, stop and ask first.
- `todos.today_date`, `todos.quadrant`, and `pomodoro_sessions` define the today-quadrant and pomodoro model.
- Theme switching must keep Qt widgets and matplotlib charts in sync.
- New or changed UI must work in both dark and light themes.
- Button, dialog, status-bar, and empty-state text should stay concise and match the existing Chinese desktop-app tone.
- Generated artifacts under `outputs/`, local database files under `data/`, and `.venv/` are not source files.

## End-of-Task Learning Loop

At the end of each task, decide whether the work revealed a reusable lesson:

- If it is a verified repository fact, append a concise dated entry to `references/lessons.md`.
- If it is a user preference, uncertain interpretation, or one-off situation, do not write it silently. Suggest it in the final response and wait for user confirmation.
- Do the learning-loop check every time, even when no lesson is added.
- Keep lessons short and operational: what to do, when it applies, and the evidence or file that established it.
- Do not duplicate lessons already present.
