# GET /api/allocation/groups/country

Get all country groups.

**Description:**
Returns all country groups with their associated country codes.

**Request:**
- Method: `GET`
- Path: `/api/allocation/groups/country`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "groups": {
      "EU": ["DE", "FR", "NL", "BE"],
      "ASIA": ["JP", "CN", "HK"]
    }
  }
  ```
  - `groups` (object): Map of group names to country code arrays

**Error Responses:**
- `500 Internal Server Error`: Database error
