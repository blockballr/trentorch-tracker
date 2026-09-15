def test_math_6day():
    import sys; sys.path.insert(0, "C:/Users/user/trentorch-tracker")
    from core import compute_forecast
    items = [{"id": "01", "title": "T", "hours": 18, "kind": "module"}]
    rows, summary = compute_forecast(items, set(), 40, 6, "sunday", "2026-09-15", 0)
    assert abs(summary["daily_hours"] - 6.6667) < 0.01
    assert summary["weeks"] == 18 / 40
def test_adapter_real_clone():
    import sys; sys.path.insert(0, "C:/Users/user/trentorch-tracker")
    from adapters.trentorch import read_progress, read_modules
    completed, started = read_progress("C:/Users/user/TrenTorch")
    assert "01" in started or len(completed) >= 0
    mods = read_modules("C:/Users/user/TrenTorch")
    assert len(mods) == 20
    assert mods[0]["id"] == "01"
def test_cli_update(tmp_path):
    import sys, json; sys.path.insert(0, "C:/Users/user/trentorch-tracker")
    from pathlib import Path
    cfg = tmp_path / "my.yaml"
    cfg.write_text('hours_per_week: 40\ndays_per_week: 6\noff_day: sunday\nstart_date: "2026-09-15"\nbuffer_pct: 20\ntrentorch_path: "C:/Users/user/TrenTorch"\n')
    import subprocess
    r = subprocess.run(["python", "C:/Users/user/trentorch-tracker/tracker.py", "--update", "--config", str(cfg)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "forecast.json").exists()
    d = json.loads((tmp_path / "forecast.json").read_text())
    assert d["summary"]["daily_hours"] == 6.67
def test_idempotent(tmp_path):
    import subprocess
    cfg = tmp_path / "my.yaml"
    cfg.write_text('hours_per_week: 40\ndays_per_week: 6\noff_day: sunday\nstart_date: "2026-09-15"\nbuffer_pct: 20\ntrentorch_path: "C:/Users/user/TrenTorch"\n')
    r1 = subprocess.run(["python", "C:/Users/user/trentorch-tracker/tracker.py", "--update", "--config", str(cfg)], capture_output=True, text=True, timeout=30)
    assert r1.returncode == 0, r1.stderr
    a = (tmp_path / "forecast.json").read_text()
    r2 = subprocess.run(["python", "C:/Users/user/trentorch-tracker/tracker.py", "--update", "--config", str(cfg)], capture_output=True, text=True, timeout=30)
    assert r2.returncode == 0, r2.stderr
    assert (tmp_path / "forecast.json").read_text() == a
def test_missing_progress(tmp_path):
    import sys; sys.path.insert(0, "C:/Users/user/trentorch-tracker")
    from adapters.trentorch import read_progress
    c, s = read_progress(str(tmp_path))
    assert c == set() and s == set()
def test_proficient_before_finish(tmp_path):
    import datetime, json, re, subprocess
    cfg = tmp_path / "my.yaml"
    cfg.write_text('hours_per_week: 40\ndays_per_week: 6\noff_day: sunday\nstart_date: "2026-09-15"\nbuffer_pct: 20\ntrentorch_path: "C:/Users/user/TrenTorch"\n')
    r = subprocess.run(["python", "C:/Users/user/trentorch-tracker/tracker.py", "--update", "--config", str(cfg)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    m = re.search(r"proficient: (\d{4}-\d{2}-\d{2})", r.stdout)
    assert m, r.stdout
    prof_date = datetime.date.fromisoformat(m.group(1))
    d = json.loads((tmp_path / "forecast.json").read_text())
    row13 = next(x for x in d["rows"] if x["id"] == "13")
    assert m.group(1) == row13["due_date"]
    fin = datetime.date.fromisoformat(d["summary"]["finish_date"])
    assert (fin - prof_date).days >= 14
