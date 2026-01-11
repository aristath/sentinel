# POST /api/v1/evaluate/stochastic

Run stochastic evaluation.

**Description:**
Performs stochastic evaluation of a trade sequence, evaluating multiple scenarios with different market conditions and weighting them to produce a weighted score. Useful for assessing sequence performance under uncertainty.

**Request:**
- Method: `POST`
- Path: `/api/v1/evaluate/stochastic`
- Body (JSON):
  ```json
  {
    "sequence": [
      {"type": "BUY", "symbol": "AAPL.US", "quantity": 10}
    ],
    "evaluation_context": {
      "transaction_cost_fixed": 2.0,
      "transaction_cost_percent": 0.002
    }
  }
  ```
  - `sequence` (array, required): Trade sequence to evaluate
  - `evaluation_context` (object, required): Evaluation parameters

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "scenarios_evaluated": 50,
    "weighted_score": 75.5,
    "feasible": true,
    "score_distribution": {
      "min": 65.0,
      "max": 85.0,
      "median": 76.0
    }
  }
  ```
  - `scenarios_evaluated` (integer): Number of stochastic scenarios evaluated
  - `weighted_score` (float): Weighted average score across all scenarios
  - `feasible` (boolean): Whether the sequence is feasible
  - `score_distribution` (object, optional): Score distribution statistics

**Error Responses:**
- `400 Bad Request`: No sequence provided, invalid request body
- `500 Internal Server Error`: Stochastic evaluation failed
