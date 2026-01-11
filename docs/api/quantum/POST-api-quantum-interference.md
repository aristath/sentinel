# POST /api/quantum/interference

Calculate quantum interference.

**Description:**
Calculates quantum interference between two probability amplitudes. Used for modeling correlated events in portfolio analysis.

**Request:**
- Method: `POST`
- Path: `/api/quantum/interference`
- Body (JSON):
  ```json
  {
    "p1": 0.5,
    "p2": 0.6,
    "energy1": 1.0,
    "energy2": 1.2
  }
  ```
  - `p1` (float, required): First probability (0.0 to 1.0)
  - `p2` (float, required): Second probability (0.0 to 1.0)
  - `energy1` (float, required): First energy value
  - `energy2` (float, required): Second energy value

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "p1": 0.5,
      "p2": 0.6,
      "energy1": 1.0,
      "energy2": 1.2,
      "energy_diff": 0.2,
      "interference": 0.55
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid request body, probabilities out of range (must be 0-1)
