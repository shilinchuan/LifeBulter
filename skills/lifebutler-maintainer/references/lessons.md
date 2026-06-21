# LifeButler Lessons

Reusable lessons discovered while maintaining LifeButler. Keep entries concise and grounded in verified repository behavior.

## 2026-06-17

- Tests already isolate local data by setting `LIFEBUTLER_DB_PATH` and clearing the `DatabaseManager` singleton in `tests/test_lifebutler_smoke.py`; follow that pattern for new database tests.
- The current verification baseline is `py_compile` plus `unittest discover`; both commands are documented in `README.md` and `app/README.md`.
- The real local SQLite database and WAL/SHM files live under `data/` and are ignored by `.gitignore`; development tasks should not inspect or mutate them directly.
- SQLite accepts a `commit` result key when quoted, but DDL/DML must quote the column as `"commit"` because `COMMIT` is a transaction keyword; see `weekly_reviews` in `app/database.py`.
- During offscreen UI QA, hidden matplotlib canvases can be zero-sized. Theme changes should update all `ChartWidget` palettes but only refresh the visible module; hidden chart pages redraw when navigated to.
- For PyQt table rows, store internal IDs in the first visible item's `Qt.UserRole` instead of using hidden ID columns; this avoids clipped header fragments and unnecessary horizontal scrollbars.
- Schema v5 removes task-project binding entirely: `todos` has no `project_id`, Project is an OKR object only, and task UI/CLI should not reintroduce project selection.
- When packaging files with Chinese names, prefer Python `zipfile` over the system `zip` command; in this environment `zip` mangled UTF-8 filenames even though extraction checks should preserve them.
- Packaged macOS `.app` runs with frozen paths; `DatabaseManager` should default user data to `~/Library/Application Support/LifeButler/data/lifebutler.db` and keep `LIFEBUTLER_DB_PATH` for tests, otherwise the app may create data inside the bundle.
