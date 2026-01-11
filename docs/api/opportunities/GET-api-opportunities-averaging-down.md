# GET /api/opportunities/averaging-down

Get averaging-down opportunities.

**Description:**
Returns securities where averaging down (buying more at lower prices) may be appropriate.

**Request:**
- Method: `GET`
- Path: `/api/opportunities/averaging-down`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of averaging-down opportunity objects

**Error Responses:**
- `500 Internal Server Error`: Service error
