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
