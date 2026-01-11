# PUT /api/allocation/groups/targets/country

Update country group allocation targets.

**Description:**
Sets allocation target percentages for country groups. Targets must be between 0 and 1 (0% to 100%). Only groups that exist can have targets set.

**Request:**
- Method: `PUT`
- Path: `/api/allocation/groups/targets/country`
- Body (JSON):
  ```json
  {
    "targets": {
      "EU": 0.45,
      "ASIA": 0.30,
      "US": 0.25
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
      "EU": 0.45,
      "ASIA": 0.30,
      "US": 0.25
    },
    "count": 3
  }
  ```
  - `weights` (object): Updated target weights (only non-zero targets returned)
  - `count` (integer): Number of groups with non-zero targets

**Error Responses:**
- `400 Bad Request`: No weights provided, invalid weight range (must be 0-1), no country groups defined
- `500 Internal Server Error`: Database error

**Side Effects:**
- Updates allocation targets in database
- Emits ALLOCATION_TARGETS_CHANGED event
