# GET /api/charts/sparklines

Get sparkline data for dashboard.

**Description:**
Returns aggregated sparkline data for portfolio visualization. Sparklines show portfolio value over time in a compact format.

**Request:**
- Method: `GET`
- Path: `/api/charts/sparklines`
- Query Parameters:
  - `period` (optional, string): Time period - "1Y" or "5Y" (default: "1Y")

**Response:**
- Status: `200 OK`
- Body: Sparkline data object with time series data

**Error Responses:**
- `400 Bad Request`: Invalid period (must be "1Y" or "5Y")
- `500 Internal Server Error`: Service error
