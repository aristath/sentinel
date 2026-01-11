# DELETE /api/allocation/groups/country/{group_name}

Delete a country group.

**Description:**
Deletes a country group by name. The group and its associations are removed from the database.

**Request:**
- Method: `DELETE`
- Path: `/api/allocation/groups/country/{group_name}`
- Path Parameters:
  - `group_name` (string, required): Name of the country group to delete

**Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "deleted": "EU"
  }
  ```

**Error Responses:**
- `400 Bad Request`: Missing group name
- `500 Internal Server Error`: Database error
