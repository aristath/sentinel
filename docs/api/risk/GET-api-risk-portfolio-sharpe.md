# GET /api/risk/portfolio/sharpe

Get portfolio Sharpe ratio.

**Description:**
Calculates the Sharpe ratio for the portfolio, which measures risk-adjusted returns.

**Request:**
- Method: `GET`
- Path: `/api/risk/portfolio/sharpe`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Sharpe ratio value and related metrics

**Error Responses:**
- `500 Internal Server Error`: Database error
