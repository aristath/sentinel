# GET /api/portfolio/transactions

Get transaction history from broker.

**Description:**
Retrieves withdrawal and transaction history from the broker (Tradernet). Includes total withdrawals and individual transaction records.

**Request:**
- Method: `GET`
- Path: `/api/portfolio/transactions`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "total_withdrawals": 10000.00,
    "withdrawals": [
      {
        "date": "2024-01-10",
        "amount": 5000.00,
        "currency": "EUR"
      }
    ],
    "note": "Additional transaction information"
  }
  ```

**Error Responses:**
- `500 Internal Server Error`: Failed to fetch transactions from broker
