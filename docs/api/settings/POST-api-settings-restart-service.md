# POST /api/settings/restart-service

Restart the Sentinel service.

**Description:**
Restarts the Sentinel systemd service using `sudo systemctl restart sentinel`. This is a system-level operation that requires sudo privileges.

**Request:**
- Method: `POST`
- Path: `/api/settings/restart-service`
- Body: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "status": "ok",
    "message": "Service restart initiated"
  }
  ```
  - `status` (string): "ok" on success, "error" on failure
  - `message` (string): Status message or error output

**Error Responses:**
- Response may contain `status: "error"` if restart command fails

**Side Effects:**
- Executes `sudo systemctl restart sentinel`
- Service will restart (connection may be lost)

**Warning:** This endpoint requires sudo privileges and will restart the service, potentially interrupting active connections.
