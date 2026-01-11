# GET /api/adaptation/performance-history

Get performance history.

**Description:**
Returns historical performance data showing how the adaptation system has performed over time.

**Request:**
- Method: `GET`
- Path: `/api/adaptation/performance-history`
- Query Parameters:
  - `limit` (optional, integer): Number of historical records

**Response:**
- Status: `200 OK`
- Body: Performance history array

**Error Responses:**
- `500 Internal Server Error`: Service error
