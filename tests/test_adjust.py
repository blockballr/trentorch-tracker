import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adjust import (
    actual_hours_by_module,
    effective_ratio,
    observed_ratio,
    scale_remaining,
)


def _items():
    return [
        {"id": "01", "title": "A", "hours": 10.0, "kind": "module"},
        {"id": "02", "title": "B", "hours": 10.0, "kind": "module"},
        {"id": "03", "title": "C", "hours": 10.0, "kind": "module"},
    ]


def test_ratio_no_data():
    info = observed_ratio(_items(), {}, set())
    assert info["ratio"] == 1.0
    assert info["applied"] is False


def test_ratio_over_10pct_applies():
    info = observed_ratio(_items(), {"01": 12.0}, set())
    assert abs(info["ratio"] - 1.2) < 1e-9
    assert info["applied"] is True
    assert info["observed_ids"] == ["01"]


def test_ratio_within_10pct_not_applied():
    info = observed_ratio(_items(), {"01": 9.5}, set())
    assert abs(info["ratio"] - 0.95) < 1e-9
    assert info["applied"] is False
    assert effective_ratio(info) == 1.0


def test_completed_without_actuals_excluded_from_ratio():
    info = observed_ratio(_items(), {"01": 12.0}, completed_ids={"02"})
    assert abs(info["ratio"] - 1.2) < 1e-9
    assert "02" not in info["observed_ids"]


def test_multi_module_observed():
    info = observed_ratio(_items(), {"01": 10.0, "02": 15.0}, set())
    assert abs(info["ratio"] - 25.0 / 20.0) < 1e-9
    assert info["applied"] is True


def test_scale_remaining_only():
    items = _items()
    out = scale_remaining(items, 1.5, completed_ids={"01"})
    assert out[0]["hours"] == 10.0
    assert abs(out[1]["hours"] - 15.0) < 1e-9
    assert abs(out[2]["hours"] - 15.0) < 1e-9
    assert items[1]["hours"] == 10.0


def test_scale_ratio_one_unchanged():
    out = scale_remaining(_items(), 1.0, completed_ids=set())
    assert [r["hours"] for r in out] == [10.0, 10.0, 10.0]


def test_actual_hours_from_sessions():
    recs = [
        {"kind": "session", "module": "01", "regular_minutes": 60, "overtime_minutes": 30},
        {"kind": "session", "module": "01", "regular_minutes": 30, "overtime_minutes": 0},
        {"kind": "session", "module": "03", "regular_minutes": 120, "overtime_minutes": 0},
    ]
    acc = actual_hours_by_module(recs)
    assert abs(acc["01"] - 2.0) < 1e-9
    assert abs(acc["03"] - 2.0) < 1e-9
    assert "02" not in acc
