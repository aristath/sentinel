# GET /api/charts/securities/{isin}

Get historical price chart data for a security.

**Description:**
Returns historical price data for a security for charting purposes. Data includes price points over the specified time range.

**Request:**
- Method: `GET`
- Path: `/api/charts/securities/{isin}`
- Path Parameters:
  - `isin` (string, required): Security ISIN (12 characters, validated)
- Query Parameters:
  - `range` (optional, string): Date range for chart data (default: "1Y")

**Response:**
- Status: `200 OK`
- Body: Chart data object with price time series

**Error Responses:**
- `400 Bad Request`: Invalid ISIN format, missing ISIN
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Service error
