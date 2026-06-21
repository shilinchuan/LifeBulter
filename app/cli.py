import json
import sys

from app.database import DatabaseManager
from app.services.overview_service import build_today_overview
from app.services.week_service import build_week_summary, current_year_week


APP_VERSION = "0.3.0"


def _meta() -> dict:
    return {"appVersion": APP_VERSION, "schemaVersion": DatabaseManager.TARGET_SCHEMA_VERSION}


def _ok(data: dict) -> dict:
    return {"ok": True, "data": data, "meta": _meta()}


def _error(code: str, message: str) -> dict:
    return {"ok": False, "error": {"code": code, "message": message}, "meta": _meta()}


def _value(argv: list[str], name: str, default=None):
    if name not in argv:
        return default
    index = argv.index(name)
    if index + 1 >= len(argv):
        raise ValueError(f"{name} 缺少参数")
    return argv[index + 1]


def _has(argv: list[str], name: str) -> bool:
    return name in argv


def _capabilities() -> dict:
    return {
        "commands": [
            "system capabilities",
            "today",
            "task list",
            "task quick-capture",
            "goal list",
            "review week",
        ],
        "enums": {
            "task_status": ["pending", "done"],
            "task_quadrant": ["q1", "q2", "q3", "q4"],
            "objective_status": ["active", "archived", "abandoned"],
            "project_status": ["planning", "active", "paused", "completed"],
        },
    }


def _handle(argv: list[str]) -> dict:
    argv = [arg for arg in argv if arg != "--json"]
    db = DatabaseManager()
    try:
        if argv[:2] == ["system", "capabilities"]:
            return _ok(_capabilities())
        if argv[:1] == ["today"]:
            return _ok(build_today_overview(db))
        if argv[:2] == ["task", "list"]:
            status = _value(argv, "--status", "all")
            if status not in ("pending", "done", "all"):
                return _error("INVALID_ARGUMENT", "status 必须是 pending、done 或 all")
            items = db.get_todos(status)
            return _ok({"items": items, "total": len(items)})
        if argv[:2] == ["task", "quick-capture"]:
            title = _value(argv, "--title", "")
            if not title:
                return _error("INVALID_ARGUMENT", "--title 必填")
            due_date = _value(argv, "--due-date", "")
            quadrant = _value(argv, "--quadrant", "q2")
            if quadrant not in ("q1", "q2", "q3", "q4"):
                return _error("INVALID_ARGUMENT", "quadrant 必须是 q1、q2、q3 或 q4")
            data = {
                "title": title,
                "priority": "medium",
                "due_date": due_date,
                "quadrant": quadrant,
                "status": "pending",
            }
            if _has(argv, "--dry-run"):
                return _ok({"dryRun": True, "task": data})
            task_id = db.add_todo(title, "medium", due_date, quadrant, "")
            data["id"] = task_id
            return _ok({"task": data})
        if argv[:2] == ["goal", "list"]:
            status = _value(argv, "--status", "active")
            if status not in ("active", "archived", "abandoned", "all"):
                return _error("INVALID_ARGUMENT", "status 必须是 active、archived、abandoned 或 all")
            items = db.get_objectives(status)
            return _ok({"items": items, "total": len(items)})
        if argv[:2] == ["review", "week"]:
            year = int(_value(argv, "--year", 0) or 0)
            week = int(_value(argv, "--week", 0) or 0)
            if not year or not week:
                year, week = current_year_week()
            return _ok(build_week_summary(db, year, week))
        return _error("UNSUPPORTED_COMMAND", "不支持的命令")
    except ValueError as exc:
        return _error("INVALID_ARGUMENT", str(exc))
    except Exception as exc:
        return _error("DATABASE_ERROR", str(exc))


def main(argv: list[str] | None = None) -> int:
    result = _handle(list(argv if argv is not None else sys.argv[1:]))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
