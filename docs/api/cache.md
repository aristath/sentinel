# Cache

Base path: `/api/cache`

Manages the in-memory TTL cache used for expensive computations (e.g. contrarian signal analysis stored under the `motion` cache name).

---

## `GET /api/cache/stats`

Returns statistics for all in-memory caches.

**Response**
```json
{
  "motion": {
    "name": "motion",
    "entries": 18,
    "ttl_seconds": 86400,
    "hits": 142,
    "misses": 23,
    "hit_rate": 0.86
  }
}
```

---

## `POST /api/cache/clear`

Clear one or all caches.

**Query params**
- `name` (string, optional) — Cache name to clear (e.g. `motion`). Omit to clear all caches.

**Response** (specific cache)
```json
{ "cleared": { "motion": 18 } }
```

**Response** (all caches)
```json
{ "cleared": { "motion": 18 } }
```
