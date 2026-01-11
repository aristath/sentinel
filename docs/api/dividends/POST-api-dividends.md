# POST /api/dividends

Create a new dividend record.

**Description:**
Creates a new dividend record in the database. The dividend is validated before creation.

**Request:**
- Method: `POST`
- Path: `/api/dividends`
- Body (JSON): DividendRecord object:
  ```json
  {
    "symbol": "AAPL.US",
    "amount": 0.25,
    "currency": "USD",
    "payment_date": "2024-01-15",
    "ex_date": "2024-01-10",
    "reinvested": false,
    "reinvested_quantity": 0,
    "pending_bonus": 0.0
  }
  ```
  - `symbol` (string, required): Security symbol
  - `amount` (float, required): Dividend amount per share
  - `currency` (string, required): Currency code
  - `payment_date` (string, required): Payment date (YYYY-MM-DD)
  - `ex_date` (string, optional): Ex-dividend date (YYYY-MM-DD)
  - `reinvested` (boolean, optional): Whether dividend has been reinvested
  - `reinvested_quantity` (integer, optional): Quantity of shares purchased with dividend
  - `pending_bonus` (float, optional): Pending bonus amount

**Response:**
- Status: `201 Created` on success
- Body: Created dividend object with assigned ID

**Error Responses:**
- `400 Bad Request`: Invalid request body, validation error
- `500 Internal Server Error`: Database error
