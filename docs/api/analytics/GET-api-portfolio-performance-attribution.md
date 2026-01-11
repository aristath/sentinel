# GET /api/portfolio/performance/attribution

Get performance attribution.

**Description:**
Returns performance attribution analysis showing which securities, sectors, or factors contributed to portfolio returns.

**Request:**
- Method: `GET`
- Path: `/api/portfolio/performance/attribution`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Performance attribution object with contributions breakdown

**Error Responses:**
- `500 Internal Server Error`: Service error
