# PUT /api/allocation/groups/industry

Create or update an industry group.

**Description:**
Creates a new industry group or updates an existing one. Industry groups define which industries belong to a named group.

**Request:**
- Method: `PUT`
- Path: `/api/allocation/groups/industry`
- Body (JSON):
  ```json
  {
    "group_name": "Tech",
    "industry_names": ["Technology", "Software", "Semiconductors"]
  }
  ```
  - `group_name` (string, required): Name of the group
  - `industry_names` (array of strings, required): List of industry names

**Response:**
- Status: `200 OK` on success
- Body: Updated group object

**Error Responses:**
- `400 Bad Request`: Missing group name
- `500 Internal Server Error`: Database error
