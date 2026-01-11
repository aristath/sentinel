# POST /api/optimizer/run

Run portfolio optimization.

**Description:**
Triggers a portfolio optimization run. The optimizer calculates optimal target allocations based on current portfolio state, allocation targets, and optimization strategy (Mean-Variance, HRP, or adaptive blend). Fetches securities, positions, prices, cash balance, allocation targets, and dividend bonuses, then runs optimization and caches the result.

**Request:**
- Method: `POST`
- Path: `/api/optimizer/run`
- Body: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "success": true,
    "result": {
      "target_weights": {
        "AAPL.US": 0.10,
        "MSFT.US": 0.08,
        "EUR": 0.05
      },
      "optimization_method": "mean_variance",
      "blend_used": 0.75,
      "portfolio_value": 50000.00,
      "duration_seconds": 12.5
    },
    "timestamp": "2024-01-15T10:30:00Z"
  }
  ```
  - `success`: Whether optimization completed successfully
  - `result.target_weights`: Optimal target weights by symbol
  - `result.optimization_method`: Method used (mean_variance, hrp, or adaptive)
  - `result.blend_used`: Actual blend used (adaptive blend, not user setting)

**Error Responses:**
- `400 Bad Request`: No securities in universe
- `500 Internal Server Error`: Failed to get settings, securities, positions, prices; optimization failed

**Side Effects:**
- Calculates new target allocations
- Updates optimizer cache with last result
- Results can be used by planning system
