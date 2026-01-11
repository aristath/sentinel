# GET /api/historical/exchange-rates/{from}/{to}

Get exchange rate between two currencies.

**Description:**
Returns the current exchange rate between two specific currencies.

**Request:**
- Method: `GET`
- Path: `/api/historical/exchange-rates/{from}/{to}`
- Path Parameters:
  - `from` (string, required): Source currency code (e.g., "USD")
  - `to` (string, required): Target currency code (e.g., "EUR")

**Response:**
- Status: `200 OK`
- Body: Exchange rate object with rate and timestamp

**Error Responses:**
- `404 Not Found`: Exchange rate not available
- `500 Internal Server Error`: Database error
