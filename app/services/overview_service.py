from datetime import date, timedelta


def _month_bounds(today: date) -> tuple[str, str]:
    first = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    last = next_month - timedelta(days=1)
    return first.isoformat(), last.isoformat()


def build_today_overview(db, today: str | None = None) -> dict:
    today_obj = date.fromisoformat(today) if today else date.today()
    today_text = today_obj.isoformat()
    todos = db.get_today_todos(today_text)
    order = {"q1": 0, "q2": 1, "q3": 2, "q4": 3}
    top_tasks = sorted(
        todos,
        key=lambda item: (
            order.get(item.get("quadrant", "q2"), 1),
            item.get("due_date") or "9999-12-31",
            item.get("updated_at") or "",
        ),
        reverse=False,
    )[:3]
    quadrants = {key: 0 for key in ("q1", "q2", "q3", "q4")}
    for todo in todos:
        quadrants[todo.get("quadrant", "q2")] = quadrants.get(todo.get("quadrant", "q2"), 0) + 1
    pomodoro = db.get_pomodoro_totals_between(today_text, today_text)
    month_start, month_end = _month_bounds(today_obj)
    finance = db.get_finance_totals_between(month_start, month_end)
    health = {"exercise_minutes_7d": db.get_exercise_minutes_between((today_obj - timedelta(days=6)).isoformat(), today_text)}
    return {
        "today": today_text,
        "top_tasks": top_tasks,
        "quadrants": quadrants,
        "pomodoro": pomodoro,
        "finance": finance,
        "health": health,
        "radar": build_life_radar(db, today_text),
    }


def build_life_radar(db, today: str | None = None) -> list[dict]:
    today_obj = date.fromisoformat(today) if today else date.today()
    today_text = today_obj.isoformat()
    alerts = []
    today_tasks = db.get_today_todos(today_text)
    q1_pending = sum(1 for todo in today_tasks if todo.get("quadrant") == "q1")
    if q1_pending > 3:
        alerts.append({
            "level": "warning",
            "title": "任务过载",
            "detail": f"今日重要紧急任务已有 {q1_pending} 个。",
            "suggestion": "先保留三件最关键的事，其余移到 q2 或本周计划。",
        })
    stale_cutoff = (today_obj - timedelta(days=3)).isoformat()
    stale = [todo for todo in today_tasks if todo.get("today_date") and todo["today_date"] <= stale_cutoff]
    if stale:
        alerts.append({
            "level": "warning",
            "title": "顺延风险",
            "detail": f"{len(stale)} 个今日任务已顺延超过 3 天。",
            "suggestion": "拆小任务，或明确延期到新的日期。",
        })
    exercise_minutes = db.get_exercise_minutes_between((today_obj - timedelta(days=6)).isoformat(), today_text)
    if exercise_minutes == 0:
        alerts.append({
            "level": "info",
            "title": "健康缺口",
            "detail": "最近 7 天还没有运动记录。",
            "suggestion": "安排一次 20 分钟低门槛运动。",
        })
    month_start, month_end = _month_bounds(today_obj)
    finance = db.get_finance_totals_between(month_start, month_end)
    if finance["income"] > 0 and finance["expense"] / finance["income"] >= 0.8:
        alerts.append({
            "level": "warning",
            "title": "财务压力",
            "detail": "本月支出已接近收入的 80%。",
            "suggestion": "检查非必要支出，保留本月现金缓冲。",
        })
    recent_cutoff = (today_obj - timedelta(days=7)).isoformat()
    for objective in db.get_objectives("active"):
        krs = db.get_key_results(objective_id=objective["id"], status_filter="active")
        if not krs:
            continue
        touched_recent = any((kr.get("updated_at") or "")[:10] >= recent_cutoff for kr in krs)
        if not touched_recent:
            alerts.append({
                "level": "info",
                "title": "目标停滞",
                "detail": f"目标「{objective['title']}」近 7 天没有更新 KR。",
                "suggestion": "更新一个 KR 进展，或调整目标状态。",
            })
            break
    return alerts
