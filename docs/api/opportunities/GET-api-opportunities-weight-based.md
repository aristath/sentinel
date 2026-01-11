# GET /api/opportunities/weight-based

Get weight-based opportunities.

**Description:**
Returns opportunities based on position weights relative to target allocations and portfolio constraints.

**Request:**
- Method: `GET`
- Path: `/api/opportunities/weight-based`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of weight-based opportunity objects

**Error Responses:**
- `500 Internal Server Error`: Service error
