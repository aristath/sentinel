# POST /api/rebalancing/simulate-rebalance

Simulate rebalancing trades.

**Description:**
Simulates the effect of proposed rebalancing trades without executing them. Useful for testing and validation.

**Request:**
- Method: `POST`
- Path: `/api/rebalancing/simulate-rebalance`
- Body (JSON):
  ```json
  {
    "trades": [
      {
        "symbol": "AAPL.US",
        "side": "BUY",
        "quantity": 10.0,
        "price": 150.25
      }
    ]
  }
  ```
  - `trades` (array, required): Array of proposed trades

**Response:**
- Status: `200 OK`
- Body: Simulation results showing portfolio state after trades

**Error Responses:**
- `400 Bad Request`: Invalid trades array
- `500 Internal Server Error`: Simulation error
