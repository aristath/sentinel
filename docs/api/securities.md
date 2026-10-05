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
    "ai_research_multiplier": 0.5,
    "ai_research_multiplier_updated_at": "2026-05-17T12:00:00+00:00",
    "ai_research_multiplier_source": "ai_research",
    "ai_research_multiplier_analysis": "Long-term strategic fit remains neutral.",
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
| `geography` | ISO‑2 country‑of‑risk from Tradernet (`attributes.CntryOfRisk`). Auto‑filled by the metadata sync; blank for ETFs and for tickers Tradernet does not classify. Not editable via the API. |
| `industry` | Refinitiv/LSEG TRBC industry name from Tradernet (`sector_code`). Auto‑filled by the metadata sync; blank for ETFs. Not editable via the API. |
| `market_id` | Broker market identifier string |
| `data` | Raw JSON metadata blob from broker (security details, market info) |
| `ai_research_multiplier` | Stored AI research rating, 0 avoid, 0.5 neutral, 1 prefer |
| `ai_research_multiplier_updated_at` | Last per-security preference update timestamp |
| `ai_research_multiplier_source` | Rating source, usually `ai_research`, `manual`, `decay`, or `migration` |
| `ai_research_multiplier_analysis` | Human-readable rationale for the stored preference |
| `quote_data` | Latest raw quote data from broker (null if not yet synced) |
| `quote_updated_at` | Timestamp of last quote sync |
| `last_synced` | Date of last metadata sync |

---

## `POST /api/securities`

Add a new security to the universe. Fetches metadata and 20 years of historical prices from the broker. If the symbol exists but is inactive, it is re-enabled instead.

`geography` and `industry` are populated by the next `sync:metadata` job — they are not accepted in the request body. Any client-supplied values are silently dropped.

**Request body**
```json
{
  "symbol": "AAPL.US"
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
- `502` — Adding the symbol to Freedom24 Favorites failed

---

## `GET /api/securities/search`

Searches Tradernet's catalog, including instruments outside Sentinel's universe.
Does not change Favorites, local securities, or trading state.

**Query params**

- `query` (string, required) — Non-empty search text: symbol, name, or ISIN.
- `exchange` (string, optional) — Broker exchange code, for example `FIX` or
  `EU`. Filters the broker's initial candidates by market code. Trimmed and
  uppercased; empty values are rejected.

**Response**

Up to 30 broker candidates before optional exchange filtering. A specific
exchange can have matches beyond the broker's initial limit; narrow the query
to find them. Original fields are preserved alongside normalized
fields and local tracking status. `tracked` includes inactive local rows;
`in_universe` means active. Local permissions are null for untracked symbols.

```json
[
  {
    "t": "AAPL.US",
    "n": "Apple Inc.",
    "isin": "US0378331005",
    "mkt": "FIX",
    "mkt_id": "30000000001",
    "type": 1,
    "kind": 1,
    "x_curr": "USD",
    "symbol": "AAPL.US",
    "name": "Apple Inc.",
    "market": "FIX",
    "market_id": "30000000001",
    "currency": "USD",
    "instrument_type": 1,
    "instrument_kind": 1,
    "tracked": false,
    "in_universe": false,
    "allow_buy": null,
    "allow_sell": null
  }
]
```

An empty list means a successful search with no matches.

**Errors**

- `400` — Blank query or explicitly blank exchange
- `422` — Missing required query
- `503` — Broker is not connected
- `502` — Broker search failed or returned malformed data

---

## `GET /api/securities/{symbol}/broker-info`

Returns broker metadata for an exact symbol, even if it is not tracked locally.
Does not import the instrument or change Favorites.

**Response**

```json
{
  "symbol": "AAPL.US",
  "info": {
    "short_name": "Apple Inc.",
    "currency": "USD",
    "lot": 1
  }
}
```

The `info` object preserves the broker response fields.

**Errors**

- `400` — Blank symbol
- `503` — Broker is not connected
- `404` — Broker information unavailable (unknown symbol or failed lookup)

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

Updates one security's AI research multiplier and stores the analysis explaining the decision.

**Request body**
```json
{
  "symbol": "MOH.GR",
  "ai_research_multiplier": 0.02,
  "analysis": "Too exposed to fossil-fuel demand for the long-term portfolio."
}
```

**Response**
Returns the updated single-security payload, including stored and effective faded preference fields.

**Errors**
- `400` — Missing/invalid `symbol`, `ai_research_multiplier`, or `analysis`
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
  "ai_research_multiplier": 0.5,
  "ai_research_multiplier_age_weeks": 0.0,
  "ai_research_multiplier_updated_at": "2026-05-17T12:00:00+00:00",
  "ai_research_multiplier_source": "ai_research",
  "ai_research_multiplier_analysis": "Long-term strategic fit remains neutral.",
  "quantity": 5.0,
  "current_price": 270.94
}
```

**Errors**
- `404` — Security not found

---

## `PUT /api/securities/{symbol}`

Update security metadata and execution controls. Only the following fields are accepted; all others (including legacy `geography` and `industry` values) are silently ignored.

| Field | Type | Description |
|---|---|---|
| `aliases` | string | Comma-separated search aliases for companion apps |
| `allow_buy` | int (0/1) | Whether buys are permitted |
| `allow_sell` | int (0/1) | Whether sells are permitted |
| `ai_research_multiplier` | float | Manual override of the stored AI research multiplier. Research tasks use `POST /api/securities/preference`. |
| `ai_research_multiplier_analysis` | string | Optional rationale when setting `ai_research_multiplier` manually |
| `active` | int (0/1) | Active flag |

**Response**
```json
{
  "symbol": "AAPL.US",
  "ai_research_multiplier": 0.6,
  "ai_research_multiplier_source": "manual",
  "ai_research_multiplier_analysis": "Manual AI research multiplier override from Sentinel UI."
}
```

**Errors**
- `404` — Security not found

---

## `DELETE /api/securities/{symbol}`

For an active security, removes it from Freedom24 Favorites and applies the safe
local universe rule:

- with a current position, it remains active and sell-only;
- without a current position, it becomes inactive and both trade permissions are disabled.

For an already-inactive security, permanently deletes the security and its
derived price/forecast/strategy data only when it has never had a trade or
dividend transaction. Historical transactions are never deleted.

**Query params**
- `sell_position` (bool, deprecated) — Retained for old clients; removal never places a sell order.

**Response**
```json
{ "status": "ok", "symbol": "AAPL.US", "deleted": true, "sold_quantity": 0, "transaction_count": 0 }
```

**Errors**
- `404` — Security not found
- `409` — Permanent deletion is blocked by transaction history or a position
- `502` — Removing an active symbol from Freedom24 Favorites failed

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
