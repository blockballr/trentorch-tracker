import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sessions


@pytest.fixture
def cfg(tmp_path):
    p = tmp_path / "my.yaml"
    p.write_text(
        'hours_per_week: 40\ndays_per_week: 6\noff_day: sunday\n'
        'start_date: "2026-09-15"\nbuffer_pct: 20\ntrentorch_path: "C:/Users/user/TrenTorch"\n',
        encoding="utf-8",
    )
    return p


def _dt(s):
    return datetime.datetime.fromisoformat(s)


def test_daily_target_400(cfg):
    assert abs(sessions.daily_target_min(sessions.load_config(cfg)) - 400.0) < 0.01


def test_sessions_round_trip(cfg):
    assert sessions.read_sessions(cfg) == []
    sessions.append_session(
        cfg,
        {
            "module": "01",
            "kind": "session",
            "start": "2026-10-15T09:00:00",
            "end": "2026-10-15T10:00:00",
            "regular_minutes": 60.0,
            "overtime_minutes": 0.0,
            "pause_count": 0,
            "target_hit": False,
        },
    )
    recs = sessions.read_sessions(cfg)
    assert len(recs) == 1
    assert recs[0]["module"] == "01"
    assert recs[0]["regular_minutes"] == 60.0


def test_lifecycle_pause_excluded(cfg):
    t0 = _dt("2026-10-15T09:00:00")
    state = sessions.start(cfg, module="01", now=t0)
    assert state["module"] == "01" and not state["paused"]
    sessions.pause(cfg, now=t0 + datetime.timedelta(minutes=30))
    st = sessions.load_state(cfg)
    assert st["paused"] and st["pause_count"] == 1
    sessions.resume(cfg, now=t0 + datetime.timedelta(minutes=40))
    assert not sessions.load_state(cfg)["paused"]
    rec = sessions.stop(cfg, now=t0 + datetime.timedelta(minutes=110))
    assert rec["module"] == "01"
    assert abs(rec["regular_minutes"] - 100.0) < 0.1
    assert rec["overtime_minutes"] == 0.0
    assert rec["pause_count"] == 1
    assert sessions.load_state(cfg) is None
    assert len(sessions.read_sessions(cfg)) == 1


def test_start_uses_progress_last_worked(cfg, tmp_path):
    clone = tmp_path / "clone"
    (clone / "user_data").mkdir(parents=True)
    (clone / "user_data" / "progress.json").write_text(
        json.dumps({"started_modules": ["01", "02"], "last_worked": "02"}),
        encoding="utf-8",
    )
    cfg.write_text(
        'hours_per_week: 40\ndays_per_week: 6\noff_day: sunday\n'
        f'start_date: "2026-09-15"\nbuffer_pct: 20\ntrentorch_path: "{clone.as_posix()}"\n',
        encoding="utf-8",
    )
    state = sessions.start(cfg, now=_dt("2026-10-15T09:00:00"))
    assert state["module"] == "02"


def test_double_start_errors(cfg):
    t0 = _dt("2026-10-15T09:00:00")
    sessions.start(cfg, module="01", now=t0)
    with pytest.raises(RuntimeError):
        sessions.start(cfg, module="02", now=t0 + datetime.timedelta(minutes=1))


def test_stop_idle_errors(cfg):
    with pytest.raises(RuntimeError):
        sessions.stop(cfg, now=_dt("2026-10-15T09:00:00"))


def test_regular_vs_overtime_split(cfg):
    t0 = _dt("2026-10-15T08:00:00")
    sessions.start(cfg, module="02", now=t0)
    rec = sessions.stop(cfg, now=t0 + datetime.timedelta(minutes=420))
    assert abs(rec["regular_minutes"] - 400.0) < 0.1
    assert abs(rec["overtime_minutes"] - 20.0) < 0.1
    assert rec["target_hit"] is True


def test_second_session_all_overtime(cfg):
    t0 = _dt("2026-10-15T08:00:00")
    sessions.start(cfg, module="01", now=t0)
    sessions.stop(cfg, now=t0 + datetime.timedelta(minutes=400))
    sessions.start(cfg, module="01", now=t0 + datetime.timedelta(minutes=420))
    rec = sessions.stop(cfg, now=t0 + datetime.timedelta(minutes=480))
    assert rec["regular_minutes"] == 0.0
    assert abs(rec["overtime_minutes"] - 60.0) < 0.1
    assert rec["target_hit"] is False


def test_forgotten_timer_auto_stops_midnight(cfg):
    t0 = _dt("2026-10-15T22:00:00")
    sessions.start(cfg, module="03", now=t0)
    state = sessions.start(cfg, module="04", now=_dt("2026-10-16T09:00:00"))
    assert state["module"] == "04"
    recs = sessions.read_sessions(cfg)
    assert len(recs) == 1
    assert recs[0]["module"] == "03"
    assert recs[0]["end"].startswith("2026-10-16T00:00")
    assert abs(recs[0]["regular_minutes"] - 120.0) < 0.1


def test_status_idle_and_live(cfg):
    t0 = _dt("2026-10-15T08:00:00")
    st0 = sessions.status(cfg, now=t0)
    assert st0["active"] is False
    assert abs(st0["minutes_to_target"] - 400.0) < 0.01
    sessions.start(cfg, module="01", now=t0)
    sessions.stop(cfg, now=t0 + datetime.timedelta(minutes=450))
    sessions.start(cfg, module="01", now=t0 + datetime.timedelta(minutes=480))
    st = sessions.status(cfg, now=t0 + datetime.timedelta(minutes=510))
    assert st["active"] is True
    assert abs(st["logged_regular"] - 400.0) < 0.1
    assert abs(st["logged_overtime"] - 50.0) < 0.1
    assert abs(st["live_overtime"] - 30.0) < 0.1


def test_status_closed_note_on_midnight(cfg):
    sessions.start(cfg, module="01", now=_dt("2026-10-15T22:00:00"))
    st = sessions.status(cfg, now=_dt("2026-10-16T09:00:00"))
    assert st["closed_note"] == "auto-stopped at midnight"
    assert st["active"] is False
    assert sessions.load_state(cfg) is None


def test_alert_once_per_day(cfg):
    t0 = _dt("2026-10-15T08:00:00")
    sessions.start(cfg, module="01", now=t0)
    sessions.stop(cfg, now=t0 + datetime.timedelta(minutes=401))
    r1 = sessions.maybe_alert(cfg, now=t0 + datetime.timedelta(hours=1))
    assert r1["fired"] is True
    r2 = sessions.maybe_alert(cfg, now=t0 + datetime.timedelta(hours=2))
    assert r2["fired"] is False
    hit = (cfg.parent / ".target_hit_date").read_text(encoding="utf-8").strip()
    assert hit == "2026-10-15"


def test_cli_watch_test_and_status(cfg):
    tr = ROOT / "tr.py"
    py = sys.executable
    r = subprocess.run(
        [py, str(tr), "--config", str(cfg), "watch", "--test"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert "Daily target hit!" in r.stdout
    r2 = subprocess.run(
        [py, str(tr), "--config", str(cfg), "status"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r2.returncode == 0, r2.stderr
    assert "target" in r2.stdout


def test_cli_stop_idle_exit_2(cfg):
    tr = ROOT / "tr.py"
    r = subprocess.run(
        [sys.executable, str(tr), "--config", str(cfg), "stop"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 2
    assert "no active timer" in r.stderr
