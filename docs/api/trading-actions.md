# Trading Actions

These endpoints execute trades directly against the broker. They are mounted under the `/api/securities` prefix.

> **Trading mode**: In `research` mode (the default) the broker will not place a real order. Switch to `live` via [Settings](settings.md) to enable live execution.

---

## `POST /api/securities/{symbol}/buy`

Place a market buy order for a security.

**Path params**
- `symbol` — Security symbol (e.g. `AAPL.US`)

**Query params**
- `quantity` (int, required) — Number of shares/units to buy

**Response**
```json
{ "order_id": "abc123" }
```

**Errors**
- `400` — Order failed (broker rejected or security not found)

---

## `POST /api/securities/{symbol}/sell`

Place a market sell order for a security.

**Path params**
- `symbol` — Security symbol (e.g. `AAPL.US`)

**Query params**
- `quantity` (int, required) — Number of shares/units to sell

**Response**
```json
{ "order_id": "abc124" }
```

**Errors**
- `400` — Order failed (broker rejected or security not found)
