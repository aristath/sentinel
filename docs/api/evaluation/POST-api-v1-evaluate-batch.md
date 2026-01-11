# POST /api/v1/evaluate/batch

Evaluate multiple sequences in batch.

**Description:**
Evaluates multiple trade sequences in batch, calculating performance metrics for each. Used for comparing and ranking sequences. Supports up to 10,000 sequences per batch.

**Request:**
- Method: `POST`
- Path: `/api/v1/evaluate/batch`
- Body (JSON):
  ```json
  {
    "sequences": [
      {
        "actions": [
          {"type": "BUY", "symbol": "AAPL.US", "quantity": 10}
        ]
      }
    ],
    "evaluation_context": {
      "transaction_cost_fixed": 2.0,
      "transaction_cost_percent": 0.002,
      "initial_portfolio_value": 50000.0
    }
  }
  ```
  - `sequences` (array, required): Trade sequences to evaluate (max 10,000)
  - `evaluation_context` (object, required): Evaluation parameters
    - `transaction_cost_fixed` (float, required): Fixed transaction cost (must be >= 0)
    - `transaction_cost_percent` (float, required): Variable transaction cost (must be >= 0)
    - `initial_portfolio_value` (float, optional): Initial portfolio value

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "results": [
      {
        "sequence_id": 0,
        "final_value": 51000.0,
        "return_pct": 2.0,
        "sharpe_ratio": 1.5,
        "max_drawdown": 0.05
      }
    ],
    "errors": []
  }
  ```

**Error Responses:**
- `400 Bad Request`: No sequences provided, too many sequences (>10,000), negative transaction costs
- `500 Internal Server Error`: Evaluation failed
