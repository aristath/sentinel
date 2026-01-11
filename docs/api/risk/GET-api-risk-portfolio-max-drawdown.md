# GET /api/risk/portfolio/max-drawdown

Get portfolio maximum drawdown.

**Description:**
Calculates the maximum drawdown for the portfolio, which represents the largest peak-to-trough decline.

**Request:**
- Method: `GET`
- Path: `/api/risk/portfolio/max-drawdown`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Maximum drawdown value and period information

**Error Responses:**
- `500 Internal Server Error`: Database error
