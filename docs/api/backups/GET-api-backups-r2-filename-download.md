# GET /api/backups/r2/{filename}/download

Download a backup file.

**Description:**
Downloads a backup file from R2 and streams it to the client. The file is served as a binary download.

**Request:**
- Method: `GET`
- Path: `/api/backups/r2/{filename}/download`
- Path Parameters:
  - `filename` (string, required): Backup filename

**Response:**
- Status: `200 OK`
- Content-Type: `application/gzip` or `application/x-tar`
- Body: Binary backup file (tar.gz)

**Error Responses:**
- `400 Bad Request`: Invalid filename format
- `404 Not Found`: Backup file not found in R2
- `500 Internal Server Error`: Download failed
