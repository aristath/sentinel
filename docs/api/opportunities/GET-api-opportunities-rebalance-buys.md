# GET /api/opportunities/rebalance-buys

Get rebalancing buy recommendations.

**Description:**
Returns securities that should be bought to rebalance the portfolio toward target allocations.

**Request:**
- Method: `GET`
- Path: `/api/opportunities/rebalance-buys`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of rebalancing buy opportunities

**Error Responses:**
- `500 Internal Server Error`: Service error
