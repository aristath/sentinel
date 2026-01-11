# GET /api/events/stream

Get unified events stream (SSE).

**Description:**
Returns a Server-Sent Events (SSE) stream that emits real-time events from the event bus. This is a unified stream for all system events including planning events, trade executions, sync operations, and more.

**Request:**
- Method: `GET`
- Path: `/api/events/stream`
- Parameters: None

**Response:**
- Status: `200 OK`
- Content-Type: `text/event-stream`
- Body: SSE event stream with various event types

**Error Responses:**
- `500 Internal Server Error`: Stream setup failed

**Note:** This is a long-lived connection that streams events until the client disconnects. Events are sent as they occur in the system.
