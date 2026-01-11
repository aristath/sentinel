# POST /api/system/sync/daily-pipeline

Run daily sync pipeline.

**Description:**
Triggers the complete daily synchronization pipeline including prices, portfolio, cash flows, and other daily operations.

**Request:**
- Method: `POST`
- Path: `/api/system/sync/daily-pipeline`
- Body: None

**Response:**
- Status: `200 OK` on success
- Body: Pipeline execution result

**Error Responses:**
- `500 Internal Server Error`: Pipeline execution failed

**Side Effects:**
- Executes complete daily sync sequence
- Updates all synchronized data
- May trigger multiple sync operations
