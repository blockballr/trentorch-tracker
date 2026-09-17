import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def make_clone(base: Path, completed=None, started=None) -> str:
    (base / "user_data").mkdir(parents=True, exist_ok=True)
    (base / "user_data" / "progress.json").write_text(
        json.dumps(
            {
                "started_modules": started or [],
                "completed_modules": completed or [],
                "last_worked": (started or ["01"])[-1],
            }
        ),
        encoding="utf-8",
    )
    src = base / "data" / "src"
    src.mkdir(parents=True, exist_ok=True)
    for i in range(1, 21):
        mod_id = f"{i:02d}"
        d = src / f"{mod_id}_mod"
        d.mkdir(parents=True, exist_ok=True)
        (d / "module.yaml").write_text(f"title: Module {mod_id}\n", encoding="utf-8")
    return str(base)


def write_cfg(tmp_path: Path, clone: str, auto_adjust=False) -> Path:
    cfg = tmp_path / "my.yaml"
    flag = "true" if auto_adjust else "false"
    cfg.write_text(
        "hours_per_week: 40\ndays_per_week: 6\noff_day: sunday\n"
        f'start_date: "2026-09-15"\nbuffer_pct: 20\ntrentorch_path: "{Path(clone).as_posix()}"\n'
        f"auto_adjust: {flag}\n",
        encoding="utf-8",
    )
    return cfg


def run_tracker(cfg: Path):
    return subprocess.run(
        [sys.executable, str(ROOT / "tracker.py"), "--update", "--config", str(cfg)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_forecast_default_unscaled(tmp_path):
    clone = make_clone(tmp_path / "clone")
    cfg = write_cfg(tmp_path, clone, auto_adjust=False)
    r = run_tracker(cfg)
    assert r.returncode == 0, r.stderr
    d = json.loads((tmp_path / "forecast.json").read_text(encoding="utf-8"))
    assert d["adjust"]["applied"] is False
    row01 = next(x for x in d["rows"] if x["id"] == "01")
    assert abs(row01["hours"] - 18 * 1.2) < 0.01


def test_forecast_auto_adjust_scales_remaining(tmp_path):
    clone = make_clone(tmp_path / "clone", completed=["01"], started=["02"])
    cfg = write_cfg(tmp_path, clone, auto_adjust=True)
    sessions = tmp_path / "sessions.jsonl"
    # module 01 est 18h, logged 27h -> ratio 1.5
    sessions.write_text(
        json.dumps(
            {
                "module": "01",
                "kind": "session",
                "start": "2026-10-15T08:00:00",
                "end": "2026-10-15T23:00:00",
                "regular_minutes": 400,
                "overtime_minutes": 1220,
                "pause_count": 0,
                "target_hit": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    r = run_tracker(cfg)
    assert r.returncode == 0, r.stderr
    assert "ratio 1.50" in r.stdout
    d = json.loads((tmp_path / "forecast.json").read_text(encoding="utf-8"))
    assert d["adjust"]["applied"] is True
    assert abs(d["adjust"]["ratio"] - 1.5) < 0.01
    row02 = next(x for x in d["rows"] if x["id"] == "02")
    assert abs(row02["hours"] - 12 * 1.5 * 1.2) < 0.05
    assert "01" not in {x["id"] for x in d["rows"]}


def test_forecast_auto_adjust_idempotent(tmp_path):
    clone = make_clone(tmp_path / "clone", completed=["01"], started=["02"])
    cfg = write_cfg(tmp_path, clone, auto_adjust=True)
    (tmp_path / "sessions.jsonl").write_text(
        json.dumps(
            {
                "module": "01",
                "kind": "session",
                "start": "2026-10-15T08:00:00",
                "end": "2026-10-15T23:00:00",
                "regular_minutes": 400,
                "overtime_minutes": 1220,
                "pause_count": 0,
                "target_hit": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    r1 = run_tracker(cfg)
    assert r1.returncode == 0, r1.stderr
    a = (tmp_path / "forecast.json").read_text(encoding="utf-8")
    r2 = run_tracker(cfg)
    assert r2.returncode == 0, r2.stderr
    assert (tmp_path / "forecast.json").read_text(encoding="utf-8") == a
