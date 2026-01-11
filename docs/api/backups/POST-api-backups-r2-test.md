# POST /api/backups/r2/test

Test R2 connection and credentials.

**Description:**
Tests the connection to Cloudflare R2 and validates that credentials are correct. Useful for troubleshooting backup configuration.

**Request:**
- Method: `POST`
- Path: `/api/backups/r2/test`
- Body: None

**Response:**
- Status: `200 OK`
- Body (success):
  ```json
  {
    "status": "success",
    "message": "Connection successful"
  }
  ```
- Body (error):
  ```json
  {
    "status": "error",
    "message": "Connection failed: invalid credentials"
  }
  ```

**Error Responses:**
- `200 OK` with error in body: R2 backup service not configured, connection failed
