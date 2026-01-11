# POST /api/settings/reschedule-jobs

Reschedule all background jobs.

**Description:**
Triggers rescheduling of all background jobs. Currently returns acknowledgment as full implementation requires scheduler integration.

**Request:**
- Method: `POST`
- Path: `/api/settings/reschedule-jobs`
- Body: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "status": "ok",
    "message": "Job rescheduling acknowledged (simplified implementation)"
  }
  ```

**Note:** Currently returns acknowledgment only. Full implementation requires scheduler integration.
