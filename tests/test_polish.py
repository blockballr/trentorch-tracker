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
from adapters.trentorch import read_milestones, read_progress
from weekly import format_heatmap, format_weekly, weekly_summary


@pytest.fixture
def cfg(tmp_path):
    p = tmp_path / "my.yaml"
    p.write_text(
        'hours_per_week: 40\ndays_per_week: 6\noff_day: sunday\n'
        'start_date: "2026-09-15"\nbuffer_pct: 20\ntrentorch_path: "C:/Users/user/TrenTorch"\n'
        "auto_adjust: false\nskill_mult: 1.0\n",
        encoding="utf-8",
    )
    return p


def test_notify_toast_failure_silent():
    import notify
    # toast helper must not raise when BurntToast/notify-send missing
    assert notify.try_toast("hello toast") in (True, False)
    assert notify.terminal_alert("msg", toast=True) is True


def test_profile_fallback(tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    prof = tmp_path / "profile.json"
    prof.write_text(json.dumps({"modules_completed": ["01", "02"]}), encoding="utf-8")
    completed, started = read_progress(str(clone), profile_path=str(prof))
    assert completed == {"01", "02"}
    assert started == {"01", "02"}


def test_read_milestones_real_or_empty():
    clone = Path("C:/Users/user/TrenTorch")
    if not clone.exists():
        pytest.skip("clone missing")
    ms = read_milestones(str(clone))
    assert isinstance(ms, list)
    if ms:
        assert ms[0]["id"] == "M1"
        assert "kind" in ms[0]


def test_skill_mult_cli(tmp_path):
    clone = tmp_path / "clone"
    (clone / "user_data").mkdir(parents=True)
    (clone / "user_data" / "progress.json").write_text(
        json.dumps({"started_modules": [], "completed_modules": []}), encoding="utf-8"
    )
    src = clone / "data" / "src"
    src.mkdir(parents=True)
    for i in range(1, 21):
        d = src / f"{i:02d}_m"
        d.mkdir()
        (d / "module.yaml").write_text(f"title: Module {i:02d}\n", encoding="utf-8")
    cfg = tmp_path / "my.yaml"
    cfg.write_text(
        "hours_per_week: 40\ndays_per_week: 6\noff_day: sunday\n"
        f'start_date: "2026-09-15"\nbuffer_pct: 0\n'
        f'trentorch_path: "{clone.as_posix()}"\nskill_mult: 1.0\n',
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tracker.py"),
            "--update",
            "--config",
            str(cfg),
            "--skill-mult",
            "2",
            "--trentorch-path",
            str(clone),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert "skill_mult: 2" in r.stdout
    d = json.loads((tmp_path / "forecast.json").read_text(encoding="utf-8"))
    row01 = next(x for x in d["rows"] if x["id"] == "01")
    assert abs(row01["hours"] - 36.0) < 0.01  # 18 * 2
    assert d["skill_mult"] == 2.0


def test_weekly_and_heatmap(cfg):
    t0 = datetime.datetime.fromisoformat("2026-10-15T08:00:00")
    sessions.start(cfg, module="01", now=t0)
    sessions.stop(cfg, now=t0 + datetime.timedelta(minutes=420))
    s = weekly_summary(cfg, now=t0 + datetime.timedelta(hours=1))
    assert s["total"] >= 400
    text = format_weekly(s)
    assert "Weekly summary" in text
    assert "hit" in text
    hm = format_heatmap(cfg, now=t0 + datetime.timedelta(hours=1), weeks=2)
    assert "Study heatmap" in hm
    assert "scale:" in hm


def test_cli_weekly_heatmap(cfg):
    tr = ROOT / "tr.py"
    py = sys.executable
    r = subprocess.run([py, str(tr), "--config", str(cfg), "weekly"], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert "Weekly summary" in r.stdout
    r2 = subprocess.run([py, str(tr), "--config", str(cfg), "heatmap"], capture_output=True, text=True, timeout=30)
    assert r2.returncode == 0, r2.stderr
    assert "heatmap" in r2.stdout.lower()
