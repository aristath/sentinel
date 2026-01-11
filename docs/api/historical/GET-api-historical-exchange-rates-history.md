# GET /api/historical/exchange-rates/history

Get exchange rate history.

**Description:**
Returns historical exchange rates for currency pairs.

**Request:**
- Method: `GET`
- Path: `/api/historical/exchange-rates/history`
- Query Parameters:
  - `from` (optional, string): Source currency (e.g., "USD")
  - `to` (optional, string): Target currency (e.g., "EUR")
  - `limit` (optional, integer): Number of historical rates to return

**Response:**
- Status: `200 OK`
- Body: Array of historical exchange rate records

**Error Responses:**
- `500 Internal Server Error`: Database error
