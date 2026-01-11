# GET /api/risk/securities/{isin}/volatility

Get security volatility.

**Description:**
Calculates volatility (standard deviation of returns) for a specific security.

**Request:**
- Method: `GET`
- Path: `/api/risk/securities/{isin}/volatility`
- Path Parameters:
  - `isin` (string, required): Security ISIN

**Response:**
- Status: `200 OK`
- Body: Volatility metrics for the security

**Error Responses:**
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Database error, insufficient data
