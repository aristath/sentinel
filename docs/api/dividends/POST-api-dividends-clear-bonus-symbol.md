# POST /api/dividends/clear-bonus/{symbol}

Clear pending bonus for a symbol.

**Description:**
Clears the pending bonus amount for a specific security symbol. Used to reset accumulated bonus amounts when dividends have been processed.

**Request:**
- Method: `POST`
- Path: `/api/dividends/clear-bonus/{symbol}`
- Path Parameters:
  - `symbol` (string, required): Security symbol

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "symbol": "AAPL.US",
    "rows_affected": 1
  }
  ```
  - `rows_affected` (integer): Number of dividend records updated

**Error Responses:**
- `500 Internal Server Error`: Database error, failed to clear bonus

**Side Effects:**
- Updates dividend records to clear pending bonus for the symbol
