# POST /api/sequences/filter

Filter sequences by eligibility.

**Description:**
Filters sequences based on planner configuration and eligibility criteria. Removes sequences that don't meet constraints.

**Request:**
- Method: `POST`
- Path: `/api/sequences/filter`
- Body (JSON):
  ```json
  {
    "sequences": [
      {
        "actions": [...],
        "pattern": "profit_taking"
      }
    ],
    "config": {
      "min_trade_amount": 100.0,
      "max_position_size": 0.10
    }
  }
  ```
  - `sequences` (array, required): Sequences to filter
  - `config` (object, optional): Filtering configuration

**Response:**
- Status: `200 OK`
- Body: Filtered sequences that meet eligibility criteria

**Error Responses:**
- `400 Bad Request`: Invalid request body
- `500 Internal Server Error`: Filtering failed
