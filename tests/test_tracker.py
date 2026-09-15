def test_math_6day():
    import sys; sys.path.insert(0, "C:/Users/user/trentorch-tracker")
    from core import compute_forecast
    items = [{"id": "01", "title": "T", "hours": 18, "kind": "module"}]
    rows, summary = compute_forecast(items, set(), 40, 6, "sunday", "2026-09-15", 0)
    assert abs(summary["daily_hours"] - 6.6667) < 0.01
    assert summary["weeks"] == 18 / 40
