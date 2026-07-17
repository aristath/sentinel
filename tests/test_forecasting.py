import math
import os
import tempfile
from datetime import datetime, timedelta

import pytest
import pytest_asyncio

from sentinel.database import Database
from sentinel.forecasting import (
    adjusted_opportunity_score,
    align_weekly_return_series,
    build_weekly_return_series,
    combine_forecast_scores,
    score_forecast_return,
)
from sentinel.forecasting.service import _prepare_toto2_batch, _toto2_series_ids
from sentinel.jobs.tasks import _points_and_scores_from_forecast


@pytest_asyncio.fixture
async def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    await db.connect()
    yield db
    await db.close()
    db.remove_from_cache()
    if os.path.exists(path):
        os.remove(path)


def test_weekly_return_series_uses_last_close_in_week():
    rows = [
        {"date": "2026-01-05", "close": 100},
        {"date": "2026-01-07", "close": 110},
        {"date": "2026-01-12", "close": 121},
    ]

    series = build_weekly_return_series(rows)

    assert len(series) == 1
    assert series[0].week_start == "2026-01-12"
    assert series[0].value == pytest.approx(math.log(121 / 110))


def test_alignment_preserves_missing_values_as_masks():
    a = build_weekly_return_series(
        [
            {"date": "2026-01-05", "close": 100},
            {"date": "2026-01-12", "close": 101},
            {"date": "2026-01-19", "close": 102},
        ]
    )
    b = build_weekly_return_series(
        [
            {"date": "2026-01-05", "close": 200},
            {"date": "2026-01-19", "close": 210},
        ]
    )

    aligned = align_weekly_return_series({"A": a, "B": b}, max_points=10)

    assert [row["mask"] for row in aligned["A"]] == [True, True]
    assert [row["mask"] for row in aligned["B"]] == [False, True]


def test_forecast_scoring_and_combination():
    scored = score_forecast_return(median_return=0.025)
    assert scored["score"] == pytest.approx(0.75)

    combined = combine_forecast_scores(
        {
            "solo": {
                "forecast_return_4w": 0.02,
                "q10_return_4w": -0.01,
                "q90_return_4w": 0.05,
                "score": 0.7,
            },
            "grouped": {
                "forecast_return_4w": 0.03,
                "q10_return_4w": 0.0,
                "q90_return_4w": 0.07,
                "score": 0.8,
            },
        }
    )
    assert combined is not None
    assert combined["forecast_return_4w"] == pytest.approx(0.025)
    assert combined["agreement"] == pytest.approx(0.9)
    assert "confidence" not in combined


def test_adjusted_opportunity_score_is_bounded_modifier():
    assert adjusted_opportunity_score(
        current_opp_score=0.5,
        forecast_score=1.0,
        weight=0.15,
    ) == pytest.approx(0.65)
    assert adjusted_opportunity_score(
        current_opp_score=0.05,
        forecast_score=0.0,
        weight=0.15,
    ) == pytest.approx(0.0)


def test_toto2_batch_preparation_keeps_newest_patch_aligned_context():
    values = [list(range(520)), list(range(1000, 1520))]
    masks = [[True] * 520, [True] * 520]

    prepared_values, prepared_masks = _prepare_toto2_batch(values, masks)

    assert len(prepared_values[0]) == 512
    assert len(prepared_values[1]) == 512
    assert prepared_values[0][0] == 8
    assert prepared_values[0][-1] == 519
    assert all(prepared_masks[0])


def test_toto2_grouped_series_ids_allow_variate_attention():
    assert _toto2_series_ids(1) == [[0]]
    assert _toto2_series_ids(4) == [[0, 0, 0, 0]]


def test_service_payload_converts_to_points_and_scores():
    payload = {
        "batches": [
            {
                "scope": "solo",
                "forecasts": {
                    "AAA": [
                        {"step": 1, "quantiles": {str(q / 10): 0.01 for q in range(1, 10)}},
                        {"step": 2, "quantiles": {str(q / 10): 0.01 for q in range(1, 10)}},
                        {"step": 3, "quantiles": {str(q / 10): 0.01 for q in range(1, 10)}},
                        {"step": 4, "quantiles": {str(q / 10): 0.01 for q in range(1, 10)}},
                    ]
                },
            }
        ]
    }

    points, scores = _points_and_scores_from_forecast(12, payload, 4)

    assert len(points) == 4
    assert points[-1]["cumulative_q50"] == pytest.approx(math.exp(0.04) - 1)
    combined = [score for score in scores if score["scope"] == "combined"][0]
    assert combined["symbol"] == "AAA"
    assert combined["forecast_return_4w"] == pytest.approx(math.exp(0.04) - 1)


@pytest.mark.asyncio
async def test_forecast_database_round_trip(temp_db):
    run_id = await temp_db.create_forecast_run(
        provider="naive",
        model_id="local",
        model_version="local",
        input_frequency="1w_log_return",
        horizon_steps=4,
        context_weeks=104,
    )
    await temp_db.store_forecast_points(
        [
            {
                "run_id": run_id,
                "symbol": "AAA",
                "scope": "solo",
                "horizon_step": 4,
                "q50": 0.01,
                "cumulative_q50": 0.04,
            }
        ]
    )
    await temp_db.store_forecast_scores(
        [
            {
                "run_id": run_id,
                "symbol": "AAA",
                "scope": "combined",
                "forecast_return_4w": 0.04,
                "q10_return_4w": -0.01,
                "q90_return_4w": 0.08,
                "agreement": 1.0,
                "score": 0.9,
            }
        ]
    )
    await temp_db.finish_forecast_run(run_id, status="completed")

    scores = await temp_db.get_latest_forecast_scores(["AAA"])
    assert scores["AAA"]["forecast_return_4w"] == pytest.approx(0.04)
    points = await temp_db.get_latest_forecast_points("AAA")
    assert points["solo"][0]["cumulative_q50"] == pytest.approx(0.04)


@pytest.mark.asyncio
async def test_mature_forecast_evaluation_query(temp_db):
    run_id = await temp_db.create_forecast_run(
        provider="naive",
        model_id="local",
        model_version="local",
        input_frequency="1w_log_return",
        horizon_steps=4,
        context_weeks=104,
    )
    old_ts = int((datetime.now() - timedelta(weeks=5)).timestamp())
    await temp_db.conn.execute(
        "UPDATE forecast_runs SET started_at = ?, status = 'completed' WHERE id = ?",
        (old_ts, run_id),
    )
    await temp_db.store_forecast_points(
        [
            {
                "run_id": run_id,
                "symbol": "AAA",
                "scope": "solo",
                "horizon_step": 4,
                "cumulative_q50": 0.02,
            }
        ]
    )

    rows = await temp_db.get_mature_forecasts_for_evaluation(horizon_steps=4)

    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAA"
