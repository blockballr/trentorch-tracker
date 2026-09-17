import argparse, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from adjust import actual_hours_by_module, observed_ratio, scale_remaining
from core import load_defaults, compute_forecast
from adapters.trentorch import (
    read_milestones,
    read_progress,
    read_modules,
    read_upstream_commit,
)
from sessions import read_sessions


def _load_config(path):
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        d = {}
        for line in text.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                d[k.strip()] = v.strip().strip('"')
        d["hours_per_week"] = float(d["hours_per_week"])
        d["days_per_week"] = int(d["days_per_week"])
        d["buffer_pct"] = float(d.get("buffer_pct", 20))
        return d


def _want_auto_adjust(cfg, cli_flag):
    if cli_flag:
        return True
    val = cfg.get("auto_adjust", False)
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "on")
    return bool(val)


def _skill_mult(cfg, cli_value):
    if cli_value is not None:
        return float(cli_value)
    val = cfg.get("skill_mult", 1.0)
    try:
        return float(val)
    except (TypeError, ValueError):
        return 1.0


def _default_profile():
    return str(Path.home() / ".trentorch" / "profile.json")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--config", required=True)
    ap.add_argument("--trentorch-path", default=None)
    ap.add_argument("--skill-mult", type=float, default=None)
    ap.add_argument("--auto-adjust", action="store_true")
    a = ap.parse_args(argv)
    cfg = _load_config(a.config)
    base = Path(__file__).parent
    defaults = load_defaults(str(base / "timeline.defaults.yaml"))
    clone = a.trentorch_path or cfg.get("trentorch_path")
    if not clone:
        print("error: trentorch_path missing from config and --trentorch-path", file=sys.stderr)
        return 2
    completed, started = read_progress(clone, profile_path=_default_profile())
    try:
        mods = read_modules(clone)
    except Exception as e:
        print(f"warning: {e}")
        mods = []
    try:
        clone_ms = read_milestones(clone)
    except Exception as e:
        print(f"warning: milestones: {e}")
        clone_ms = []
    mult = _skill_mult(cfg, a.skill_mult)
    if mult <= 0:
        print("error: skill_mult must be > 0", file=sys.stderr)
        return 2
    items = []
    by_id = {m["id"]: m["title"] for m in mods}
    for m in defaults["modules"]:
        items.append({
            "id": m["id"],
            "title": by_id.get(m["id"], m["title"]),
            "hours": float(m["hours"]) * mult,
            "kind": "module",
        })
    if clone_ms:
        ms_by_id = {m["id"]: m for m in clone_ms}
        for ms in defaults["milestones"]:
            src = ms_by_id.get(ms["id"], {})
            items.append({
                "id": ms["id"],
                "title": src.get("title", ms["title"]),
                "hours": float(ms["hours"]) * mult,
                "kind": "milestone",
            })
    else:
        for ms in defaults["milestones"]:
            items.append({
                "id": ms["id"],
                "title": ms["title"],
                "hours": float(ms["hours"]) * mult,
                "kind": "milestone",
            })
    cur_pin = read_upstream_commit(clone)
    if cur_pin != defaults.get("upstream_commit"):
        print(f"warning: clone {cur_pin} != defaults pin {defaults.get('upstream_commit')} (curriculum may have drifted)")
    if mult != 1.0:
        print(f"skill_mult: {mult:g} applied to estimate hours")
    adjust_info = {"ratio": 1.0, "applied": False, "observed_est": 0.0, "observed_actual": 0.0, "observed_ids": []}
    if _want_auto_adjust(cfg, a.auto_adjust):
        try:
            recs = read_sessions(a.config)
        except Exception:
            recs = []
        act = actual_hours_by_module(recs)
        # ratio against unbuttered * skill_mult hours already on items
        adjust_info = observed_ratio(items, act, completed)
        if adjust_info["applied"]:
            items = scale_remaining(items, adjust_info["ratio"], completed)
            print(
                f"auto-adjust: ratio {adjust_info['ratio']:.2f} "
                f"({adjust_info['observed_actual']}h actual / {adjust_info['observed_est']}h est); "
                f"remaining hours scaled"
            )
        else:
            print(f"auto-adjust: ratio {adjust_info['ratio']:.2f} within 10%, estimates unchanged")
    rows, summary = compute_forecast(
        items,
        completed,
        float(cfg["hours_per_week"]),
        int(cfg["days_per_week"]),
        cfg.get("off_day", "sunday"),
        cfg.get("start_date", "2026-09-15"),
        float(cfg.get("buffer_pct", 20)),
    )
    outdir = Path(a.config).parent
    payload = {
        "summary": summary,
        "rows": rows,
        "adjust": adjust_info,
        "skill_mult": mult,
        "trentorch_path": clone,
    }
    (outdir / "forecast.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        f"# Forecast ({cfg['hours_per_week']}h/week, {cfg['days_per_week']} days, {cfg.get('off_day','sunday')} off)",
        "",
        f"Finish: {summary['finish_date']} ({summary['weeks']} weeks, {summary['total_remaining']}h remaining, {summary['daily_hours']}h/day)",
        "",
    ]
    if mult != 1.0:
        lines.append(f"Skill multiplier: {mult:g}")
        lines.append("")
    if adjust_info.get("applied"):
        lines.append(f"Auto-adjust: ratio {adjust_info['ratio']:.2f} applied to remaining hours")
        lines.append("")
    prof_row = next((r for r in rows if r["id"] == "13"), None)
    prof_label = "Proficient (Module 13 - transformer built)"
    if prof_row is not None:
        lines.append(f"{prof_label}: {prof_row['due_date']}")
        lines.append("")
    for r in rows:
        mark = "x" if r["id"] in completed else " "
        lines.append(f"- [{mark}] {r['id']} {r['title']} - {r['hours']}h due {r['due_date']}")
    (outdir / "forecast.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{prof_label}: {prof_row['due_date'] if prof_row is not None else '?'} finish: {summary['finish_date']} ({summary['daily_hours']}h/day)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
