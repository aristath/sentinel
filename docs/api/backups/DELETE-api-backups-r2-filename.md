# DELETE /api/backups/r2/{filename}

Delete a backup from R2.

**Description:**
Deletes a specific backup file from Cloudflare R2. The filename must match the expected backup format (sentinel-backup-YYYY-MM-DD-HHMMSS.tar.gz).

**Request:**
- Method: `DELETE`
- Path: `/api/backups/r2/{filename}`
- Path Parameters:
  - `filename` (string, required): Backup filename (must match format: sentinel-backup-YYYY-MM-DD-HHMMSS.tar.gz)

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "status": "success",
    "message": "Backup deleted"
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid filename format, contains path separators
- `200 OK` with error in body: R2 backup service not configured
- `500 Internal Server Error`: Failed to delete backup from R2
