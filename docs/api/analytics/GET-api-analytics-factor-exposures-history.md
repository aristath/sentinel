# GET /api/analytics/factor-exposures/history

Get factor exposure history.

**Description:**
Returns historical factor exposure data showing how factor exposures have changed over time.

**Request:**
- Method: `GET`
- Path: `/api/analytics/factor-exposures/history`
- Query Parameters:
  - `limit` (optional, integer): Number of historical records (default: 100)

**Response:**
- Status: `200 OK`
- Body: Array of historical factor exposure records with timestamps

**Error Responses:**
- `500 Internal Server Error`: Database error
