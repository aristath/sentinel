# Securities

Base path: `/api/securities`

Manages the security universe — which instruments Sentinel tracks, trades, and plans around.

---

## `GET /api/securities`

Returns all securities in the universe (including inactive ones).

**Response**
```json
[
  {
    "symbol": "AAPL.US",
    "name": "Apple Inc.",
    "currency": "USD",
    "geography": "US",
    "industry": "Technology",
    "min_lot": 1,
    "active": 1,
    "allow_buy": 1,
    "allow_sell": 1,
    "market_id": "93",
    "user_multiplier": 0.5,
    "user_multiplier_updated_at": "2026-05-17T12:00:00+00:00",
    "user_multiplier_source": "clara",
    "user_multiplier_analysis": "Long-term strategic fit remains neutral.",
    "aliases": "Apple, MacBook, Apple Silicon",
    "quote_data": null,
    "quote_updated_at": null,
    "last_synced": "2026-04-14",
    "data": "{...}"
  }
]
```

| Field | Description |
|---|---|
| `market_id` | Broker market identifier string |
| `data` | Raw JSON metadata blob from broker (security details, market info) |
| `user_multiplier` | Stored Clara strategic preference, 0 avoid, 0.5 neutral, 1 prefer |
| `user_multiplier_updated_at` | Last per-security preference update timestamp |
| `user_multiplier_source` | Preference source, usually `clara`, `manual`, or `migration` |
| `user_multiplier_analysis` | Human-readable rationale for the stored preference |
| `quote_data` | Latest raw quote data from broker (null if not yet synced) |
| `quote_updated_at` | Timestamp of last quote sync |
| `last_synced` | Date of last metadata sync |

---

## `POST /api/securities`

Add a new security to the universe. Fetches metadata and 20 years of historical prices from the broker. If the symbol exists but is inactive, it is re-enabled instead.

**Request body**
```json
{
  "symbol": "AAPL.US",
  "geography": "US",
  "industry": "Technology",
  "allow_buy": 1,
  "allow_sell": 1
}
```

**Response**
```json
{
  "status": "ok",
  "symbol": "AAPL.US",
  "name": "Apple Inc.",
  "prices_count": 5032,
  "re_enabled": false
}
```

**Errors**
- `400` — Symbol missing or already active
- `404` — Symbol not found at broker

---

## `GET /api/securities/aliases`

Returns symbol, name, and aliases for all active securities. Intended for use by a companion news/sentiment app.

**Response**
```json
[
  { "symbol": "AAPL.US", "name": "Apple Inc.", "aliases": "Apple, MacBook, Apple Silicon" }
]
```

Note: `aliases` is a comma-separated string, not an array.

---

## `POST /api/securities/preference`

Updates one security's Clara strategic preference and stores the analysis explaining the decision.

**Request body**
```json
{
  "symbol": "MOH.GR",
  "user_multiplier": 0.02,
  "analysis": "Too exposed to fossil-fuel demand for the long-term portfolio."
}
```

**Response**
Returns the updated single-security payload, including stored and effective faded preference fields.

**Errors**
- `400` — Missing/invalid `symbol`, `user_multiplier`, or `analysis`
- `404` — Security not found

---

## `GET /api/securities/{symbol}`

Returns details for a single security including current position data.

**Response**
```json
{
  "symbol": "AAPL.US",
  "name": "Apple Inc.",
  "currency": "USD",
  "geography": "US",
  "industry": "Technology",
  "aliases": "Apple, MacBook, Apple Silicon",
  "user_multiplier": 0.5,
  "effective_user_multiplier": 0.5,
  "user_multiplier_age_weeks": 0.0,
  "user_multiplier_updated_at": "2026-05-17T12:00:00+00:00",
  "user_multiplier_source": "clara",
  "user_multiplier_analysis": "Long-term strategic fit remains neutral.",
  "quantity": 5.0,
  "current_price": 270.94
}
```

**Errors**
- `404` — Security not found

---

## `PUT /api/securities/{symbol}`

Update security metadata and execution controls. Only the following fields are accepted; all others are silently ignored.

| Field | Type | Description |
|---|---|---|
| `geography` | string | Geography category |
| `industry` | string | Industry category |
| `aliases` | string | Comma-separated search aliases for companion apps |
| `allow_buy` | int (0/1) | Whether buys are permitted |
| `allow_sell` | int (0/1) | Whether sells are permitted |
| `user_multiplier` | float | Manual strategic preference override. Clara integrations should prefer `POST /api/securities/preference`. |
| `user_multiplier_analysis` | string | Optional rationale when setting `user_multiplier` manually |
| `active` | int (0/1) | Active flag |

**Response**
```json
{
  "symbol": "AAPL.US",
  "user_multiplier": 0.6,
  "effective_user_multiplier": 0.6,
  "user_multiplier_source": "manual",
  "user_multiplier_analysis": "Manual preference override from Sentinel UI."
}
```

**Errors**
- `404` — Security not found

---

## `DELETE /api/securities/{symbol}`

Soft-delete a security: marks it inactive, disables trading, deletes its current position record, and preserves all historical prices and trade history.

**Query params**
- `sell_position` (bool, default `true`) — If `true` and there is an open position, a market sell order is placed before deactivating.

**Response**
```json
{ "status": "ok", "sold_quantity": 10 }
```

**Errors**
- `404` — Security not found
- `400` — Sell order failed (only when `sell_position=true`)

---

## `GET /api/securities/{symbol}/prices`

Returns validated historical price data for a security (spikes and crashes interpolated).

**Query params**
- `days` (int, default `365`) — Number of calendar days to return

**Response** (newest first)
```json
[
  {
    "symbol": "AAPL.US",
    "date": "2026-04-25",
    "open": 184.0,
    "high": 186.5,
    "low": 183.2,
    "close": 185.5,
    "volume": 52000000
  }
]
```

Each record includes `symbol` (same as the path param).

---

## `POST /api/securities/{symbol}/sync-prices`

Triggers a price sync for a single security from the broker.

**Query params**
- `days` (int, default `365`) — Number of days to fetch

**Response**
```json
{ "synced": 365 }
```
