# GET /api/historical/returns/correlation-matrix

Get correlation matrix for portfolio securities.

**Description:**
Calculates and returns a correlation matrix showing how returns of different securities in the portfolio move together.

**Request:**
- Method: `GET`
- Path: `/api/historical/returns/correlation-matrix`
- Query Parameters:
  - `period` (optional, string): Time period for correlation calculation (e.g., "1Y", "5Y")
  - `limit` (optional, integer): Number of data points to use

**Response:**
- Status: `200 OK`
- Body: Correlation matrix object with ISIN pairs and correlation coefficients

**Error Responses:**
- `500 Internal Server Error`: Database error, insufficient data
