# POST /api/trade-validation/calculate-limit-price

Calculate limit price for a trade.

**Description:**
Calculates an appropriate limit price for a trade order based on current market price and slippage buffer (default: 0.5% for buys, -0.5% for sells).

**Request:**
- Method: `POST`
- Path: `/api/trade-validation/calculate-limit-price`
- Body (JSON):
  ```json
  {
    "symbol": "AAPL.US",
    "side": "BUY",
    "current_price": 150.25,
    "slippage_pct": 0.5
  }
  ```
  - `symbol` (string, required): Security symbol
  - `side` (string, required): "BUY" or "SELL"
  - `current_price` (float, required): Current market price
  - `slippage_pct` (float, optional): Slippage percentage (default: 0.5% for buys, -0.5% for sells)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "symbol": "AAPL.US",
      "side": "BUY",
      "current_price": 150.25,
      "slippage_pct": 0.5,
      "limit_price": 151.00,
      "note": "Limit price calculated with slippage buffer"
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `limit_price` (float): Calculated limit price
  - `slippage_pct` (float): Applied slippage percentage

**Error Responses:**
- `400 Bad Request`: Invalid request body
- `500 Internal Server Error`: Calculation error
