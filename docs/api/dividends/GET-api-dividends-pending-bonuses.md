# GET /api/dividends/pending-bonuses

Get all pending bonuses.

**Description:**
Returns all symbols with pending bonus amounts accumulated from small dividends.

**Request:**
- Method: `GET`
- Path: `/api/dividends/pending-bonuses`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of bonus objects:
  ```json
  [
    {
      "symbol": "AAPL.US",
      "pending_bonus": 15.50
    }
  ]
  ```

**Error Responses:**
- `500 Internal Server Error`: Database error
