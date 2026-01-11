# POST /api/quantum/amplitude

Calculate quantum amplitude.

**Description:**
Calculates the quantum amplitude from probability and energy values. Used in quantum probability models for portfolio analysis.

**Request:**
- Method: `POST`
- Path: `/api/quantum/amplitude`
- Body (JSON):
  ```json
  {
    "probability": 0.75,
    "energy": 1.5
  }
  ```
  - `probability` (float, required): Probability value (0.0 to 1.0)
  - `energy` (float, required): Energy value

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "probability": 0.75,
      "energy": 1.5,
      "amplitude": {
        "real": 0.866,
        "imaginary": 0.0,
        "magnitude": 0.866,
        "phase": 0.0
      }
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid request body
