# POST /api/v1/simulate/custom-prices

Simulate sequence with custom prices.

**Description:**
Simulates a trade sequence using custom price values instead of current market prices. Useful for scenario analysis, stress testing, and "what-if" analysis with hypothetical price scenarios.

**Request:**
- Method: `POST`
- Path: `/api/v1/simulate/custom-prices`
- Body (JSON):
  ```json
  {
    "sequence": [
      {"type": "BUY", "symbol": "AAPL.US", "quantity": 10}
    ],
    "custom_prices": {
      "AAPL.US": 150.50,
      "MSFT.US": 380.25
    },
    "evaluation_context": {
      "transaction_cost_fixed": 2.0,
      "transaction_cost_percent": 0.002
    }
  }
  ```
  - `sequence` (array, required): Trade sequence to simulate
  - `custom_prices` (object, required): Map of symbol to custom price (must include all symbols in sequence)
  - `evaluation_context` (object, required): Simulation parameters

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "result": {
      "sequence_id": 0,
      "score": 75.5,
      "feasible": true,
      "final_portfolio_value": 50150.0
    },
    "custom_prices": {
      "AAPL.US": 150.50,
      "MSFT.US": 380.25
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z",
      "elapsed_ms": 45,
      "prices_applied": 2
    }
  }
  ```
  - `result` (object): Simulation result (same structure as batch simulation result)
  - `custom_prices` (object): Custom prices that were applied
  - `metadata` (object): Metadata including timestamp, elapsed time, and number of prices applied

**Error Responses:**
- `400 Bad Request`: No sequence provided, no custom prices provided, invalid request body
- `500 Internal Server Error`: Simulation failed, no result returned
