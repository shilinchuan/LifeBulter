from datetime import date, timedelta


def current_year_week() -> tuple[int, int]:
    today = date.today().isocalendar()
    return today.year, today.week


def week_date_range(year: int, week: int) -> tuple[str, str]:
    monday = date.fromisocalendar(year, week, 1)
    sunday = date.fromisocalendar(year, week, 7)
    return monday.isoformat(), sunday.isoformat()


def build_week_summary(db, year: int, week: int) -> dict:
    start_date, end_date = week_date_range(year, week)
    weekly_tasks = db.get_weekly_tasks(year, week)
    task_total = len(weekly_tasks)
    task_done = sum(
        1 for item in weekly_tasks
        if item.get("task_status") == "done" or int(item.get("completion") or 0) >= 100
    )
    today_obj = date.today()
    stale_date = (today_obj - timedelta(days=3)).isoformat()
    deferred = 0
    for item in weekly_tasks:
        if item.get("task_status") == "done":
            continue
        today_date = item.get("today_date") or item.get("today_task_date") or ""
        if today_date and (today_date < start_date or today_date <= stale_date):
            deferred += 1
    pomodoro = db.get_pomodoro_totals_between(start_date, end_date)
    finance = db.get_finance_totals_between(start_date, end_date)
    exercise_minutes = db.get_exercise_minutes_between(start_date, end_date)
    return {
        "year": year,
        "week": week,
        "start_date": start_date,
        "end_date": end_date,
        "task_total": task_total,
        "task_done": task_done,
        "task_completion_rate": round(task_done / task_total * 100) if task_total else 0,
        "pomodoro_minutes": pomodoro["minutes"],
        "exercise_minutes": exercise_minutes,
        "income": finance["income"],
        "expense": finance["expense"],
        "balance": finance["balance"],
        "deferred_task_count": deferred,
        "radar": [],
    }


def render_week_review_markdown(summary: dict, review: dict | None) -> str:
    review = review or {}
    radar_items = summary.get("radar") or []
    radar_text = "\n".join(f"- {item.get('title', '')}: {item.get('detail', '')}" for item in radar_items) or "- 暂无风险提醒"
    return (
        f"# LifeButler 周报 {summary['year']}-{summary['week']:02d}\n\n"
        "## 自动统计\n\n"
        f"- 本周任务：已完成 {summary['task_done']} / 总计 {summary['task_total']}，完成率 {summary['task_completion_rate']}%\n"
        f"- 专注时间：{summary['pomodoro_minutes']} 分钟\n"
        f"- 运动时间：{summary['exercise_minutes']} 分钟\n"
        f"- 收入：¥{summary['income']:.2f}\n"
        f"- 支出：¥{summary['expense']:.2f}\n"
        f"- 结余：¥{summary['balance']:.2f}\n"
        f"- 顺延任务：{summary['deferred_task_count']} 个\n\n"
        "## 本周做得好的\n\n"
        f"{review.get('proud', '')}\n\n"
        "## 下周要改变的\n\n"
        f"{review.get('change', '')}\n\n"
        "## 下周承诺\n\n"
        f"{review.get('commit', '')}\n\n"
        "## 生活雷达\n\n"
        f"{radar_text}\n"
    )
