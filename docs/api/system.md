# System

General health and version endpoints. No shared prefix.

---

## `GET /api/health`

Health check. Returns broker connection status and current trading mode.

**Response**
```json
{
  "status": "healthy",
  "broker_connected": true,
  "trading_mode": "research"
}
```

---

## `GET /api/version`

Returns the application version string.

**Response**
```json
{ "version": "v2026.04.14.04.47" }
```

The version uses a date-based format (`v{YYYY}.{MM}.{DD}.{HH}.{MM}`).
