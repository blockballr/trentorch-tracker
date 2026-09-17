import datetime
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sessions
from report import build_report, format_report


@pytest.fixture
def cfg(tmp_path):
    p = tmp_path / "my.yaml"
    p.write_text(
        'hours_per_week: 40\ndays_per_week: 6\noff_day: sunday\n'
        'start_date: "2026-09-15"\nbuffer_pct: 20\ntrentorch_path: "C:/Users/user/TrenTorch"\n',
        encoding="utf-8",
    )
    return p


def test_report_empty_full_curriculum(cfg):
    report = build_report(cfg, base_dir=str(ROOT))
    assert report["totals"]["est_hours"] == 422.0
    assert report["summary"]["actual_hours"] == 0.0
    assert len(report["rows"]) == 26
    row01 = next(r for r in report["rows"] if r["id"] == "01")
    assert row01["est_hours"] == 18.0
    assert row01["vs"] == "not started"
    text = format_report(report)
    assert "Est. Hours" in text
    assert "not started" in text
    assert "Accuracy:" in text


def test_report_actuals_vs_estimates(cfg):
    t0 = datetime.datetime.fromisoformat("2026-10-15T08:00:00")
    sessions.start(cfg, module="01", now=t0)
    sessions.stop(cfg, now=t0 + datetime.timedelta(hours=12, minutes=24))
    report = build_report(cfg, now=t0 + datetime.timedelta(hours=13), base_dir=str(ROOT))
    row = next(r for r in report["rows"] if r["id"] == "01")
    assert row["est_hours"] == 18.0
    assert abs(row["total"] - 12.4) < 0.05
    assert row["vs"] != "not started"
    assert report["summary"]["days_logged"] == 1
    text = format_report(report)
    assert "01" in text and "Accuracy:" in text
