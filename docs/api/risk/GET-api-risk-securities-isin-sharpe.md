# GET /api/risk/securities/{isin}/sharpe

Get security Sharpe ratio.

**Description:**
Calculates the Sharpe ratio for a specific security.

**Request:**
- Method: `GET`
- Path: `/api/risk/securities/{isin}/sharpe`
- Path Parameters:
  - `isin` (string, required): Security ISIN

**Response:**
- Status: `200 OK`
- Body: Sharpe ratio and related metrics

**Error Responses:**
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Database error
