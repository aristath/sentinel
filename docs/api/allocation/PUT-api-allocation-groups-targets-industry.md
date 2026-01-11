# PUT /api/allocation/groups/targets/industry

Update industry group allocation targets.

**Description:**
Sets allocation target percentages for industry groups. Targets must be between 0 and 1 (0% to 100%). Only groups that exist can have targets set.

**Request:**
- Method: `PUT`
- Path: `/api/allocation/groups/targets/industry`
- Body (JSON):
  ```json
  {
    "targets": {
      "Tech": 0.40,
      "Finance": 0.25,
      "Healthcare": 0.20
    }
  }
  ```
  - `targets` (object, required): Map of group names to target percentages (0.0 to 1.0)

**Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "weights": {
      "Tech": 0.40,
      "Finance": 0.25,
      "Healthcare": 0.20
    },
    "count": 3
  }
  ```

**Error Responses:**
- `400 Bad Request`: No weights provided, invalid weight range (must be 0-1), no industry groups defined
- `500 Internal Server Error`: Database error

**Side Effects:**
- Updates allocation targets in database
- Emits ALLOCATION_TARGETS_CHANGED event
