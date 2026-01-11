# POST /api/sequences/generate/pattern

Generate sequences from a specific pattern.

**Description:**
Generates trade sequences using a specific generation pattern (e.g., "profit_taking", "averaging_down", "rebalancing"). Only the specified pattern is enabled.

**Request:**
- Method: `POST`
- Path: `/api/sequences/generate/pattern`
- Body (JSON):
  ```json
  {
    "pattern_type": "profit_taking",
    "opportunities": {
      "profit_taking": [...],
      "averaging_down": [...]
    },
    "config": {
      "max_trades_per_sequence": 5,
      "min_trade_amount": 100.0
    }
  }
  ```
  - `pattern_type` (string, required): Pattern name (e.g., "profit_taking", "averaging_down", "rebalancing")
  - `opportunities` (object, required): Opportunities by category
  - `config` (object, optional): Planner configuration (defaults used if not provided)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "sequences": [
        {
          "actions": [
            {"type": "SELL", "symbol": "AAPL.US", "quantity": 10}
          ],
          "pattern": "profit_taking"
        }
      ],
      "count": 5,
      "pattern_type": "profit_taking"
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `400 Bad Request`: Missing pattern_type, invalid request body
- `500 Internal Server Error`: Sequence generation failed
