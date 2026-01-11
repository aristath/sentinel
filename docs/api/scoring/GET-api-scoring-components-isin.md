# GET /api/scoring/components/{isin}

Get detailed score component breakdown.

**Description:**
Returns detailed breakdown of all score components for a security, showing how each factor contributes to the total score.

**Request:**
- Method: `GET`
- Path: `/api/scoring/components/{isin}`
- Path Parameters:
  - `isin` (string, required): Security ISIN

**Response:**
- Status: `200 OK`
- Body: Detailed component breakdown object with all scoring factors

**Error Responses:**
- `400 Bad Request`: Invalid ISIN
- `404 Not Found`: Security not found
- `500 Internal Server Error`: Service error
