# GET /api/allocation/deviations

Get allocation deviation scores.

**Description:**
Returns deviation scores showing how far current allocations are from target allocations. Includes deviation percentages and status (balanced, underweight, overweight).

**Request:**
- Method: `GET`
- Path: `/api/allocation/deviations`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "country": {
      "EU": {
        "deviation": -0.05,
        "need": 0.05,
        "status": "underweight"
      }
    },
    "industry": {
      "Tech": {
        "deviation": 0.03,
        "need": 0.0,
        "status": "overweight"
      }
    }
  }
  ```
  - `deviation` (float): Deviation from target (-0.05 means 5% under target)
  - `need` (float): Amount needed to reach target (0.0 if over target)
  - `status` (string): "balanced", "underweight", or "overweight"

**Error Responses:**
- `500 Internal Server Error`: Service error
