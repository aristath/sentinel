# GET /api/allocation/current

Get current allocation percentages.

**Description:**
Returns current portfolio allocation percentages by country and industry, calculated from actual positions.

**Request:**
- Method: `GET`
- Path: `/api/allocation/current`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Current allocation object with country and industry percentages

**Error Responses:**
- `500 Internal Server Error`: Service error
