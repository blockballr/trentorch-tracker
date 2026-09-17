import datetime
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from sessions import daily_target_min, format_hm, load_config, read_sessions


def daily_minutes(config_path, now=None):
    out = defaultdict(lambda: {"regular": 0.0, "overtime": 0.0, "total": 0.0})
    for s in read_sessions(config_path):
        if s.get("kind") != "session":
            continue
        start = str(s.get("start") or "")
        if len(start) < 10:
            continue
        day = start[:10]
        reg = float(s.get("regular_minutes") or 0)
        ot = float(s.get("overtime_minutes") or 0)
        out[day]["regular"] += reg
        out[day]["overtime"] += ot
        out[day]["total"] += reg + ot
    return out


def weekly_summary(config_path, now=None, days=7):
    now = now if now is not None else datetime.datetime.now()
    config = load_config(config_path)
    target = daily_target_min(config)
    by_day = daily_minutes(config_path, now=now)
    end = now.date()
    rows = []
    total_reg = 0.0
    total_ot = 0.0
    days_hit = 0
    for i in range(days - 1, -1, -1):
        d = end - datetime.timedelta(days=i)
        key = d.isoformat()
        rec = by_day.get(key, {"regular": 0.0, "overtime": 0.0, "total": 0.0})
        hit = rec["regular"] >= target
        if hit:
            days_hit += 1
        rows.append({
            "date": key,
            "regular": round(rec["regular"], 1),
            "overtime": round(rec["overtime"], 1),
            "total": round(rec["total"], 1),
            "target_hit": hit,
        })
        total_reg += rec["regular"]
        total_ot += rec["overtime"]
    return {
        "days": rows,
        "total_regular": round(total_reg, 1),
        "total_overtime": round(total_ot, 1),
        "total": round(total_reg + total_ot, 1),
        "target_min": round(target, 1),
        "days_hit": days_hit,
        "avg_regular": round(total_reg / max(1, days), 1),
    }


def format_weekly(summary):
    lines = [
        f"Weekly summary ({len(summary['days'])} days, target {format_hm(summary['target_min'])}/day)",
        "",
    ]
    for r in summary["days"]:
        mark = "hit" if r["target_hit"] else "    "
        lines.append(
            f"{r['date']}  reg {r['regular']:>6.1f}m  ot {r['overtime']:>6.1f}m  "
            f"tot {r['total']:>6.1f}m  {mark}"
        )
    lines.append("")
    lines.append(
        f"Totals: regular {summary['total_regular']}m + overtime {summary['total_overtime']}m "
        f"= {summary['total']}m | avg regular {summary['avg_regular']}m/day | "
        f"target days hit {summary['days_hit']}/{len(summary['days'])}"
    )
    return "\n".join(lines)


def format_heatmap(config_path, now=None, weeks=8):
    now = now if now is not None else datetime.datetime.now()
    config = load_config(config_path)
    target = daily_target_min(config)
    by_day = daily_minutes(config_path)
    end = now.date()
    start = end - datetime.timedelta(days=end.weekday() + 7 * (weeks - 1))
    levels = " .:-=+*#"
    lines = ["Study heatmap (minutes/day)", "", "      Mon Tue Wed Thu Fri Sat Sun"]
    day = start
    week_rows = []
    while day <= end:
        if day.weekday() == 0 or day == start:
            week_rows.append([None] * 7)
        week_rows[-1][day.weekday()] = by_day.get(day.isoformat(), {"total": 0.0})["total"]
        day += datetime.timedelta(days=1)
    for idx, row in enumerate(week_rows):
        cells = []
        for v in row:
            if v is None:
                cells.append("   ")
            elif v <= 0:
                cells.append(" . ")
            else:
                ratio = min(1.0, v / target) if target > 0 else 1.0
                ch = levels[min(len(levels) - 1, 1 + int(ratio * (len(levels) - 2)))]
                cells.append(f" {ch} ")
        week_start = start + datetime.timedelta(days=7 * idx)
        lines.append(f"{week_start.isoformat()[5:]} " + "".join(cells))
    lines.append("")
    lines.append(f"scale: . none .. {levels[-1]} at/over target ({format_hm(target)})")
    return "\n".join(lines)
