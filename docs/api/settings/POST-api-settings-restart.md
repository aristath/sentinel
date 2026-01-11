# POST /api/settings/restart

Restart the system.

**Description:**
Initiates a system reboot using `sudo reboot`. This is a destructive operation that will reboot the entire system.

**Request:**
- Method: `POST`
- Path: `/api/settings/restart`
- Body: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "status": "rebooting"
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Failed to initiate reboot command

**Side Effects:**
- Executes `sudo reboot`
- System will reboot (all connections will be lost)
- System will be unavailable until reboot completes

**Warning:** This is a destructive operation that will reboot the entire system. Use with extreme caution.
