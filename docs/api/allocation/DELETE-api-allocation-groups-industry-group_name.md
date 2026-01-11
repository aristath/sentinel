# DELETE /api/allocation/groups/industry/{group_name}

Delete an industry group.

**Description:**
Deletes an industry group by name. The group and its associations are removed from the database.

**Request:**
- Method: `DELETE`
- Path: `/api/allocation/groups/industry/{group_name}`
- Path Parameters:
  - `group_name` (string, required): Name of the industry group to delete

**Response:**
- Status: `200 OK` on success
- Body:
  ```json
  {
    "deleted": "Tech"
  }
  ```

**Error Responses:**
- `400 Bad Request`: Missing group name
- `500 Internal Server Error`: Database error
