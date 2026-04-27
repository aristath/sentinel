# LED Display

Base path: `/api/led`

Controls the optional hardware LED display connected via an Arduino UNO Q bridge.

---

## `GET /api/led/status`

Returns the current state of the LED display and its hardware bridge.

**Response**
```json
{
  "enabled": false,
  "running": false,
  "trade_count": 0,
  "broker_connected": true,
  "bridge": {
    "bridge_ok": true,
    "consecutive_failures": 0,
    "last_attempt_ts": 1745748000,
    "last_attempt_at": "2026-04-27T10:00:00+00:00",
    "last_success_ts": 1745748000,
    "last_success_at": "2026-04-27T10:00:00+00:00",
    "last_error_ts": null,
    "last_error_at": null,
    "last_error": null,
    "watchdog_action": null,
    "app_instance": "arduino-app/sentinel",
    "updated_at_ts": 1745748000,
    "updated_at": "2026-04-27T10:00:00+00:00",
    "stale_seconds": 42,
    "stale_threshold_seconds": 600,
    "is_stale": false
  }
}
```

---

## `PUT /api/led/enabled`

Enable or disable the LED display.

**Request body**
```json
{ "enabled": true }
```

**Response**
```json
{ "enabled": true }
```

---

## `POST /api/led/refresh`

Force an immediate LED display refresh without waiting for the next cycle.

**Response** (when running)
```json
{ "status": "refreshed", "trade_count": 3 }
```

**Response** (when not running)
```json
{ "status": "not_running" }
```

---

## `GET /api/led/bridge/health`

Get the latest health telemetry stored by the Arduino UNO Q bridge.

**Response** — Same shape as the `bridge` field in [`GET /api/led/status`](#get-apiled-status).

---

## `POST /api/led/bridge/health`

Store health telemetry reported by the Arduino UNO Q bridge. Called by the bridge process itself.

**Request body** (all fields optional)
```json
{
  "bridge_ok": true,
  "consecutive_failures": 0,
  "last_attempt_ts": 1745748000,
  "last_success_ts": 1745748000,
  "last_error_ts": null,
  "last_error": null,
  "watchdog_action": null,
  "app_instance": "bridge-v1"
}
```

**Response** — Normalised health object (same shape as [`GET /api/led/bridge/health`](#get-apiledbridgehealth)).
