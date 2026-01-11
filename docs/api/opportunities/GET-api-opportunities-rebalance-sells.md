# GET /api/opportunities/rebalance-sells

Get rebalancing sell recommendations.

**Description:**
Returns securities that should be sold to rebalance the portfolio toward target allocations.

**Request:**
- Method: `GET`
- Path: `/api/opportunities/rebalance-sells`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of rebalancing sell opportunities

**Error Responses:**
- `500 Internal Server Error`: Service error
