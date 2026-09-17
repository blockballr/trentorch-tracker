THRESHOLD = 0.10


def observed_ratio(items, actual_hours_by_id, completed_ids=None):
    """Ratio from modules that logged time. Zero-time completions stay out of the ratio."""
    actual_hours_by_id = actual_hours_by_id or {}
    completed_ids = set(completed_ids or [])
    obs_est = 0.0
    obs_act = 0.0
    obs_ids = []
    for it in items:
        iid = str(it["id"])
        act = float(actual_hours_by_id.get(iid, 0.0) or 0.0)
        if act <= 0:
            continue
        obs_est += float(it["hours"])
        obs_act += act
        obs_ids.append(iid)
    if obs_est <= 0:
        return {
            "ratio": 1.0,
            "applied": False,
            "observed_est": 0.0,
            "observed_actual": 0.0,
            "observed_ids": [],
        }
    ratio = obs_act / obs_est
    applied = abs(ratio - 1.0) > THRESHOLD
    return {
        "ratio": ratio,
        "applied": applied,
        "observed_est": round(obs_est, 4),
        "observed_actual": round(obs_act, 4),
        "observed_ids": obs_ids,
    }


def scale_remaining(items, ratio, completed_ids=None):
    completed_ids = set(completed_ids or [])
    out = []
    for it in items:
        row = dict(it)
        if str(it["id"]) not in completed_ids:
            row["hours"] = float(it["hours"]) * float(ratio)
        out.append(row)
    return out


def actual_hours_by_module(sessions_records):
    acc = {}
    for s in sessions_records or []:
        if s.get("kind") not in (None, "session"):
            continue
        if s.get("kind") == "session" or "regular_minutes" in s:
            mid = str(s.get("module"))
            hours = (float(s.get("regular_minutes") or 0) + float(s.get("overtime_minutes") or 0)) / 60.0
            acc[mid] = acc.get(mid, 0.0) + hours
    return acc


def effective_ratio(info):
    if not info:
        return 1.0
    return float(info["ratio"]) if info.get("applied") else 1.0
