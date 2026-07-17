import math
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sentinel.snapshot_service import _format_progress, _midnight_utc_ts, _snapshot_write_plan


def test_format_progress_includes_percent_and_eta():
    text = _format_progress(start_ts=0.0, current_idx=50, total=200, date_str="2026-02-05", now_ts=100.0)
    assert "50/200" in text
    assert "25.0%" in text
    assert "eta" in text
    assert "2026-02-05" in text
    assert "elapsed" in text
    assert "s" in text
    assert not math.isnan(float(text.split("eta=")[1].split("s")[0]))


def test_snapshot_write_plan_refreshes_recent_existing_dates():
    today = date(2026, 7, 17)
    all_dates = [(today - timedelta(days=days)).isoformat() for days in range(40, -1, -1)]
    all_timestamps = [_midnight_utc_ts(iso) for iso in all_dates]
    existing = set(all_timestamps)

    plan = _snapshot_write_plan(all_dates, all_timestamps, existing, today=today, tail_days=30)

    assert plan[0][0] == "2026-06-17"
    assert plan[-1][0] == "2026-07-17"
    assert len(plan) == 31


def test_snapshot_write_plan_includes_missing_old_dates():
    today = date(2026, 7, 17)
    all_dates = [(today - timedelta(days=days)).isoformat() for days in range(40, -1, -1)]
    all_timestamps = [_midnight_utc_ts(iso) for iso in all_dates]
    missing_old = _midnight_utc_ts("2026-06-10")
    existing = set(all_timestamps) - {missing_old}

    plan = _snapshot_write_plan(all_dates, all_timestamps, existing, today=today, tail_days=30)

    assert ("2026-06-10", missing_old) in plan
