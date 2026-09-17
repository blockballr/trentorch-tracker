from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from core import load_defaults
from sessions import daily_target_min, load_config, read_sessions, status


def _estimates(base_dir=None):
    base = Path(base_dir) if base_dir else Path(__file__).parent
    defaults = load_defaults(str(base / "timeline.defaults.yaml"))
    est = {}
    for m in defaults.get("modules", []):
        est[str(m["id"])] = {
            "title": m["title"],
            "hours": float(m["hours"]),
            "kind": "module",
        }
    for m in defaults.get("milestones", []):
        est[str(m["id"])] = {
            "title": m["title"],
            "hours": float(m["hours"]),
            "kind": "milestone",
        }
    return est


def _vs_label(actual_h, est_h):
    if actual_h <= 0:
        return "not started"
    if est_h <= 0:
        return "n/a"
    pct = (actual_h - est_h) / est_h * 100.0
    return f"{pct:+.0f}%"


def build_report(config_path, now=None, base_dir=None):
    config = load_config(config_path)
    est = _estimates(base_dir)
    sessions = [s for s in read_sessions(config_path) if s.get("kind") == "session"]
    by_mod = defaultdict(lambda: {"regular": 0.0, "overtime": 0.0})
    days = set()
    for s in sessions:
        mod = str(s["module"])
        by_mod[mod]["regular"] += float(s.get("regular_minutes", 0.0)) / 60.0
        by_mod[mod]["overtime"] += float(s.get("overtime_minutes", 0.0)) / 60.0
        if s.get("start"):
            days.add(str(s["start"])[:10])
    st = status(config_path, now=now)
    rows = []
    total_est = 0.0
    total_reg = 0.0
    total_ot = 0.0
    for mid, e in est.items():
        a = by_mod.get(mid, {"regular": 0.0, "overtime": 0.0})
        total_h = a["regular"] + a["overtime"]
        rows.append(
            {
                "id": mid,
                "title": e["title"],
                "est_hours": e["hours"],
                "regular": round(a["regular"], 2),
                "overtime": round(a["overtime"], 2),
                "total": round(total_h, 2),
                "vs": _vs_label(total_h, e["hours"]),
            }
        )
        total_est += e["hours"]
        total_reg += a["regular"]
        total_ot += a["overtime"]
    actual_total = total_reg + total_ot
    remaining_est = max(0.0, total_est - actual_total)
    day_count = max(1, len(days))
    target = daily_target_min(config)
    return {
        "rows": rows,
        "totals": {
            "est_hours": round(total_est, 2),
            "regular": round(total_reg, 2),
            "overtime": round(total_ot, 2),
            "total": round(actual_total, 2),
            "vs_remaining_pct": round(remaining_est / total_est * 100.0, 1)
            if total_est
            else 0.0,
        },
        "summary": {
            "est_hours": round(total_est, 2),
            "actual_hours": round(actual_total, 2),
            "pct_of_forecast": round(actual_total / total_est * 100.0, 1)
            if total_est
            else 0.0,
            "days_logged": len(days),
            "daily_reg_avg": round(total_reg / day_count, 2) if days else 0.0,
            "daily_ot_avg": round(total_ot / day_count, 2) if days else 0.0,
            "daily_target_min": round(target, 2),
            "live": st,
        },
    }


def format_report(report):
    header = (
        f"{'Module':<8} {'Est. Hours':>10} {'Regular':>8} "
        f"{'Overtime':>9} {'Total':>7} {'vs Est.':>10}"
    )
    lines = [header, "-" * len(header)]
    for r in report["rows"]:
        lines.append(
            f"{r['id']:<8} {r['est_hours']:>10.1f} {r['regular']:>8.2f} "
            f"{r['overtime']:>9.2f} {r['total']:>7.2f} {r['vs']:>10}"
        )
    t = report["totals"]
    lines.append("-" * len(header))
    lines.append(
        f"{'Total':<8} {t['est_hours']:>10.1f} {t['regular']:>8.2f} "
        f"{t['overtime']:>9.2f} {t['total']:>7.2f} {t['vs_remaining_pct']:>9.1f}% remaining"
    )
    s = report["summary"]
    lines.append("")
    lines.append(
        f"Accuracy: estimated {s['est_hours']}h, actual so far {s['actual_hours']}h "
        f"({s['pct_of_forecast']}% of forecast)"
    )
    if s["days_logged"]:
        lines.append(
            f"Daily avg: {s['daily_reg_avg']}h regular + {s['daily_ot_avg']}h overtime "
            f"across {s['days_logged']} days"
        )
        lines.append(f"Daily target: {s['daily_target_min']:.0f} min")
    else:
        lines.append("No sessions logged yet.")
    return "\n".join(lines)
