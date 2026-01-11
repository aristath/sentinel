# DELETE /api/backups/r2/restore/staged

Cancel a staged restore.

**Description:**
Cancels a restore that has been staged but not yet executed. Removes the restore flag file to prevent restoration on next service start.

**Request:**
- Method: `DELETE`
- Path: `/api/backups/r2/restore/staged`
- Body: None

**Response:**
- Status: `200 OK`
- Body: Success confirmation

**Error Responses:**
- `500 Internal Server Error`: Failed to cancel restore
