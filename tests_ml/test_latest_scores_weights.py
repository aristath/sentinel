from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel_ml.api.routers.ml import get_latest_scores
from sentinel_ml.utils.weights import compute_weighted_blend


def test_compute_weighted_blend_handles_missing_components():
    components = {"wavelet": 0.6, "xgboost": None, "ridge": 0.4}
    weights = {"wavelet": 0.25, "xgboost": 0.5, "ridge": 0.25}
    result = compute_weighted_blend(components, weights)
    # availability-aware renormalization => (0.6*0.25 + 0.4*0.25) / 0.5
    assert result == pytest.approx(0.5)


def test_compute_weighted_blend_zero_total_returns_none():
    assert compute_weighted_blend({"wavelet": None}, {"wavelet": 0.0}) is None


@pytest.mark.asyncio
async def test_latest_scores_includes_wavelet_weight_in_final_score():
    deps = MagicMock()
    deps.monolith.get_settings = AsyncMock(
        return_value={
            "ml_weight_wavelet": 0.5,
            "ml_weight_xgboost": 0.5,
            "ml_weight_ridge": 0.0,
            "ml_weight_rf": 0.0,
            "ml_weight_svr": 0.0,
        }
    )
    deps.monolith.get_scores = AsyncMock(return_value={"AAA": 0.2})

    deps.ml_db.get_latest_prediction = AsyncMock(
        side_effect=lambda model_type, symbol: {"ml_score": 0.8, "predicted_return": 0.1, "predicted_at": 1}
        if model_type == "xgboost"
        else None
    )

    result = await get_latest_scores(deps=deps, symbols="AAA")
    score = result["scores"]["AAA"]
    # (0.5*0.2 + 0.5*0.8) / 1.0
    assert score["final_score"] == pytest.approx(0.5)
    assert score["predicted_return"] == pytest.approx(0.15)  # 0.5*0.2 + 0.5*0.1


@pytest.mark.asyncio
async def test_latest_scores_returns_wavelet_only_when_models_missing():
    deps = MagicMock()
    deps.monolith.get_settings = AsyncMock(
        return_value={
            "ml_weight_wavelet": 0.25,
            "ml_weight_xgboost": 0.25,
            "ml_weight_ridge": 0.25,
            "ml_weight_rf": 0.25,
            "ml_weight_svr": 0.25,
        }
    )
    deps.monolith.get_scores = AsyncMock(return_value={"BBB": 0.4})
    deps.ml_db.get_latest_prediction = AsyncMock(return_value=None)

    result = await get_latest_scores(deps=deps, symbols="BBB")
    assert result["scores"]["BBB"]["final_score"] == pytest.approx(0.4)
    assert result["scores"]["BBB"]["predicted_return"] == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_latest_scores_omits_symbols_with_no_available_components():
    deps = MagicMock()
    deps.monolith.get_settings = AsyncMock(
        return_value={
            "ml_weight_wavelet": 0.25,
            "ml_weight_xgboost": 0.25,
            "ml_weight_ridge": 0.25,
            "ml_weight_rf": 0.25,
            "ml_weight_svr": 0.25,
        }
    )
    deps.monolith.get_scores = AsyncMock(return_value={})
    deps.ml_db.get_latest_prediction = AsyncMock(return_value=None)

    result = await get_latest_scores(deps=deps, symbols="CCC")
    assert result == {"scores": {}}
