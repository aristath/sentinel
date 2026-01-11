# GET /api/portfolio/diversification

Get diversification scores.

**Description:**
Returns diversification scores measuring how well-diversified the portfolio is across securities, sectors, and geographies.

**Request:**
- Method: `GET`
- Path: `/api/portfolio/diversification`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Diversification scores object

**Error Responses:**
- `500 Internal Server Error`: Service error
