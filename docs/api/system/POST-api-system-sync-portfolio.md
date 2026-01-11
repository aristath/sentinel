# POST /api/system/sync/portfolio

Sync portfolio from broker.

**Description:**
Triggers synchronization of portfolio positions from the broker (Tradernet). Fetches current positions and updates the local portfolio database.

**Request:**
- Method: `POST`
- Path: `/api/system/sync/portfolio`
- Body: None

**Response:**
- Status: `200 OK` on success
- Body: Sync result with count of positions updated

**Error Responses:**
- `500 Internal Server Error`: Broker API error, sync failed

**Side Effects:**
- Fetches positions from broker
- Updates portfolio database
- Updates position quantities and values
- Emits PORTFOLIO_SYNCED event
