# GET /api/adaptation/adaptive-weights

Get current adaptive scoring weights.

**Description:**
Returns the current adaptive scoring weights that adjust based on market regime. Shows how scoring weights have been adjusted from base weights.

**Request:**
- Method: `GET`
- Path: `/api/adaptation/adaptive-weights`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Adaptive weights object showing base weights, adjustments, and effective weights

**Error Responses:**
- `500 Internal Server Error`: Service error
