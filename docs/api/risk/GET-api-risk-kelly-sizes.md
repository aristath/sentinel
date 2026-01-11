# GET /api/risk/kelly-sizes

Get Kelly-optimal position sizes for all securities.

**Description:**
Returns Kelly-optimal position sizes for all securities in the portfolio. Kelly sizing calculates optimal position sizes based on expected returns and confidence.

**Request:**
- Method: `GET`
- Path: `/api/risk/kelly-sizes`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Object mapping ISINs to Kelly-optimal sizes and related metrics

**Error Responses:**
- `500 Internal Server Error`: Database error, calculation error
