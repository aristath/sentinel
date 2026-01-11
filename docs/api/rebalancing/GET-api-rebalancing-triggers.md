# GET /api/rebalancing/triggers

Get rebalancing triggers.

**Description:**
Checks whether rebalancing should be triggered based on current portfolio state and deviation thresholds.

**Request:**
- Method: `GET`
- Path: `/api/rebalancing/triggers`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "should_rebalance": false,
      "reason": "Allocations within thresholds"
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
  - `should_rebalance` (boolean): Whether rebalancing is recommended
  - `reason` (string): Explanation of the trigger status

**Error Responses:**
- `500 Internal Server Error`: Service error
