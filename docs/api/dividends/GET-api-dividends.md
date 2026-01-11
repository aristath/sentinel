# GET /api/dividends

Get all dividend records.

**Description:**
Returns a list of dividend records with optional limit. Dividends include payment dates, amounts, symbols, and reinvestment status.

**Request:**
- Method: `GET`
- Path: `/api/dividends`
- Query Parameters:
  - `limit` (optional, integer): Maximum number of dividends to return (default: 100)

**Response:**
- Status: `200 OK`
- Body: Array of dividend objects:
  ```json
  [
    {
      "id": 123,
      "symbol": "AAPL.US",
      "amount": 0.25,
      "currency": "USD",
      "payment_date": "2024-01-15",
      "ex_date": "2024-01-10",
      "reinvested": false,
      "reinvested_quantity": 0,
      "pending_bonus": 0.0,
      "created_at": "2024-01-10T10:00:00Z"
    }
  ]
  ```

**Error Responses:**
- `500 Internal Server Error`: Database error
