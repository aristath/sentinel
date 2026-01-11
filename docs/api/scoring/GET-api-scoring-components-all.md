# GET /api/scoring/components/all

Get score components for all securities.

**Description:**
Returns score component breakdowns for all securities in the universe. Useful for bulk analysis.

**Request:**
- Method: `GET`
- Path: `/api/scoring/components/all`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of score component objects (one per security)

**Error Responses:**
- `500 Internal Server Error`: Service error
