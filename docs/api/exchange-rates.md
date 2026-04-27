# Exchange Rates

Base path: `/api/exchange-rates`

All rates are expressed as: 1 unit of foreign currency = N EUR.

---

## `GET /api/exchange-rates`

Returns all stored exchange rates to EUR.

**Response**
```json
{
  "USD": 0.924,
  "GBP": 1.172,
  "CHF": 1.041
}
```

---

## `POST /api/exchange-rates/sync`

Fetches the latest exchange rates from the Tradernet API and updates the database.

**Response** — Same shape as `GET /api/exchange-rates`.

---

## `PUT /api/exchange-rates/{curr}`

Manually override the rate for a specific currency to EUR. Useful for testing or when the automated sync returns bad data.

**Path params**
- `curr` — ISO 4217 currency code (e.g. `USD`, `GBP`)

**Request body**
```json
{ "rate": 0.930 }
```

**Response**
```json
{ "status": "ok" }
```
