# GET /api/snapshots/historical-summary

Get historical summary snapshot.

**Description:**
Returns a summary of recent trading activity and dividends over the last 30 days. Includes trade counts, total buy/sell values, and dividend summaries.

**Request:**
- Method: `GET`
- Path: `/api/snapshots/historical-summary`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "recent_trades": {
        "trades": [
          {
            "id": 456,
            "symbol": "AAPL.US",
            "side": "BUY",
            "quantity": 10.0,
            "price": 150.00,
            "executed_at": "2024-01-10T14:30:00Z"
          }
        ],
        "count": 5,
        "total_buys": 15000.00,
        "total_sells": 5000.00
      },
      "recent_dividends": {
        "dividends": [
          {
            "id": 789,
            "symbol": "AAPL.US",
            "amount_eur": 25.00,
            "payment_date": "2024-01-05"
          }
        ],
        "count": 3,
        "total_amount_eur": 75.00
      },
      "period": "last_30_days"
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Service error
