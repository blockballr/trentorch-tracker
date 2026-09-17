import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REAL_CLONE = Path("C:/Users/user/TrenTorch")


def make_synthetic_clone(base: Path) -> str:
    (base / "user_data").mkdir(parents=True, exist_ok=True)
    (base / "user_data" / "progress.json").write_text(
        json.dumps({"started_modules": ["01"], "completed_modules": []})
    )
    src = base / "data" / "src"
    src.mkdir(parents=True, exist_ok=True)
    for i in range(1, 21):
        mod_id = f"{i:02d}"
        d = src / f"{mod_id}_mod"
        d.mkdir(parents=True, exist_ok=True)
        (d / "module.yaml").write_text(f"title: Module {mod_id}\n")
    return str(base)


def write_cfg(tmp_path: Path, clone: str) -> Path:
    cfg = tmp_path / "my.yaml"
    posix = Path(clone).as_posix()
    cfg.write_text(
        'hours_per_week: 40\ndays_per_week: 6\noff_day: sunday\n'
        f'start_date: "2026-09-15"\nbuffer_pct: 20\ntrentorch_path: "{posix}"\n'
    )
    return cfg


def test_math_6day():
    from core import compute_forecast
    items = [{"id": "01", "title": "T", "hours": 18, "kind": "module"}]
    rows, summary = compute_forecast(items, set(), 40, 6, "sunday", "2026-09-15", 0)
    assert abs(summary["daily_hours"] - 6.6667) < 0.01
    assert summary["weeks"] == 18 / 40


def test_adapter_synthetic_exact(tmp_path):
    from adapters.trentorch import read_progress, read_modules
    clone = make_synthetic_clone(tmp_path / "clone")
    completed, started = read_progress(clone)
    assert started == {"01"} and completed == set()
    mods = read_modules(clone)
    assert len(mods) == 20
    assert mods[0]["id"] == "01" and mods[0]["title"] == "Module 01"


@pytest.mark.skipif(not REAL_CLONE.exists(), reason="real clone not present")
def test_adapter_real_clone():
    from adapters.trentorch import read_modules
    mods = read_modules(str(REAL_CLONE))
    assert len(mods) == 20
    assert {m["id"] for m in mods} == {f"{i:02d}" for i in range(1, 21)}


def test_cli_update(tmp_path):
    clone = make_synthetic_clone(tmp_path / "clone")
    cfg = write_cfg(tmp_path, clone)
    r = subprocess.run(
        [sys.executable, str(ROOT / "tracker.py"), "--update", "--config", str(cfg)],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "forecast.json").exists()
    d = json.loads((tmp_path / "forecast.json").read_text())
    assert d["summary"]["daily_hours"] == 6.67


def test_idempotent(tmp_path):
    clone = make_synthetic_clone(tmp_path / "clone")
    cfg = write_cfg(tmp_path, clone)
    cmd = [sys.executable, str(ROOT / "tracker.py"), "--update", "--config", str(cfg)]
    r1 = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert r1.returncode == 0, r1.stderr
    a = (tmp_path / "forecast.json").read_text()
    r2 = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert r2.returncode == 0, r2.stderr
    assert (tmp_path / "forecast.json").read_text() == a


def test_missing_progress(tmp_path):
    from adapters.trentorch import read_progress
    c, s = read_progress(str(tmp_path))
    assert c == set() and s == set()


def test_proficient_before_finish(tmp_path):
    import datetime
    clone = make_synthetic_clone(tmp_path / "clone")
    cfg = write_cfg(tmp_path, clone)
    r = subprocess.run(
        [sys.executable, str(ROOT / "tracker.py"), "--update", "--config", str(cfg)],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stderr
    m = re.search(r"Module 13 .*?: (\d{4}-\d{2}-\d{2})", r.stdout)
    assert m, r.stdout
    prof_date = datetime.date.fromisoformat(m.group(1))
    d = json.loads((tmp_path / "forecast.json").read_text())
    row13 = next(x for x in d["rows"] if x["id"] == "13")
    assert m.group(1) == row13["due_date"]
    fin = datetime.date.fromisoformat(d["summary"]["finish_date"])
    assert (fin - prof_date).days >= 14


def test_weeks_invariant_across_days():
    from core import compute_forecast
    items = [{"id": "01", "title": "T", "hours": 40, "kind": "module"}]
    _, s5 = compute_forecast(items, set(), 40, 5, "sunday", "2026-09-15", 20)
    _, s6 = compute_forecast(items, set(), 40, 6, "sunday", "2026-09-15", 20)
    _, s7 = compute_forecast(items, set(), 40, 7, "sunday", "2026-09-15", 20)
    assert s5["weeks"] == s6["weeks"] == s7["weeks"]
    assert abs(s5["daily_hours"] - 8.0) < 0.01
    assert abs(s7["daily_hours"] - 40 / 7) < 0.01


def test_cli_invalid_days_exit_2(tmp_path):
    clone = make_synthetic_clone(tmp_path / "clone")
    cfg = tmp_path / "bad.yaml"
    cfg.write_text(
        "hours_per_week: 40\ndays_per_week: 4\n"
        f'start_date: "2026-09-15"\ntrentorch_path: "{Path(clone).as_posix()}"\n'
    )
    r = subprocess.run(
        [sys.executable, str(ROOT / "tracker.py"), "--update", "--config", str(cfg)],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 2
    assert "days_per_week" in (r.stderr + r.stdout).lower()


def test_cli_missing_path_exit_2(tmp_path):
    cfg = tmp_path / "nop.yaml"
    cfg.write_text('hours_per_week: 40\ndays_per_week: 6\nstart_date: "2026-09-15"\n')
    r = subprocess.run(
        [sys.executable, str(ROOT / "tracker.py"), "--update", "--config", str(cfg)],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 2
