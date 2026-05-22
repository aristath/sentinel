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
    "industry": "Computers, Phones & Household Electronics",
    "min_lot": 1,
    "active": 1,
    "allow_buy": 1,
    "allow_sell": 1,
    "market_id": "93",
    "user_multiplier": 0.5,
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
| `geography` | ISO‑2 country‑of‑risk from Tradernet (`attributes.CntryOfRisk`). Auto‑filled by metadata sync; blank for ETFs and for tickers Tradernet does not classify. **Not editable.** |
| `industry` | Refinitiv/LSEG TRBC industry name from Tradernet (`sector_code`). Auto‑filled by metadata sync; blank for ETFs. **Not editable.** |
| `market_id` | Broker market identifier string |
| `data` | Raw JSON metadata blob from broker |
| `quote_data` | Latest raw quote payload (null if not yet synced) |
| `quote_updated_at` | Timestamp of last quote sync |
| `last_synced` | Date of last metadata sync |

---

## `POST /api/securities`

Add a new security to the universe. Fetches metadata and 20 years of historical prices from the broker. If the symbol exists but is inactive, it is re-enabled instead.

`geography` and `industry` are populated by the next `sync:metadata` job — they are **not** accepted in the request body. Any client-supplied values are silently dropped.

**Request body**
```json
{ "symbol": "AAPL.US" }
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

---

## `GET /api/securities/aliases`

Returns symbol, name, and aliases for all active securities (for companion news/sentiment apps).

```json
[
  { "symbol": "AAPL.US", "name": "Apple Inc.", "aliases": "Apple, MacBook, Apple Silicon" }
]
```

---

## `GET /api/securities/{symbol}`

Returns details for a single security including current position data.

---

## `PUT /api/securities/{symbol}`

Update execution controls. Only the following fields are accepted; everything else (including legacy `geography` and `industry`) is silently ignored.

| Field | Type | Description |
|---|---|---|
| `aliases` | string | Comma-separated search aliases for companion apps |
| `allow_buy` | int (0/1) | Whether buys are permitted |
| `allow_sell` | int (0/1) | Whether sells are permitted |
| `user_multiplier` | float | Manual strategic preference override. Clara should prefer `POST /api/securities/preference`. |
| `user_multiplier_analysis` | string | Optional rationale when setting `user_multiplier` manually |
| `active` | int (0/1) | Active flag |

---

## `POST /api/securities/preference`

Clara's structural rating sink. Writes `user_multiplier` (0..1) and human-readable rationale.

```json
{ "symbol": "AAPL.US", "user_multiplier": 0.78, "analysis": "Two-three paragraph rationale..." }
```

---

## `DELETE /api/securities/{symbol}`

Soft-delete a security or restrict it to sell-only when a position is open.

---

## `GET /api/securities/{symbol}/prices`

Historical prices for a security (newest first, spikes/crashes interpolated).
