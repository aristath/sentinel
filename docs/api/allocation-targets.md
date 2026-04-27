# Allocation Targets

Base path: `/api/allocation-targets`

Manages the target weight for each geography and industry category. These weights drive the ideal portfolio allocation computed by the Planner.

---

## `GET /api/allocation-targets`

Returns all stored allocation target weights, split by type.

**Response**
```json
{
  "geography": [
    { "type": "geography", "name": "US", "weight": 0.6 },
    { "type": "geography", "name": "EU", "weight": 0.4 }
  ],
  "industry": [
    { "type": "industry", "name": "Technology", "weight": 0.3 }
  ]
}
```

---

## `PUT /api/allocation-targets/{target_type}/{name}`

Set the weight for a single allocation target.

**Path params**
- `target_type` — `geography` or `industry`
- `name` — Category name (e.g. `US`, `Technology`)

**Request body**
```json
{ "weight": 0.6 }
```

**Response**
```json
{ "status": "ok" }
```

**Errors**
- `400` — Invalid `target_type`
