# GET /api/risk/securities/{isin}/sortino

Get security Sortino ratio.

**Description:**
Calculates the Sortino ratio for a specific security.

**Request:**
- Method: `GET`
- Path: `/api/risk/securities/{isin}/sortino`
- Path Parameters:
  - `isin` (string, required): Security ISIN

**Response:**
- Status: `200 OK`
- Body: Sortino ratio and related metrics

**Error Responses:**
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Database error
