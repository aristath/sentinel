# GET /api/currency/available-currencies

Get available currencies.

**Description:**
Returns list of currencies supported by the system.

**Request:**
- Method: `GET`
- Path: `/api/currency/available-currencies`
- Parameters: None

**Response:**
- Status: `200 OK`
- Body:
  ```json
  {
    "data": {
      "currencies": [
        {"code": "EUR", "name": "Euro", "symbol": "€"},
        {"code": "USD", "name": "US Dollar", "symbol": "$"},
        {"code": "GBP", "name": "British Pound", "symbol": "£"},
        {"code": "HKD", "name": "Hong Kong Dollar", "symbol": "HK$"}
      ],
      "count": 4
    },
    "metadata": {
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }
  ```
