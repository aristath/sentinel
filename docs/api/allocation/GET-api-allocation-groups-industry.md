# GET /api/allocation/groups/industry

Get all industry groups.

**Description:**
Returns all industry groups with their associated industry names.

**Request:**
- Method: `GET`
- Path: `/api/allocation/groups/industry`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "groups": {
      "Tech": ["Technology", "Software", "Semiconductors"],
      "Finance": ["Banking", "Insurance"]
    }
  }
  ```
  - `groups` (object): Map of group names to industry name arrays

**Error Responses:**
- `500 Internal Server Error`: Database error
