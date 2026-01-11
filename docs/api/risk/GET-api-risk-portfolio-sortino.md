# GET /api/risk/portfolio/sortino

Get portfolio Sortino ratio.

**Description:**
Calculates the Sortino ratio for the portfolio, which measures risk-adjusted returns considering only downside volatility.

**Request:**
- Method: `GET`
- Path: `/api/risk/portfolio/sortino`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Sortino ratio value and related metrics

**Error Responses:**
- `500 Internal Server Error`: Database error
