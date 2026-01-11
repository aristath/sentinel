# GET /api/symbolic-regression/formulas/{id}/metrics

Get formula validation metrics.

**Description:**
Returns detailed validation metrics for a specific formula including fitness, R-squared, and other performance indicators.

**Request:**
- Method: `GET`
- Path: `/api/symbolic-regression/formulas/{id}/metrics`
- Path Parameters:
  - `id` (integer, required): Formula ID

**Response:**
- Status: `200 OK`
- Body: Validation metrics object with detailed performance data

**Error Responses:**
- `400 Bad Request`: Invalid formula ID
- `404 Not Found`: Formula not found
- `500 Internal Server Error`: Database error
