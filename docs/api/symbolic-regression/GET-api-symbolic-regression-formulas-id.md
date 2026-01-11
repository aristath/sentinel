# GET /api/symbolic-regression/formulas/{id}

Get formula by ID.

**Description:**
Returns detailed information about a specific formula including its expression and validation metrics.

**Request:**
- Method: `GET`
- Path: `/api/symbolic-regression/formulas/{id}`
- Path Parameters:
  - `id` (integer, required): Formula ID

**Response:**
- Status: `200 OK`
- Body: Formula details object

**Error Responses:**
- `400 Bad Request`: Invalid formula ID
- `404 Not Found`: Formula not found
- `500 Internal Server Error`: Database error
