# POST /api/trade-validation/check-eligibility

Check security eligibility for trading.

**Description:**
Checks if a security is eligible for trading based on security settings (allow_buy, allow_sell, active status, etc.). Uses safety service validation to determine eligibility.

**Request:**
- Method: `POST`
- Path: `/api/trade-validation/check-eligibility`
- Body (JSON):
  ```json
  {
    "symbol": "AAPL.US"
  }
  ```
  - `symbol` (string, required): Security symbol

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "symbol": "AAPL.US",
      "eligible": true,
      "reasons": [],
      "can_buy": true,
      "can_sell": true
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `eligible` (boolean): Whether security is eligible
  - `reasons` (array): List of reasons if not eligible
  - `can_buy` (boolean): Whether buying is allowed
  - `can_sell` (boolean): Whether selling is allowed

**Error Responses:**
- `400 Bad Request`: Invalid request body
- `503 Service Unavailable`: Safety service not available
