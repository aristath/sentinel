# POST /api/scoring/score/what-if

Calculate score with custom weights (what-if analysis).

**Description:**
Calculates what the security score would be with custom weight configurations. Useful for analyzing how different weight combinations affect scoring. Currently returns a stub response as full implementation requires database integration.

**Request:**
- Method: `POST`
- Path: `/api/scoring/score/what-if`
- Body (JSON):
  ```json
  {
    "isin": "US0378331005",
    "weights": {
      "fundamental": 0.30,
      "dividend": 0.25,
      "technical": 0.20,
      "quality": 0.15,
      "valuation": 0.10
    }
  }
  ```
  - `isin` (string, required): Security ISIN
  - `weights` (object, required): Custom weight mapping (must sum to 1.0)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "isin": "US0378331005",
      "custom_weights": {
        "fundamental": 0.30,
        "dividend": 0.25,
        "technical": 0.20,
        "quality": 0.15,
        "valuation": 0.10
      },
      "original_score": 0.0,
      "custom_score": 0.0,
      "delta": 0.0,
      "note": "What-if scoring requires database integration for security data"
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid request body, ISIN required, weights must sum to 1.0
- `500 Internal Server Error`: Service error

**Note:** Full implementation requires database integration to fetch security data and recalculate scores with custom weights.
