# POST /api/dividends/{id}/mark-reinvested

Mark a dividend as reinvested.

**Description:**
Marks a dividend as reinvested and records the quantity of shares purchased. Used by the dividend reinvestment job after successful trade execution.

**Request:**
- Method: `POST`
- Path: `/api/dividends/{id}/mark-reinvested`
- Path Parameters:
  - `id` (integer, required): Dividend ID
- Body (JSON):
  ```json
  {
    "quantity": 10
  }
  ```
  - `quantity` (integer, required): Number of shares purchased (must be > 0)

**Response:**
- Status: `204 No Content` on success

**Error Responses:**
- `400 Bad Request`: Invalid dividend ID, invalid quantity
- `500 Internal Server Error`: Database error

**Note:** This endpoint is used internally by the dividend reinvestment job.
