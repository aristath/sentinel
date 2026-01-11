# POST /api/v1/evaluate/single

Evaluate a single sequence.

**Description:**
Evaluates a single trade sequence, calculating performance metrics and allocation fit. This is a convenience endpoint for evaluating one sequence at a time, internally using the batch evaluation service.

**Request:**
- Method: `POST`
- Path: `/api/v1/evaluate/single`
- Body (JSON):
  ```json
  {
    "sequence": [
      {"type": "BUY", "symbol": "AAPL.US", "quantity": 10}
    ],
    "evaluation_context": {
      "transaction_cost_fixed": 2.0,
      "transaction_cost_percent": 0.002,
      "initial_portfolio_value": 50000.0
    }
  }
  ```
  - `sequence` (array, required): Trade sequence to evaluate (array of action candidates)
  - `evaluation_context` (object, required): Evaluation parameters
    - `transaction_cost_fixed` (float, required): Fixed transaction cost
    - `transaction_cost_percent` (float, required): Variable transaction cost percentage
    - `initial_portfolio_value` (float, optional): Initial portfolio value

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "sequence_id": 0,
    "score": 75.5,
    "feasible": true,
    "allocation_fit": 80.0,
    "transaction_costs": 4.5,
    "final_portfolio_value": 50045.5
  }
  ```
  - `sequence_id` (integer): Sequence identifier (always 0 for single evaluation)
  - `score` (float): Final evaluation score
  - `feasible` (boolean): Whether the sequence is feasible (sufficient cash, valid trades)
  - `allocation_fit` (float): Portfolio allocation alignment score
  - `transaction_costs` (float): Total transaction costs
  - `final_portfolio_value` (float): Portfolio value after sequence execution

**Error Responses:**
- `400 Bad Request`: No sequence provided, invalid request body
- `500 Internal Server Error`: Evaluation failed, no result returned
