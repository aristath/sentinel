# GET /api/allocation/rebalance-needs

Get rebalancing needs.

**Description:**
Returns analysis of rebalancing needs showing which groups need adjustment to meet target allocations.

**Request:**
- Method: `GET`
- Path: `/api/allocation/rebalance-needs`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Rebalancing needs analysis object

**Error Responses:**
- `500 Internal Server Error`: Service error
