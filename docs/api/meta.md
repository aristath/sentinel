# Meta

Base path: `/api/meta`

---

## `GET /api/meta/categories`

Returns all distinct geography and industry categories derived from all securities (active and inactive) in the database.

**Response**
```json
{
  "geographies": ["Asia", "EU", "US"],
  "industries": ["Energy", "Healthcare", "Technology"]
}
```
