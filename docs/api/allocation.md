# Allocation

Base path: `/api/allocation`

Read and write allocation data for radar chart display and bulk target management.

---

## `GET /api/allocation/current`

Returns current vs target allocations formatted for radar chart display.

**Response**
```json
{
  "geography": [
    { "name": "US", "current_pct": 58.2, "target_pct": 60.0 }
  ],
  "industry": [
    { "name": "Technology", "current_pct": 32.1, "target_pct": 30.0 }
  ],
  "alerts": []
}
```

---

## `GET /api/allocation/targets`

Returns all allocation targets as nested dicts, suitable for form population.

**Response**
```json
{
  "geography": { "US": 0.6, "EU": 0.4 },
  "industry": { "Technology": 0.3, "Healthcare": 0.2 }
}
```

---

## `GET /api/allocation/available-geographies`

Returns all geography categories that exist in either securities or allocation targets.

**Response**
```json
{ "geographies": ["EU", "US", "Asia"] }
```

---

## `GET /api/allocation/available-industries`

Returns all industry categories that exist in either securities or allocation targets.

**Response**
```json
{ "industries": ["Energy", "Healthcare", "Technology"] }
```

---

## `PUT /api/allocation/targets/geography`

Replace all geography target weights in one request.

**Request body**
```json
{ "targets": { "US": 0.6, "EU": 0.3, "Asia": 0.1 } }
```

**Response**
```json
{ "status": "ok" }
```

---

## `PUT /api/allocation/targets/industry`

Replace all industry target weights in one request.

**Request body**
```json
{ "targets": { "Technology": 0.3, "Healthcare": 0.2, "Energy": 0.1 } }
```

**Response**
```json
{ "status": "ok" }
```

---

## `DELETE /api/allocation/targets/geography/{name}`

Delete a geography target. The category disappears from the UI if no security uses it.

**Response**
```json
{ "status": "ok" }
```

---

## `DELETE /api/allocation/targets/industry/{name}`

Delete an industry target. The category disappears from the UI if no security uses it.

**Response**
```json
{ "status": "ok" }
```
