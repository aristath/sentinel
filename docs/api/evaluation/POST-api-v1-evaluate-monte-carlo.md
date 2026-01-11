# POST /api/v1/evaluate/monte-carlo

Run Monte Carlo evaluation.

**Description:**
Performs Monte Carlo simulation for a sequence, running multiple random scenarios to estimate probability distributions of outcomes.

**Request:**
- Method: `POST`
- Path: `/api/v1/evaluate/monte-carlo`
- Body (JSON):
  ```json
  {
    "sequence": {
      "actions": [...]
    },
    "evaluation_context": {...},
    "iterations": 10000,
    "confidence_level": 0.95
  }
  ```
  - `sequence` (object, required): Trade sequence to evaluate
  - `evaluation_context` (object, required): Evaluation parameters
  - `iterations` (integer, optional): Number of Monte Carlo iterations (default: 10,000)
  - `confidence_level` (float, optional): Confidence level for intervals (default: 0.95)

**Response:**
- Status: `200 OK`
- Body: Monte Carlo results with probability distributions and confidence intervals

**Error Responses:**
- `400 Bad Request`: Invalid request body, invalid iterations
- `500 Internal Server Error`: Monte Carlo simulation failed
