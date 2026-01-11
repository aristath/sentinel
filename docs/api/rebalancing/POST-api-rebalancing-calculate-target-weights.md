# POST /api/rebalancing/calculate/target-weights

Calculate rebalancing to specific target weights.

**Description:**
Calculates rebalancing trades to achieve specific target weights for securities. Allows custom allocation targets.

**Request:**
- Method: `POST`
- Path: `/api/rebalancing/calculate/target-weights`
- Body (JSON):
  ```json
  {
    "target_weights": {
      "AAPL.US": 0.10,
      "MSFT.US": 0.08,
      "EUR": 0.05
    },
    "available_cash": 1000.00
  }
  ```
  - `target_weights` (object, required): Target allocation weights by symbol (must not be empty)
  - `available_cash` (float, required): Available cash in EUR (must be > 0)

**Response:**
- Status: `200 OK`
- Body: Rebalancing recommendations based on custom target weights

**Error Responses:**
- `400 Bad Request`: Missing or empty target_weights, invalid available_cash
- `500 Internal Server Error`: Service error
