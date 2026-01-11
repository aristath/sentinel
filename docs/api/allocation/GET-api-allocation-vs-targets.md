# GET /api/allocation/vs-targets

Get allocation comparison vs targets.

**Description:**
Returns detailed comparison of current allocations against target allocations, showing deviations, status, and rebalancing needs.

**Request:**
- Method: `GET`
- Path: `/api/allocation/vs-targets`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Comparison object with detailed allocation vs target analysis

**Error Responses:**
- `500 Internal Server Error`: Service error
