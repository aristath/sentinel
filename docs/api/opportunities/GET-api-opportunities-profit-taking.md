# GET /api/opportunities/profit-taking

Get profit-taking opportunities.

**Description:**
Returns securities that are candidates for profit-taking based on gains, valuations, and portfolio targets.

**Request:**
- Method: `GET`
- Path: `/api/opportunities/profit-taking`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of profit-taking opportunity objects

**Error Responses:**
- `500 Internal Server Error`: Service error
