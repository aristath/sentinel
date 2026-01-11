# GET /api/historical/prices/monthly/{isin}

Get monthly price history for a security.

**Description:**
Returns monthly aggregated price data for a security. Useful for longer-term analysis.

**Request:**
- Method: `GET`
- Path: `/api/historical/prices/monthly/{isin}`
- Path Parameters:
  - `isin` (string, required): Security ISIN
- Query Parameters:
  - `limit` (optional, integer): Maximum number of monthly prices to return (default: 120, which is ~10 years)

**Response:**
- Status: `200 OK`
- Body: Similar structure to daily prices, but with monthly data

**Error Responses:**
- `500 Internal Server Error`: Database error
