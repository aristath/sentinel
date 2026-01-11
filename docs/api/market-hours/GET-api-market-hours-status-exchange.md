# GET /api/market-hours/status/{exchange}

Get market status for a specific exchange.

**Description:**
Returns the current market status for a specific exchange (e.g., "NYSE", "NASDAQ", "LSE").

**Request:**
- Method: `GET`
- Path: `/api/market-hours/status/{exchange}`
- Path Parameters:
  - `exchange` (string, required): Exchange name/identifier

**Response:**
- Status: `200 OK`
- Body: Exchange-specific market status

**Error Responses:**
- `404 Not Found`: Exchange not found
- `500 Internal Server Error`: Service error
