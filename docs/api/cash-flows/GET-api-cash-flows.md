# GET /api/cash-flows

Get cash flow history with optional filters.

**Description:**
Returns a list of cash flow records including deposits, withdrawals, fees, and other cash movements. Supports filtering by transaction type and date range.

**Request:**
- Method: `GET`
- Path: `/api/cash-flows`
- Query Parameters:
  - `transaction_type` (optional, string): Filter by transaction type (deposit, withdrawal, fee, etc.)
  - `start_date` (optional, string): Start date filter (YYYY-MM-DD format)
  - `end_date` (optional, string): End date filter (YYYY-MM-DD format)
  - `limit` (optional, integer): Maximum number of records to return (1-10000, default: all)

**Response:**
- Status: `200 OK`
- Body: Array of cash flow objects:
  ```json
  [
    {
      "id": 123,
      "transaction_type": "deposit",
      "amount": 1000.00,
      "amount_eur": 1000.00,
      "currency": "EUR",
      "date": "2024-01-15",
      "description": "Monthly deposit",
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
  ```

**Error Responses:**
- `400 Bad Request`: Invalid date format, start_date > end_date, invalid limit range
- `500 Internal Server Error`: Database error

**Note:** Either use date range filtering (start_date + end_date) OR transaction_type filtering OR limit. Date range takes precedence.
