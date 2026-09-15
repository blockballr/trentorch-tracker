import datetime

OFF = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}

def load_defaults(path):
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    except ImportError:
        import json
        alt = path.replace(".yaml", ".json")
        with open(alt) as f:
            return json.load(f)

def _advance(d, off):
    d += datetime.timedelta(days=1)
    while d.weekday() == off:
        d += datetime.timedelta(days=1)
    return d

def compute_forecast(items, completed, hours_per_week, days_per_week, off_day, start_date, buffer_pct):
    if hours_per_week <= 0:
        raise ValueError("hours_per_week must be > 0")
    if days_per_week not in (5, 6, 7):
        raise ValueError("days_per_week must be 5, 6, or 7")
    mult = 1.0 + float(buffer_pct) / 100.0
    daily = float(hours_per_week) / float(days_per_week)
    off = OFF[off_day.lower()] if days_per_week != 7 else None
    cur = datetime.date.fromisoformat(start_date)
    if off is not None and cur.weekday() == off:
        cur += datetime.timedelta(days=1)
        while cur.weekday() == off:
            cur += datetime.timedelta(days=1)
    rows = []
    remaining = 0.0
    carry = 0.0
    for it in items:
        if it["id"] in completed:
            continue
        h = float(it["hours"]) * mult
        remaining += h
        carry += h
        while carry >= daily - 1e-9:
            carry -= daily
            if off is None:
                cur += datetime.timedelta(days=1)
            else:
                cur = _advance(cur, off)
        rows.append({"id": it["id"], "title": it["title"], "hours": round(h, 1), "due_date": cur.isoformat(), "daily_target": round(daily, 2)})
    weeks = remaining / float(hours_per_week)
    return rows, {"total_remaining": round(remaining, 1), "weeks": round(weeks, 2), "finish_date": cur.isoformat(), "daily_hours": round(daily, 2)}
