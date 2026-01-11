# GET /api/portfolio/unrealized-pnl/breakdown

Get unrealized P&L breakdown.

**Description:**
Returns detailed breakdown of unrealized gains and losses by security, showing cost basis, current value, and gain/loss.

**Request:**
- Method: `GET`
- Path: `/api/portfolio/unrealized-pnl/breakdown`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body: Unrealized P&L breakdown by security

**Error Responses:**
- `500 Internal Server Error`: Service error
