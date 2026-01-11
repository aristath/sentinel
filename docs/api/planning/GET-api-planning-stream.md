# GET /api/planning/stream

Server-Sent Events stream for planning events.

**Description:**
Returns a Server-Sent Events (SSE) stream that emits real-time events during planning job execution. Events include progress updates, completion status, and errors.

**Request:**
- Method: `GET`
- Path: `/api/planning/stream`
- Parameters: None
- Headers: Standard SSE headers are set by the server

**Response:**
- Status: `200 OK`
- Content-Type: `text/event-stream`
- Body: SSE event stream:
  ```
  event: planning.progress
  data: {"step": "building_context", "progress": 25}

  event: planning.complete
  data: {"status": "success", "recommendations_count": 5}
  ```

**Error Responses:**
- Connection errors handled via SSE error events

**Note:** This is a streaming endpoint that keeps the connection open. Clients should handle reconnection logic.
