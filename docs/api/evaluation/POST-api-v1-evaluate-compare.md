# POST /api/v1/evaluate/compare

Compare multiple sequences.

**Description:**
Evaluates multiple trade sequences and returns comparison metrics including best/worst scores, score ranges, and feasibility analysis. Used to compare different trading strategies or sequences side-by-side.

**Request:**
- Method: `POST`
- Path: `/api/v1/evaluate/compare`
- Body (JSON):
  ```json
  {
    "sequences": [
      [
        {"type": "BUY", "symbol": "AAPL.US", "quantity": 10}
      ],
      [
        {"type": "BUY", "symbol": "MSFT.US", "quantity": 15}
      ]
    ],
    "evaluation_context": {
      "transaction_cost_fixed": 2.0,
      "transaction_cost_percent": 0.002
    }
  }
  ```
  - `sequences` (array, required): Array of trade sequences to compare (2-100 sequences)
  - `evaluation_context` (object, required): Evaluation parameters

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "results": [
      {
        "sequence_id": 0,
        "score": 75.5,
        "feasible": true
      },
      {
        "sequence_id": 1,
        "score": 82.3,
        "feasible": true
      }
    ],
    "comparison": {
      "count": 2,
      "best_index": 1,
      "worst_index": 0,
      "best_score": 82.3,
      "worst_score": 75.5,
      "score_range": 6.8,
      "all_feasible": true,
      "evaluation_time_ms": 125
    }
  }
  ```
  - `results` (array): Evaluation results for each sequence
  - `comparison` (object): Comparison metrics
    - `count` (integer): Number of sequences compared
    - `best_index` (integer): Index of sequence with highest score
    - `worst_index` (integer): Index of sequence with lowest score
    - `best_score` (float): Highest evaluation score
    - `worst_score` (float): Lowest evaluation score
    - `score_range` (float): Difference between best and worst scores
    - `all_feasible` (boolean): Whether all sequences are feasible
    - `evaluation_time_ms` (integer): Evaluation time in milliseconds

**Error Responses:**
- `400 Bad Request`: Less than 2 sequences provided, more than 100 sequences, invalid request body
- `500 Internal Server Error`: Evaluation failed
