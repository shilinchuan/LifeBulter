import re
from datetime import date, timedelta


MONEY_RE = re.compile(r"(?:[¥￥]\s*)?(\d+(?:\.\d+)?)\s*(?:元|[rR])?")
MINUTES_RE = re.compile(r"(\d+)\s*(?:分钟|分|min|m)")
EXERCISE_WORDS = ("跑步", "步行", "骑行", "游泳", "健身", "瑜伽", "运动")
TASK_WORDS = ("明天", "今天", "截止", "完成", "提交", "复习", "作业", "报告", "开发", "修复", "整理")


def parse_quick_capture(text: str, today: str | None = None) -> dict:
    raw = (text or "").strip()
    today_obj = date.fromisoformat(today) if today else date.today()
    if not raw:
        return {"raw": raw, "kind": "invalid", "confidence": "rule", "fields": {}}
    money = MONEY_RE.search(raw)
    minutes = MINUTES_RE.search(raw)
    exercise_type = next((word for word in EXERCISE_WORDS if word in raw), "")
    has_money_signal = bool(money and ("元" in raw or "¥" in raw or "￥" in raw or re.search(r"\d+(?:\.\d+)?\s*[rR]\b", raw) or "." in money.group(1)))
    if money and has_money_signal and not (exercise_type and minutes):
        return {
            "raw": raw,
            "kind": "finance",
            "confidence": "rule",
            "fields": {
                "type": "expense",
                "category": "其他",
                "amount": float(money.group(1)),
                "date": today_obj.isoformat(),
                "note": raw,
            },
        }
    if exercise_type and minutes:
        return {
            "raw": raw,
            "kind": "exercise",
            "confidence": "rule",
            "fields": {
                "date": today_obj.isoformat(),
                "type": exercise_type,
                "duration": int(minutes.group(1)),
            },
        }
    if any(word in raw for word in TASK_WORDS):
        due_date = today_obj.isoformat()
        if "明天" in raw:
            due_date = (today_obj + timedelta(days=1)).isoformat()
        return {
            "raw": raw,
            "kind": "task",
            "confidence": "rule",
            "fields": {
                "title": raw,
                "due_date": due_date,
                "priority": "medium",
                "quadrant": "q2",
                "add_to_today": "今天" in raw,
            },
        }
    return {
        "raw": raw,
        "kind": "memo",
        "confidence": "rule",
        "fields": {
            "title": raw[:20],
            "content": raw,
            "category": "general",
            "tags": "",
        },
    }


def commit_quick_capture(db, parsed: dict, edited_fields: dict | None = None) -> dict:
    kind = parsed.get("kind")
    if kind == "invalid":
        raise ValueError("收集内容不能为空")
    fields = dict(parsed.get("fields") or {})
    fields.update(edited_fields or {})
    if kind == "task":
        task_id = db.add_todo(
            fields["title"],
            fields.get("priority", "medium"),
            fields.get("due_date", ""),
            fields.get("quadrant", "q2"),
            "",
        )
        if fields.get("add_to_today"):
            db.mark_todo_today(task_id, fields.get("quadrant", "q2"), fields.get("today_date") or date.today().isoformat())
        return {"kind": kind, "id": task_id}
    if kind == "finance":
        amount = float(fields.get("amount") or 0)
        if amount <= 0:
            raise ValueError("金额必须大于 0")
        record_id = db.add_record(
            fields.get("type", "expense"),
            fields.get("category") or "其他",
            amount,
            fields.get("date") or date.today().isoformat(),
            fields.get("note", ""),
        )
        return {"kind": kind, "id": record_id}
    if kind == "exercise":
        duration = int(fields.get("duration") or 0)
        if duration <= 0:
            raise ValueError("运动时长必须大于 0")
        exercise_id = db.add_exercise(
            fields.get("date") or date.today().isoformat(),
            fields.get("type") or "其他",
            duration,
        )
        return {"kind": kind, "id": exercise_id}
    if kind == "memo":
        memo_id = db.add_memo(
            fields.get("title") or parsed.get("raw", "")[:20],
            fields.get("content") or parsed.get("raw", ""),
            fields.get("category") or "general",
            fields.get("tags", ""),
        )
        return {"kind": kind, "id": memo_id}
    raise ValueError(f"不支持的收集类型: {kind}")
