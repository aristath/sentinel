# GET /api/scoring/weights/current

Get current scoring weights.

**Description:**
Returns the current scoring weights including base weights and adaptive adjustments based on market regime.

**Request:**
- Method: `GET`
- Path: `/api/scoring/weights/current`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Weights object:
  ```json
  {
    "base_weights": {
      "quality": 0.45,
      "opportunity": 0.25,
      "fundamental": 0.20,
      "technical": 0.10
    },
    "adaptive_adjustments": {
      "quality": 0.0,
      "opportunity": 0.05
    },
    "current_weights": {
      "quality": 0.45,
      "opportunity": 0.30,
      "fundamental": 0.20,
      "technical": 0.10
    }
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Service error
