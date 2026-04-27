# Prices

Base path: `/api/prices`

Bulk price operations across the full security universe. For per-security price history and sync, see [Securities](securities.md).

---

## `POST /api/prices/sync-all`

Syncs historical prices for all securities that have fewer than 100 days of price data. No-op if all securities are already populated.

**Response**
```json
{ "status": "ok" }
```
