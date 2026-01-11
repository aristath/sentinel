# POST /api/v1/monte-carlo/advanced

Run advanced Monte Carlo evaluation.

**Description:**
Performs advanced Monte Carlo simulation with custom volatilities, drift adjustments, and conservative weighting. Provides enhanced analytics including score distribution metrics and percentile ranges. Useful for sophisticated risk analysis and scenario planning.

**Request:**
- Method: `POST`
- Path: `/api/v1/monte-carlo/advanced`
- Body (JSON):
  ```json
  {
    "sequence": [
      {"type": "BUY", "symbol": "AAPL.US", "quantity": 10}
    ],
    "symbol_volatilities": {
      "AAPL.US": 0.25,
      "MSFT.US": 0.20
    },
    "evaluation_context": {
      "transaction_cost_fixed": 2.0,
      "transaction_cost_percent": 0.002
    },
    "paths": 500,
    "custom_drift": {
      "AAPL.US": 0.05
    },
    "conservative_weight": 0.3
  }
  ```
  - `sequence` (array, required): Trade sequence to evaluate
  - `symbol_volatilities` (object, required): Map of symbol to volatility (0.0-1.0)
  - `evaluation_context` (object, required): Evaluation parameters
  - `paths` (integer, required): Number of Monte Carlo paths (1-1000)
  - `custom_drift` (object, optional): Map of symbol to custom drift adjustment
  - `conservative_weight` (float, optional): Conservative weighting factor (0.0-1.0) for final score calculation

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "result": {
      "final_score": 75.5,
      "worst_score": 65.0,
      "best_score": 85.0,
      "p10_score": 70.0,
      "p90_score": 80.0,
      "avg_score": 75.2,
      "paths": 500
    },
    "advanced_analytics": {
      "volatility_applied": 2,
      "custom_drift_applied": 1,
      "conservative_weight": 0.3,
      "score_distribution": {
        "range": 20.0,
        "p10_to_p90": 10.0,
        "percentile_range_pct": 50.0
      }
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z",
      "elapsed_ms": 250
    }
  }
  ```
  - `result` (object): Monte Carlo result with percentile scores
    - `final_score` (float): Final weighted score (may be adjusted by conservative_weight)
    - `worst_score` (float): Worst-case scenario score
    - `best_score` (float): Best-case scenario score
    - `p10_score` (float): 10th percentile score
    - `p90_score` (float): 90th percentile score
    - `avg_score` (float): Average score across all paths
    - `paths` (integer): Number of paths executed
  - `advanced_analytics` (object): Advanced analytics and configuration
    - `volatility_applied` (integer): Number of custom volatilities applied
    - `custom_drift_applied` (integer): Number of custom drift adjustments applied
    - `conservative_weight` (float): Conservative weighting factor used
    - `score_distribution` (object): Score distribution metrics
      - `range` (float): Range from worst to best score
      - `p10_to_p90` (float): Range from 10th to 90th percentile
      - `percentile_range_pct` (float): Percentile range as percentage of total range
  - `metadata` (object): Response metadata

**Error Responses:**
- `400 Bad Request`: No sequence provided, paths out of range (1-1000), invalid request body
- `500 Internal Server Error`: Monte Carlo evaluation failed
