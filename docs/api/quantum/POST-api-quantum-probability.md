# POST /api/quantum/probability

Calculate probability from amplitude.

**Description:**
Calculates probability using the Born rule from a quantum amplitude (real and imaginary components).

**Request:**
- Method: `POST`
- Path: `/api/quantum/probability`
- Body (JSON):
  ```json
  {
    "amplitude_real": 0.866,
    "amplitude_imag": 0.0
  }
  ```
  - `amplitude_real` (float, required): Real component of amplitude
  - `amplitude_imag` (float, required): Imaginary component of amplitude

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "amplitude": {
        "real": 0.866,
        "imaginary": 0.0
      },
      "probability": 0.75
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid request body
