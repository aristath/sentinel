# GET /api/adaptation/current

Get current market regime.

**Description:**
Returns the current detected market regime (bull, bear, or sideways) and regime score.

**Request:**
- Method: `GET`
- Path: `/api/adaptation/current`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "regime": "bull",
    "score": 0.75,
    "confidence": 0.85,
    "detected_at": "2024-01-15T10:30:00Z"
  }
  ```
  - `regime` (string): Market regime ("bull", "bear", "sideways")
  - `score` (float): Regime score (-1.0 to +1.0)
  - `confidence` (float): Confidence level (0.0 to 1.0)
  - `detected_at` (string): When regime was detected

**Error Responses:**
- `500 Internal Server Error`: Service error
