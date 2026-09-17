import datetime
import json
from pathlib import Path

STATE_NAME = ".timer_state.json"
SESSIONS_NAME = "sessions.jsonl"
TARGET_HIT_NAME = ".target_hit_date"


def _now(now=None):
    return now if now is not None else datetime.datetime.now()


def _dir(config_path):
    return Path(config_path).parent


def _state_path(config_path):
    return _dir(config_path) / STATE_NAME


def _sessions_path(config_path):
    return _dir(config_path) / SESSIONS_NAME


def _target_hit_path(config_path):
    return _dir(config_path) / TARGET_HIT_NAME


def daily_target_min(config):
    hours = float(config["hours_per_week"])
    days = int(config["days_per_week"])
    if days <= 0:
        raise ValueError("days_per_week must be > 0")
    return hours / days * 60.0


def load_config(path):
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


def load_state(config_path):
    p = _state_path(config_path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(config_path, state):
    p = _state_path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")


def clear_state(config_path):
    p = _state_path(config_path)
    if p.exists():
        p.unlink()


def read_sessions(config_path):
    p = _sessions_path(config_path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def append_session(config_path, record):
    p = _sessions_path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")


def _parse_iso(s):
    return datetime.datetime.fromisoformat(s)


def _midnight_after(dt):
    d = dt.date() + datetime.timedelta(days=1)
    return datetime.datetime.combine(d, datetime.time.min)


def live_elapsed_seconds(state, now):
    if state is None:
        return 0.0
    acc = float(state.get("accumulated_seconds", 0.0))
    if state.get("paused") or not state.get("segment_start"):
        return acc
    seg_start = _parse_iso(state["segment_start"])
    cutoff = _midnight_after(_parse_iso(state["start_time"]))
    end = now if now <= cutoff else cutoff
    return acc + max(0.0, (end - seg_start).total_seconds())


def _needs_midnight_close(state, now):
    if state is None:
        return False
    return _parse_iso(state["start_time"]).date() < now.date()


def _day_regular_prior(config_path, day_iso, exclude_start=None):
    prior = 0.0
    for s in read_sessions(config_path):
        if s.get("kind") != "session":
            continue
        if not str(s.get("start", "")).startswith(day_iso):
            continue
        if exclude_start is not None and s.get("start") == exclude_start:
            continue
        prior += float(s.get("regular_minutes", 0.0))
    return prior


def _close_state(config_path, state, end_dt, daily_target):
    start = _parse_iso(state["start_time"])
    cutoff = _midnight_after(start)
    if end_dt > cutoff:
        end_dt = cutoff
    total_sec = float(state.get("accumulated_seconds", 0.0))
    if not state.get("paused") and state.get("segment_start"):
        seg_start = _parse_iso(state["segment_start"])
        if seg_start > cutoff:
            seg_start = cutoff
        end_for_span = end_dt if end_dt <= cutoff else cutoff
        if end_for_span < seg_start:
            end_for_span = seg_start
        total_sec += (end_for_span - seg_start).total_seconds()
    minutes = max(0.0, total_sec) / 60.0
    day_iso = start.date().isoformat()
    prior_regular = _day_regular_prior(config_path, day_iso, state.get("start_time"))
    target = float(daily_target)
    remaining = max(0.0, target - prior_regular)
    regular = min(minutes, remaining)
    overtime = max(0.0, minutes - regular)
    target_hit = prior_regular < target and (prior_regular + minutes) >= target
    record = {
        "module": state["module"],
        "kind": "session",
        "start": state["start_time"],
        "end": end_dt.isoformat(),
        "regular_minutes": round(regular, 2),
        "overtime_minutes": round(overtime, 2),
        "pause_count": int(state.get("pause_count", 0)),
        "target_hit": bool(target_hit),
    }
    append_session(config_path, record)
    clear_state(config_path)
    return record


def resolve_module(config, explicit=None, clone=None):
    if explicit is not None:
        s = str(explicit)
        return s.zfill(2) if s.isdigit() else s
    if clone:
        p = Path(clone) / "user_data" / "progress.json"
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                last = d.get("last_worked")
                if last:
                    s = str(last)
                    return s.zfill(2) if s.isdigit() else s
                started = d.get("started_modules") or []
                if started:
                    s = str(started[-1])
                    return s.zfill(2) if s.isdigit() else s
            except Exception:
                pass
    return "01"


def _auto_close_if_stale(config_path, state, now):
    if state is None or not _needs_midnight_close(state, now):
        return state, None
    config = load_config(config_path)
    closed = _close_state(
        config_path,
        state,
        _midnight_after(_parse_iso(state["start_time"])),
        daily_target_min(config),
    )
    return None, closed


def start(config_path, module=None, now=None):
    now = _now(now)
    config = load_config(config_path)
    state = load_state(config_path)
    state, closed = _auto_close_if_stale(config_path, state, now)
    if module is None and closed is not None:
        module = closed["module"]
    if state is not None and state.get("paused"):
        raise RuntimeError(f"timer paused for module {state['module']}; use resume")
    if state is not None:
        raise RuntimeError(
            f"timer already running for module {state['module']} since {state['start_time']}"
        )
    mod = resolve_module(config, module, config.get("trentorch_path"))
    state = {
        "module": mod,
        "start_time": now.isoformat(),
        "segment_start": now.isoformat(),
        "pause_time": None,
        "paused": False,
        "accumulated_seconds": 0.0,
        "pause_count": 0,
    }
    save_state(config_path, state)
    return state


def pause(config_path, now=None):
    now = _now(now)
    state = load_state(config_path)
    if state is None:
        raise RuntimeError("no active timer")
    if state.get("paused"):
        raise RuntimeError("timer already paused")
    state, closed = _auto_close_if_stale(config_path, state, now)
    if closed is not None:
        return closed
    state["accumulated_seconds"] = live_elapsed_seconds(state, now)
    state["pause_time"] = now.isoformat()
    state["segment_start"] = None
    state["paused"] = True
    state["pause_count"] = int(state.get("pause_count", 0)) + 1
    save_state(config_path, state)
    return state


def resume(config_path, now=None):
    now = _now(now)
    state = load_state(config_path)
    if state is None:
        raise RuntimeError("no active timer")
    if not state.get("paused"):
        raise RuntimeError("timer is not paused")
    state, closed = _auto_close_if_stale(config_path, state, now)
    if closed is not None:
        return closed
    state["pause_time"] = None
    state["segment_start"] = now.isoformat()
    state["paused"] = False
    save_state(config_path, state)
    return state


def stop(config_path, now=None):
    now = _now(now)
    config = load_config(config_path)
    target = daily_target_min(config)
    state = load_state(config_path)
    if state is None:
        raise RuntimeError("no active timer")
    state, closed = _auto_close_if_stale(config_path, state, now)
    if closed is not None:
        return closed
    return _close_state(config_path, state, now, target)


def status(config_path, now=None):
    now = _now(now)
    config = load_config(config_path)
    target = daily_target_min(config)
    state = load_state(config_path)
    closed_note = None
    state, closed = _auto_close_if_stale(config_path, state, now)
    if closed is not None:
        closed_note = "auto-stopped at midnight"
    day_iso = now.date().isoformat()
    logged_regular = 0.0
    logged_overtime = 0.0
    for s in read_sessions(config_path):
        if s.get("kind") != "session":
            continue
        if not str(s.get("start", "")).startswith(day_iso):
            continue
        logged_regular += float(s.get("regular_minutes", 0.0))
        logged_overtime += float(s.get("overtime_minutes", 0.0))
    live_min = 0.0
    live_regular = 0.0
    live_overtime = 0.0
    active = state is not None
    paused = bool(state and state.get("paused"))
    module = state["module"] if state else None
    if state is not None:
        live_min = live_elapsed_seconds(state, now) / 60.0
        remaining = max(0.0, target - logged_regular)
        live_regular = min(live_min, remaining)
        live_overtime = max(0.0, live_min - live_regular)
    total_regular = logged_regular + live_regular
    total_overtime = logged_overtime + live_overtime
    return {
        "active": active,
        "paused": paused,
        "module": module,
        "live_minutes": round(live_min, 2),
        "logged_regular": round(logged_regular, 2),
        "logged_overtime": round(logged_overtime, 2),
        "live_regular": round(live_regular, 2),
        "live_overtime": round(live_overtime, 2),
        "total_regular": round(total_regular, 2),
        "total_overtime": round(total_overtime, 2),
        "daily_target_min": round(target, 2),
        "minutes_to_target": round(max(0.0, target - total_regular), 2),
        "closed_note": closed_note,
    }


def maybe_alert(config_path, now=None):
    now = _now(now)
    config = load_config(config_path)
    target = daily_target_min(config)
    st = status(config_path, now=now)
    today = now.date().isoformat()
    hit_path = _target_hit_path(config_path)
    already = hit_path.read_text(encoding="utf-8").strip() if hit_path.exists() else ""
    if st["total_regular"] >= target and already != today:
        hit_path.parent.mkdir(parents=True, exist_ok=True)
        hit_path.write_text(today, encoding="utf-8")
        hours = st["total_regular"] / 60.0
        return {
            "fired": True,
            "message": f"Daily target hit! You've done {hours:.1f}h. Overtime is being tracked.",
            "today": today,
        }
    return {"fired": False, "message": None, "today": today}


def format_hm(minutes):
    m = int(round(float(minutes)))
    return f"{m // 60}h {m % 60}m"
