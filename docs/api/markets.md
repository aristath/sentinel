# Markets

Base path: `/api/markets`

---

## `GET /api/markets/status`

Returns open/closed status for every exchange that has at least one security in the current universe. Exchanges with no securities are excluded.

**Response**
```json
{
  "markets": [
    { "name": "EU", "status": "OPEN", "is_open": true },
    { "name": "HKEX", "status": "CLOSE", "is_open": false },
    { "name": "ATHEX", "status": "OPEN", "is_open": true }
  ],
  "any_open": true
}
```

- `status` — Raw status string from broker: `OPEN` or `CLOSE`
- `is_open` — `true` when `status == "OPEN"`
- `any_open` — `true` if at least one relevant exchange is currently open
