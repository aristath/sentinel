# POST /api/trade-validation/validate-trade

Validate a trade without execution.

**Description:**
Performs full trade validation using the 7-layer safety validation system without executing the trade. Returns validation results including errors and warnings.

**Request:**
- Method: `POST`
- Path: `/api/trade-validation/validate-trade`
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
  - `price` (float, optional): Expected price (for validation)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "passed": true,
      "symbol": "AAPL.US",
      "side": "BUY",
      "quantity": 10.0,
      "errors": [],
      "warnings": []
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `passed` (boolean): Whether validation passed
  - `errors` (array): List of validation errors (if any)
  - `warnings` (array): List of validation warnings (if any)

**Error Responses:**
- `400 Bad Request`: Invalid request body
- `503 Service Unavailable`: Safety service not available

**Side Effects:**
- No trade execution - validation only
