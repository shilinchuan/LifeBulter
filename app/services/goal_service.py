def calculate_kr_progress(kr: dict) -> int:
    target = float(kr.get("target_value") or 0)
    current = float(kr.get("current_value") or 0)
    metric_type = kr.get("metric_type", "number")
    if target <= 0:
        return 0
    if metric_type == "boolean":
        return 100 if current >= 1 else 0
    if metric_type == "percentage":
        return max(0, min(100, round(current / 100 * 100)))
    return max(0, min(100, round(current / target * 100)))


def build_objective_detail(db, objective_id: int) -> dict:
    objective = db.get_objective(objective_id)
    krs = db.get_key_results(objective_id=objective_id, status_filter="all")
    for kr in krs:
        kr["progress"] = calculate_kr_progress(kr)
    projects = db.get_projects(objective_id=objective_id, status_filter="all")
    return {"objective": objective, "krs": krs, "projects": projects}
