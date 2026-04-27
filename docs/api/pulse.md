# Pulse

Base path: `/api/pulse`

Provides labels derived from the active security universe for use by the Pulse classification feature.

---

## `GET /api/pulse/labels`

Returns geographies and industries from **active** securities only.

**Response**
```json
{
  "geographies": ["EU", "US"],
  "industries": ["Healthcare", "Technology"]
}
```
