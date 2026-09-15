import argparse, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from core import load_defaults, compute_forecast
from adapters.trentorch import read_progress, read_modules, read_upstream_commit

def _load_config(path):
    text = Path(path).read_text()
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = _load_config(a.config)
    base = Path(__file__).parent
    defaults = load_defaults(str(base / "timeline.defaults.yaml"))
    clone = cfg["trentorch_path"]
    completed, started = read_progress(clone)
    try:
        mods = read_modules(clone)
    except Exception as e:
        print(f"warning: {e}")
        mods = []
    items = []
    by_id = {m["id"]: m["title"] for m in mods}
    for m in defaults["modules"]:
        items.append({"id": m["id"], "title": by_id.get(m["id"], m["title"]), "hours": m["hours"], "kind": "module"})
    for ms in defaults["milestones"]:
        items.append({"id": ms["id"], "title": ms["title"], "hours": ms["hours"], "kind": "milestone"})
    cur_pin = read_upstream_commit(clone)
    if cur_pin != defaults.get("upstream_commit"):
        print(f"warning: clone {cur_pin} != defaults pin {defaults.get('upstream_commit')} (curriculum may have drifted)")
    rows, summary = compute_forecast(items, completed, float(cfg["hours_per_week"]), int(cfg["days_per_week"]), cfg.get("off_day", "sunday"), cfg.get("start_date", "2026-09-15"), float(cfg.get("buffer_pct", 20)))
    outdir = Path(a.config).parent
    (outdir / "forecast.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    lines = [f"# Forecast ({cfg['hours_per_week']}h/week, {cfg['days_per_week']} days, {cfg.get('off_day','sunday')} off)", "", f"Finish: {summary['finish_date']} ({summary['weeks']} weeks, {summary['total_remaining']}h remaining, {summary['daily_hours']}h/day)", ""]
    prof = [r for r in rows if r["id"] in ("13", "M5")]
    if prof:
        lines.append(f"Proficient (through 13+M5): {prof[-1]['due_date']}")
        lines.append("")
    for r in rows:
        mark = "x" if r["id"] in completed else " "
        lines.append(f"- [{mark}] {r['id']} {r['title']} — {r['hours']}h due {r['due_date']}")
    (outdir / "forecast.md").write_text("\n".join(lines))
    print(f"proficient: {prof[-1]['due_date'] if prof else '?'} finish: {summary['finish_date']} ({summary['daily_hours']}h/day)")

if __name__ == "__main__":
    main()
