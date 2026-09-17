from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from adjust import actual_hours_by_module, observed_ratio
from adapters.trentorch import read_progress
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


def _completed_ids(config):
    clone = config.get("trentorch_path")
    if not clone:
        return set()
    try:
        completed, _started = read_progress(clone)
        return {str(x) for x in completed}
    except Exception:
        return set()


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
    item_list = [
        {"id": mid, "title": e["title"], "hours": e["hours"], "kind": e["kind"]}
        for mid, e in est.items()
    ]
    act_by_id = actual_hours_by_module(sessions)
    completed = _completed_ids(config)
    adj = observed_ratio(item_list, act_by_id, completed)
    ratio = float(adj["ratio"]) if adj["applied"] else 1.0
    rows = []
    total_est = 0.0
    total_reg = 0.0
    total_ot = 0.0
    total_adj_remaining = 0.0
    for mid, e in est.items():
        a = by_mod.get(mid, {"regular": 0.0, "overtime": 0.0})
        total_h = a["regular"] + a["overtime"]
        is_remaining = mid not in completed and total_h <= 0
        adj_hours = round(e["hours"] * ratio, 2) if is_remaining and adj["applied"] else None
        if is_remaining and adj["applied"]:
            total_adj_remaining += e["hours"] * ratio
        rows.append(
            {
                "id": mid,
                "title": e["title"],
                "est_hours": e["hours"],
                "regular": round(a["regular"], 2),
                "overtime": round(a["overtime"], 2),
                "total": round(total_h, 2),
                "vs": _vs_label(total_h, e["hours"]),
                "adj_hours": adj_hours,
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
            "adj_remaining": round(total_adj_remaining, 2) if adj["applied"] else None,
        },
        "adjust": adj,
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
    adj = report.get("adjust") or {}
    show_adj = bool(adj.get("applied"))
    header = (
        f"{'Module':<8} {'Est. Hours':>10} {'Regular':>8} "
        f"{'Overtime':>9} {'Total':>7} {'vs Est.':>10}"
    )
    if show_adj:
        header += f" {'Adj.':>8}"
    lines = [header, "-" * len(header)]
    for r in report["rows"]:
        line = (
            f"{r['id']:<8} {r['est_hours']:>10.1f} {r['regular']:>8.2f} "
            f"{r['overtime']:>9.2f} {r['total']:>7.2f} {r['vs']:>10}"
        )
        if show_adj:
            if r.get("adj_hours") is not None:
                line += f" {r['adj_hours']:>8.1f}"
            else:
                line += f" {'-':>8}"
        lines.append(line)
    t = report["totals"]
    lines.append("-" * len(header))
    total_line = (
        f"{'Total':<8} {t['est_hours']:>10.1f} {t['regular']:>8.2f} "
        f"{t['overtime']:>9.2f} {t['total']:>7.2f} {t['vs_remaining_pct']:>9.1f}% remaining"
    )
    lines.append(total_line)
    s = report["summary"]
    lines.append("")
    lines.append(
        f"Accuracy: estimated {s['est_hours']}h, actual so far {s['actual_hours']}h "
        f"({s['pct_of_forecast']}% of forecast)"
    )
    if adj:
        ratio = float(adj.get("ratio", 1.0))
        if adj.get("applied"):
            lines.append(
                f"Observed ratio: {ratio:.2f} "
                f"({adj.get('observed_actual', 0)}h actual / {adj.get('observed_est', 0)}h est "
                f"over {len(adj.get('observed_ids') or [])} modules); remaining scaled in report when shown"
            )
        else:
            lines.append(
                f"Observed ratio: {ratio:.2f} - within 10%, estimates unchanged"
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
