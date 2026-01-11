# GET /api/adaptation/history

Get market regime history.

**Description:**
Returns historical market regime changes over time, showing how the regime has evolved.

**Request:**
- Method: `GET`
- Path: `/api/adaptation/history`
- Query Parameters:
  - `limit` (optional, integer): Number of historical records (default: 100)
  - `start_date` (optional, string): Start date filter (YYYY-MM-DD)

**Response:**
- Status: `200 OK`
- Body: Array of regime history records

**Error Responses:**
- `500 Internal Server Error`: Service error
