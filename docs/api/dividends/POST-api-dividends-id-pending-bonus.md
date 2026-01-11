# POST /api/dividends/{id}/pending-bonus

Set pending bonus for a dividend.

**Description:**
Sets the pending bonus amount for a dividend. Used by the dividend reinvestment job to accumulate small dividends for future reinvestment.

**Request:**
- Method: `POST`
- Path: `/api/dividends/{id}/pending-bonus`
- Path Parameters:
  - `id` (integer, required): Dividend ID
- Body (JSON):
  ```json
  {
    "amount": 5.50
  }
  ```
  - `amount` (float, required): Pending bonus amount (must be >= 0)

**Response:**
- Status: `204 No Content` on success

**Error Responses:**
- `400 Bad Request`: Invalid dividend ID, negative amount
- `500 Internal Server Error`: Database error

**Note:** This endpoint is used internally by the dividend reinvestment job.
