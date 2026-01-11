# GET /api/snapshots/pending-actions

Get pending actions snapshot.

**Description:**
Returns a snapshot of pending actions including pending retry trades from the retry queue. Useful for monitoring trades that are awaiting retry.

**Request:**
- Method: `GET`
- Path: `/api/snapshots/pending-actions`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "pending_retries": [
        {
          "id": 123,
          "symbol": "AAPL.US",
          "side": "BUY",
          "quantity": 10.0,
          "attempts": 2,
          "last_attempt": "2024-01-15T10:00:00Z"
        }
      ],
      "retry_count": 1
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `pending_retries` (array): List of pending retry trades
  - `retry_count` (integer): Total count of pending retries

**Error Responses:**
- `500 Internal Server Error`: Service error
