# GET /api/risk/portfolio/volatility

Get portfolio volatility.

**Description:**
Calculates portfolio volatility (standard deviation of returns) based on historical returns.

**Request:**
- Method: `GET`
- Path: `/api/risk/portfolio/volatility`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Volatility metrics object

**Error Responses:**
- `500 Internal Server Error`: Database error
