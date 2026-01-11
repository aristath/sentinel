# POST /api/rebalancing/calculate

Calculate rebalancing trades.

**Description:**
Calculates recommended rebalancing trades to move the portfolio toward target allocations. Uses available cash to make purchases.

**Request:**
- Method: `POST`
- Path: `/api/rebalancing/calculate`
- Body (JSON):
  ```json
  {
    "available_cash": 1000.00
  }
  ```
  - `available_cash` (float, required): Available cash in EUR (must be > 0)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "recommendations": [
        {
          "symbol": "AAPL.US",
          "action": "BUY",
          "quantity": 6.0,
          "reason": "Underweight allocation"
        }
      ],
      "count": 5,
      "available_cash": 1000.00
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z",
      "note": "Dry-run calculation - no trades executed"
    }
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid available_cash (must be > 0)
- `500 Internal Server Error`: Service error, insufficient portfolio data

**Note:** This is a dry-run calculation. No trades are executed.
