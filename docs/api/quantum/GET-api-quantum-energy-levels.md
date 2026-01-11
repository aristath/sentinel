# GET /api/quantum/energy-levels

Get discrete energy levels.

**Description:**
Returns the discrete energy levels used in quantum probability calculations.

**Request:**
- Method: `GET`
- Path: `/api/quantum/energy-levels`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Array of energy level objects with values and descriptions

**Error Responses:**
- `500 Internal Server Error`: Service error
