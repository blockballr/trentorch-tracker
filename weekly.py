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


def _heat_level(mins, target):
    if mins <= 0:
        return 0
    if target <= 0:
        return 5
    r = mins / target
    if r < 0.25:
        return 1
    if r < 0.5:
        return 2
    if r < 0.75:
        return 3
    if r < 1.0:
        return 4
    return 5


def build_heatmap_html(config_path, now=None, weeks=12, title="TrenTorch study heatmap"):
    now = now if now is not None else datetime.datetime.now()
    config = load_config(config_path)
    target = daily_target_min(config)
    by_day = daily_minutes(config_path)
    end = now.date()
    start = end - datetime.timedelta(days=end.weekday() + 7 * (weeks - 1))
    bg, card, text, muted, border = "#0d1117", "#161b22", "#e6edf3", "#8b949e", "#30363d"
    palette = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#56d364"]
    n_weeks = max(1, ((end - start).days // 7) + 1)
    grid = [[None] * 7 for _ in range(n_weeks)]
    d = start
    while d <= end:
        grid[(d - start).days // 7][d.weekday()] = d
        d += datetime.timedelta(days=1)
    rows_html = []
    total = 0.0
    days_logged = 0
    hits = 0
    for week in grid:
        cells = []
        for day in week:
            if day is None:
                cells.append('<td class="c empty"></td>')
                continue
            m = by_day.get(day.isoformat(), {"total": 0.0})["total"]
            total += m
            if m > 0:
                days_logged += 1
            if m >= target > 0:
                hits += 1
            lv = _heat_level(m, target)
            cells.append(
                f'<td class="c lv{lv}" title="{day.isoformat()} | {m:.0f}m"></td>'
            )
        label = week[0].isoformat()[5:] if week[0] else ""
        rows_html.append(
            f'<tr><th class="wk">{label}</th>{"".join(cells)}</tr>'
        )
    swatches = "".join(
        f'<span class="sw" style="background:{c}"></span>' for c in palette
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ margin:0; min-height:100vh; background:{bg}; color:{text};
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
    display:flex; align-items:center; justify-content:center; padding:40px; }}
  .card {{ background:{card}; border:1px solid {border}; border-radius:16px;
    padding:28px 32px; max-width:760px; box-shadow:0 12px 40px rgba(0,0,0,.45); }}
  h1 {{ margin:0 0 4px; font-size:22px; font-weight:600; letter-spacing:-.02em; }}
  .sub {{ color:{muted}; font-size:13px; margin-bottom:20px; }}
  table {{ border-collapse:separate; border-spacing:4px; }}
  th.wk {{ color:{muted}; font-weight:500; font-size:10px; text-align:right;
    padding-right:6px; width:40px; }}
  td.c {{ width:14px; height:14px; border-radius:3px; }}
  td.empty {{ background:transparent; }}
  .lv0 {{ background:{palette[0]}; border:1px solid {border}; }}
  .lv1 {{ background:{palette[1]}; }}
  .lv2 {{ background:{palette[2]}; }}
  .lv3 {{ background:{palette[3]}; }}
  .lv4 {{ background:{palette[4]}; }}
  .lv5 {{ background:{palette[5]}; }}
  .legend {{ margin-top:18px; display:flex; align-items:center; gap:6px;
    color:{muted}; font-size:12px; }}
  .sw {{ width:12px; height:12px; border-radius:3px; display:inline-block; }}
  .stats {{ margin-top:14px; color:{muted}; font-size:13px; }}
  .stats b {{ color:{text}; font-weight:600; }}
</style>
</head>
<body>
  <div class="card">
    <h1>{title}</h1>
    <div class="sub">target {format_hm(target)}/day | {weeks} weeks</div>
    <table>{"".join(rows_html)}</table>
    <div class="legend">Less {swatches} More</div>
    <div class="stats">
      <b>{days_logged}</b> study days | <b>{hits}</b> target days |
      <b>{total/60:.1f}h</b> logged
    </div>
  </div>
</body>
</html>
"""


def write_heatmap_html(config_path, out_path=None, now=None, weeks=12, title=None):
    cfg_path = Path(config_path)
    if out_path is None:
        out_path = cfg_path.parent / "heatmap.html"
    else:
        out_path = Path(out_path)
    label = title or f"TrenTorch study heatmap ({cfg_path.parent.name})"
    html = build_heatmap_html(cfg_path, now=now, weeks=weeks, title=label)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
