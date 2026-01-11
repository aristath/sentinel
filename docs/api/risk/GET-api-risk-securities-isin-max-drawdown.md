# GET /api/risk/securities/{isin}/max-drawdown

Get security maximum drawdown.

**Description:**
Calculates the maximum drawdown for a specific security.

**Request:**
- Method: `GET`
- Path: `/api/risk/securities/{isin}/max-drawdown`
- Path Parameters:
  - `isin` (string, required): Security ISIN

**Response:**
- Status: `200 OK`
- Body: Maximum drawdown value and period

**Error Responses:**
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Database error
