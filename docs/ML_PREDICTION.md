# ML-Enhanced Per-Security Prediction

## Overview

The ML prediction system uses a Neural Network + XGBoost ensemble to predict future returns for individual securities. **Each security has its own trained model**, recognizing that different securities behave differently (Apple is not the same as Dunkin' Donuts or Procter & Gamble).

Predictions are blended with wavelet-based scores using a configurable ratio, allowing empirical testing to find the optimal mix.

## Architecture

### Per-Symbol Models

Unlike traditional approaches that train one model on pooled data, this system:
- Trains **separate models per security**
- Each model learns patterns specific to that security
- Models are stored at `data/ml_models/{symbol}/`
- New securities get models once sufficient training data accumulates

### Why Per-Symbol?

Different securities have different:
- Price dynamics and volatility patterns
- Response to market conditions
- Sector-specific behavior
- Correlation structures

A single pooled model would average these differences away. Per-symbol models capture security-specific patterns.

## How It Works

### 1. Feature Extraction

For each security, 20 features are extracted:

**Price & Returns** (4 features):
- `return_1d`, `return_5d`, `return_20d`, `return_60d`

**Price Position** (1 feature):
- `price_normalized` (vs 200-day MA)

**Volatility** (3 features):
- `volatility_10d`, `volatility_30d`
- `atr_14d` (Average True Range)

**Volume** (2 features):
- `volume_normalized` (vs 20-day avg)
- `volume_trend` (increasing/decreasing)

**Technical Indicators** (3 features):
- `rsi_14` (Relative Strength Index)
- `macd` (Moving Average Convergence Divergence)
- `bollinger_position` (price position in Bollinger Bands)

**Wavelet Components** (2 features):
- `wavelet_d1` (short-term momentum)
- `wavelet_d4` (medium-term trend)

**Sentiment** (1 feature):
- `sentiment_score`

**Market Context** (4 features):
- `market_return_20d` (market average performance)
- `market_volatility` (normalized market volatility)
- `market_regime` (0=Bear, 1=Sideways, 2=Bull)
- `sector_relative_strength` (sector vs market)

### 2. ML Prediction

Each symbol's ensemble predicts the **expected return** over the next 14 days:
1. Neural Network prediction (64→32→16 architecture)
2. XGBoost prediction (150 estimators, max_depth=4)
3. 50-50 weighted blend

### 3. Score Blending

The predicted return is normalized to a 0-1 score and blended with the wavelet score:

```
final_score = (1 - blend_ratio) * wavelet_score + blend_ratio * ml_score
```

Where `blend_ratio` ranges from 0.0 (pure wavelet) to 1.0 (pure ML).

**Return to Score Mapping**:
- -10% predicted return → 0.0 score
- 0% predicted return → 0.5 score
- +10% predicted return → 1.0 score

### 4. Weekly Retraining

Every Sunday at 23:00:
- New training samples generated from recent 90-day window
- Each symbol's model retrained on its full historical data
- New model overwrites existing model

## Configuration

Settings (via `/api/settings` or web UI):

```json
{
  "ml_enabled": true,
  "ml_wavelet_blend_ratio": 0.3,
  "ml_retrain_weekly": true,
  "ml_prediction_horizon_days": 14,
  "ml_min_samples_per_symbol": 100
}
```

**Key Settings**:
- `ml_enabled`: Enable/disable ML predictions
- `ml_wavelet_blend_ratio`: Blend ratio (0.0 = pure wavelet, 1.0 = pure ML)
- `ml_retrain_weekly`: Auto-retrain weekly
- `ml_min_samples_per_symbol`: Minimum samples required to train a model for a symbol

## Initial Setup

### 1. Install Dependencies

```bash
poetry install
```

This installs: `tensorflow>=2.15.0`, `xgboost>=2.0.0`, `ta>=0.11.0`

### 2. Generate Training Data

```bash
python scripts/generate_ml_training_data.py
```

This creates training samples from historical data (2017-present) for each symbol in the universe.

### 3. Train Initial Models

```bash
python scripts/train_initial_ml_models.py
```

Trains one NN + XGBoost ensemble per symbol that has sufficient training data.

### 4. Enable ML

Via API:
```bash
curl -X POST http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"ml_enabled": true, "ml_wavelet_blend_ratio": 0.3}'
```

Or via web UI: Settings → ML Configuration

## API Endpoints

### Get ML Status
```bash
GET /api/ml/status
```

Returns:
```json
{
  "enabled": true,
  "blend_ratio": 0.3,
  "symbols_with_models": 45,
  "total_training_samples": 154200,
  "aggregate_metrics": {
    "avg_validation_rmse": 0.0234,
    "avg_validation_mae": 0.0187,
    "avg_validation_r2": 0.42,
    "total_trained_samples": 154200
  }
}
```

### Retrain All Models
```bash
POST /api/ml/retrain
```

Returns:
```json
{
  "status": "completed",
  "symbols_trained": 45,
  "symbols_skipped": 3,
  "results": {
    "AAPL": {"validation_rmse": 0.021, "validation_r2": 0.48},
    "MSFT": {"validation_rmse": 0.023, "validation_r2": 0.44}
  }
}
```

### Retrain Single Symbol
```bash
POST /api/ml/retrain/{symbol}
```

### List Per-Symbol Models
```bash
GET /api/ml/models
```

Returns:
```json
{
  "models": [
    {
      "symbol": "AAPL",
      "training_samples": 3420,
      "validation_rmse": 0.021,
      "validation_mae": 0.016,
      "validation_r2": 0.48,
      "last_trained_at": "2025-01-27T12:00:00"
    }
  ]
}
```

### Get Specific Symbol's Model
```bash
GET /api/ml/models/{symbol}
```

### Get Performance Metrics
```bash
GET /api/ml/performance
```

## Storage Structure

```
data/ml_models/
  AAPL/
    nn_model.keras
    nn_scaler.pkl
    nn_metadata.json
    xgb_model.json
    xgb_scaler.pkl
    xgb_metadata.json
    ensemble_metadata.json
  MSFT/
    ...
  GOOG/
    ...
```

Each symbol has its own directory with model files.

## Historical Predictions and As-Of Semantics

### ML predictions (historical)

- **One row per (symbol, date)** in `ml_predictions`. Column `predicted_at` is a Unix timestamp (end-of-day for that date).
- **Backfill**: `scripts/backfill_ml_predictions.py` runs the **current** model on historical features for each date: wavelet score as-of that date, features from prices up to that date, regime from OHLCV via `quote_data_from_prices(prices)`.
- **Regime on each row**: Columns `regime_score` and `regime_dampening` store the quote-based regime used for that prediction (from `get_regime_adjusted_return` with `quote_data` from OHLCV when backfilling).

### Wavelet score as-of date

- **`get_score(symbol, as_of_date=None)`** (database): If `as_of_date` is set (Unix timestamp), returns the latest score with `calculated_at <= as_of_date`. If `None`, returns the latest score.
- **`get_scores(symbols, as_of_date=None)`**: Same semantics per symbol.
- **`Security.get_score(as_of_date=None)`**: Passes `as_of_date` through to the database. Used by backtester/API when score as of date T is needed.

### ML prediction as-of

- **`get_ml_prediction_as_of(symbol, as_of_ts)`** (database): Returns the most recent `ml_predictions` row for `symbol` with `predicted_at <= as_of_ts` (one row, or `None`). Used by backtester and API for historical ML score.

### HMM regime_states (historical)

- **Quote-based regime**: The continuous `regime_score` and `regime_dampening` are computed from quote data (live or from OHLCV) and stored on each ML prediction.
- **HMM discrete regime**: The `regime_states` table stores (symbol, date, regime, regime_name, confidence) from the HMM model. **Backfill**: `scripts/backfill_regime_states.py` fills historical rows using the current HMM model and features truncated to each date.
- **RegimeDetector as-of API**: `detect_regime_as_of(symbol, date_str)` returns `{regime, regime_name, confidence}` for that date (or `None` if insufficient data). `store_regime_state_for_date(symbol, date_str, regime, regime_name, confidence)` writes one row; idempotent (INSERT OR REPLACE).

### Running the backfill scripts

From the repo root with the virtual environment activated:

1. **Regime states** (optional; can run before or after ML backfill):
   ```bash
   python scripts/backfill_regime_states.py
   ```
   - Fills `regime_states` with historical HMM labels for each (symbol, date).
   - Requires price data; uses the current HMM model and ~2 years of lookback. Skips dates with insufficient data.
   - Resumable: skips existing (symbol, date) rows.

2. **ML predictions**:
   ```bash
   python scripts/backfill_ml_predictions.py
   ```
   - Fills `ml_predictions` with historical rows (one per symbol per date).
   - Requires: price data and trained models for symbols with `ml_enabled` (run training at least once).
   - Resumable: skips existing (symbol, predicted_at) rows.
   - Uses wavelet score as-of each date, features from prices up to that date, and regime from OHLCV.

Run price sync and (if needed) model training before backfilling. Both scripts log progress and commit periodically.

### Backtester (per-day historical data)

The backtester uses **point-in-time** data for each simulation day:

- **Wavelet scores**: Each rebalance day it runs `Analyzer.update_scores()` against the simulation DB (which has `set_simulation_date(current_date)`), so prices and scores are computed only from data on or before that day.
- **Prices in recommendations**: When generating recommendations, the Planner is called with `as_of_date=self._simulation_date`. The RebalanceEngine then uses `db.get_prices(symbol, days=250, end_date=as_of_date)` and `today=as_of_date` for feature extraction and ML, so no future data leaks into the rebalance logic.
- **ML**: `predict_and_blend` runs each rebalance day with that day’s wavelet score and features (from prices up to `as_of_date`), so ML is effectively as-of that date.

## New Securities

When a new security is added to the universe:

1. Historical data is fetched (typically 10 years)
2. Training samples are generated during next data generation run
3. Once `ml_min_samples_per_symbol` samples exist, a model is trained
4. Until then, the security uses wavelet-only scoring (fallback)

No manual intervention required - the system handles this automatically during weekly retraining.

## Monitoring

### Performance Tracking

The system tracks:
- **MAE** (Mean Absolute Error): Average prediction error
- **RMSE** (Root Mean Squared Error): Prediction accuracy
- **R²**: Model explanatory power
- **Drift**: Model degradation over time

### Per-Symbol Metrics

Each symbol's model has its own validation metrics, visible via:
- `GET /api/ml/models` (all symbols)
- `GET /api/ml/models/{symbol}` (specific symbol)

## Troubleshooting

### Q: Symbol doesn't have ML predictions?

Check if model exists:
```bash
curl http://localhost:8000/api/ml/models/{symbol}
```

If no model:
1. Check training sample count (need `ml_min_samples_per_symbol` samples)
2. Run `POST /api/ml/retrain/{symbol}` to trigger training
3. The symbol will use wavelet-only fallback until a model is trained

### Q: How do I switch back to pure wavelet?

Set `ml_wavelet_blend_ratio` to `0.0`:
```bash
curl -X POST http://localhost:8000/api/settings \
  -d '{"ml_wavelet_blend_ratio": 0.0}'
```

Or disable ML entirely:
```bash
curl -X POST http://localhost:8000/api/settings \
  -d '{"ml_enabled": false}'
```

### Q: How much disk space is needed?

- Per symbol: ~5 MB
- 50 symbols: ~250 MB
- 100 symbols: ~500 MB

Each symbol has only one model (no versioning), keeping storage minimal.

## Performance Expectations

**Validation Metrics** (typical per-symbol):
- MAE: 0.015 - 0.030 (1.5-3% prediction error)
- RMSE: 0.020 - 0.040
- R²: 0.20 - 0.55 (varies by security)

**Inference**:
- < 10ms per security prediction
- Models cached in memory for fast access

**Training**:
- Initial: Depends on universe size (1-2 min per symbol)
- Weekly: Same (full retrain per symbol)

## Best Practices

1. **Start Conservative**: Begin with `blend_ratio=0.2` (80% wavelet, 20% ML)
2. **Backtest First**: Test different ratios before deploying
3. **Monitor Per-Symbol**: Some symbols may have better ML predictions than others
4. **Allow Learning Time**: Model quality improves as more data accumulates
5. **Keep Retraining On**: Weekly retraining adapts to market changes

## Technical Details

**Neural Network Architecture**:
- Input: 20 features
- Hidden layers: 64 → 32 → 16 neurons
- Output: 1 (predicted return)
- Activation: ReLU (hidden), Linear (output)
- Regularization: BatchNorm + Dropout (0.3, 0.2, 0.1)
- Optimizer: Adam (lr=0.001)
- Loss: MSE

**XGBoost Configuration**:
- n_estimators: 150
- max_depth: 4
- learning_rate: 0.05
- subsample: 0.8
- colsample_bytree: 0.8

**Ensemble**:
- 50% Neural Network + 50% XGBoost
- Predictions averaged

**Training Data Per Symbol**:
- Rolling 7-day windows from historical data
- Features extracted at time T
- Label = actual return from T to T+14 days
- Typical: 300-500 samples per symbol (10 years of weekly windows)

## Centralized Feature Definitions

All feature names and their order are defined in `sentinel/ml_features.py`:

```python
from sentinel.ml_features import FEATURE_NAMES, NUM_FEATURES, DEFAULT_FEATURES
```

This ensures consistency between training and inference.
