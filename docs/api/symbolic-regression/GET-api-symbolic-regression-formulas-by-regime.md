# GET /api/symbolic-regression/formulas/by-regime

Get formulas filtered by regime range.

**Description:**
Returns formulas that are valid for a specific market regime range. Useful for finding formulas applicable to current market conditions.

**Request:**
- Method: `GET`
- Path: `/api/symbolic-regression/formulas/by-regime`
- Query Parameters:
  - `regime_min` (required, float): Minimum regime score (e.g., -1.0)
  - `regime_max` (required, float): Maximum regime score (e.g., 0.5)

**Response:**
- Status: `200 OK`
- Body: Formulas matching the regime range

**Error Responses:**
- `400 Bad Request`: Missing regime_min or regime_max, invalid values
- `500 Internal Server Error`: Database error
