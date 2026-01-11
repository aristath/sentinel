# POST /api/planning/recommendations

Generate new trade recommendations.

**Description:**
Triggers generation of a new trade plan based on current portfolio state, opportunities, and planner configuration. This is an asynchronous operation - use the status endpoint to check completion.

**Request:**
- Method: `POST`
- Path: `/api/planning/recommendations`
- Body: None (optional configuration may be supported)

**Response:**
- Status: `200 OK` or `202 Accepted`
- Body: Generation job status or recommendations if available immediately

**Error Responses:**
- `500 Internal Server Error`: Planning service error

**Side Effects:**
- Triggers planning job execution
- Generates new recommendations
- Updates recommendation cache
