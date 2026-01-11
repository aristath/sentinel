# POST /api/symbolic-regression/discover

Start formula discovery.

**Description:**
Triggers formula discovery using symbolic regression. This is a computationally intensive operation that discovers mathematical formulas for expected returns or scoring.

**Request:**
- Method: `POST`
- Path: `/api/symbolic-regression/discover`
- Body (JSON):
  ```json
  {
    "formula_type": "expected_return",
    "security_type": "stock",
    "start_date": "2020-01-01T00:00:00Z",
    "end_date": "2024-01-01T00:00:00Z",
    "forward_months": 12
  }
  ```
  - `formula_type` (string, required): "expected_return" or "scoring"
  - `security_type` (string, required): "stock" or "etf"
  - `start_date` (string, required): Start date for training data (ISO 8601)
  - `end_date` (string, required): End date for training data (ISO 8601)
  - `forward_months` (integer, required): Forward prediction period (6 or 12 months)

**Response:**
- Status: `200 OK`
- Body: Discovery job status and ID

**Error Responses:**
- `400 Bad Request`: Invalid request body, invalid dates
- `500 Internal Server Error`: Discovery failed

**Side Effects:**
- Starts computationally intensive formula discovery process
- May take significant time to complete
- Saves discovered formulas to database
