# GET /api/historical/returns/monthly/{isin}

Get monthly returns for a security.

**Description:**
Calculates and returns monthly percentage returns based on monthly price changes.

**Request:**
- Method: `GET`
- Path: `/api/historical/returns/monthly/{isin}`
- Path Parameters:
  - `isin` (string, required): Security ISIN
- Query Parameters:
  - `limit` (optional, integer): Maximum number of monthly returns (default: 120)

**Response:**
- Status: `200 OK`
- Body: Similar structure to daily returns but with monthly data

**Error Responses:**
- `500 Internal Server Error`: Database error
