# POST /api/trade-validation/check-cash-sufficiency

Check cash sufficiency for a trade.

**Description:**
Validates whether there is sufficient cash available to execute a buy trade, taking into account commission costs and currency conversion. For SELL orders, always returns sufficient.

**Request:**
- Method: `POST`
- Path: `/api/trade-validation/check-cash-sufficiency`
- Body (JSON):
  ```json
  {
    "symbol": "AAPL.US",
    "side": "BUY",
    "quantity": 10.0,
    "price": 150.25
  }
  ```
  - `symbol` (string, required): Security symbol
  - `side` (string, required): "BUY" or "SELL"
  - `quantity` (float, required): Number of shares/units
  - `price` (float, required): Trade price

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "symbol": "AAPL.US",
      "side": "BUY",
      "sufficient": true,
      "required_cash": 1507.51,
      "available_cash": 2500.00,
      "deficit": 0.0,
      "commission_included": true
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `sufficient` (boolean): Whether sufficient cash is available
  - `required_cash` (float): Total cash required (trade value + commission)
  - `available_cash` (float): Available cash balance
  - `deficit` (float): Cash deficit if insufficient (0 if sufficient)
  - `commission_included` (boolean): Whether commission is included in required cash

**Error Responses:**
- `400 Bad Request`: Invalid request body
- `500 Internal Server Error`: Check error

**Note:** For SELL orders, cash sufficiency check is not applicable and returns sufficient=true.
