# GET /api/sequences/patterns

List available sequence generation patterns.

**Description:**
Returns a list of all available sequence generation patterns with descriptions.

**Request:**
- Method: `GET`
- Path: `/api/sequences/patterns`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "patterns": [
      {
        "name": "profit_taking",
        "description": "Take profits from winning positions"
      },
      {
        "name": "averaging_down",
        "description": "Buy more of losing positions at lower prices"
      },
      {
        "name": "rebalancing",
        "description": "Rebalance portfolio to target allocations"
      }
    ],
    "count": 13
  }
  ```
