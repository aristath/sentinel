# PUT /api/allocation/groups/country

Create or update a country group.

**Description:**
Creates a new country group or updates an existing one. Country groups define which countries belong to a named group (e.g., "EU", "ASIA"). Empty strings and duplicates in the country list are automatically filtered out.

**Request:**
- Method: `PUT`
- Path: `/api/allocation/groups/country`
- Body (JSON):
  ```json
  {
    "group_name": "EU",
    "country_names": ["DE", "FR", "NL", "BE"]
  }
  ```
  - `group_name` (string, required): Name of the group
  - `country_names` (array of strings, required): List of country codes

**Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "group_name": "EU",
    "country_names": ["DE", "FR", "NL", "BE"]
  }
  ```

**Error Responses:**
- `400 Bad Request`: Missing group name
- `500 Internal Server Error`: Database error
