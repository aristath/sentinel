# POST /api/backups/r2/restore

Stage a restore from R2 backup.

**Description:**
Downloads a backup from R2, validates it, stages it for restoration, and restarts the service. The service restart triggers the actual restore process. **Warning:** This operation will restart the service and restore all databases from the backup.

**Request:**
- Method: `POST`
- Path: `/api/backups/r2/restore`
- Body (JSON):
  ```json
  {
    "filename": "sentinel-backup-2024-01-15-103000.tar.gz"
  }
  ```
  - `filename` (string, required): Backup filename to restore

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "status": "success",
    "message": "Restore staged, restarting service...",
    "restart_command": "systemctl restart sentinel"
  }
  ```

**Error Responses:**
- `400 Bad Request`: Invalid filename format, invalid request body
- `200 OK` with error in body: Restore service not configured
- `500 Internal Server Error`: Failed to stage restore, download failed, validation failed

**Side Effects:**
- Downloads backup from R2
- Validates backup file
- Creates restore flag file
- **Restarts the service** (service restart triggers restore)

**Warning:** This operation will restore all databases from the backup, overwriting current data.
