# GET /api/opportunities/all

Get all opportunities.

**Description:**
Returns all identified opportunities including buy opportunities, profit-taking opportunities, and rebalancing needs.

**Request:**
- Method: `GET`
- Path: `/api/opportunities/all`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of opportunity objects with details, scores, and recommendations

**Error Responses:**
- `500 Internal Server Error`: Service error
