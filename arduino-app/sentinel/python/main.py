# pyright: reportMissingImports=false
"""
Sentinel LED App — soroban abacus display for Arduino UNO Q.

Fetches total portfolio value in EUR, sends as integer to MCU.
MCU renders the value as soroban-style digits on an 8×5 NeoPixel shield.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests
from arduino.app_utils import App, Bridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_HEARTBEAT_STALE_SEC = 600


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s=%r, using default=%d", name, raw, default)
        return default
    if value < minimum:
        logger.warning("%s=%d below minimum=%d, clamping", name, value, minimum)
        return minimum
    return value


REFRESH_INTERVAL_SEC = _env_int("LED_REFRESH_INTERVAL_SEC", 60)
BRIDGE_TIMEOUT_SEC = _env_int("LED_BRIDGE_TIMEOUT_SEC", 10)
BRIDGE_RETRIES = _env_int("LED_BRIDGE_RETRIES", 3)
BRIDGE_RETRY_DELAY_SEC = _env_int("LED_BRIDGE_RETRY_DELAY_SEC", 1, minimum=0)
MAX_CONSECUTIVE_FAILURES = _env_int("LED_MAX_CONSECUTIVE_FAILURES", 5)
WATCHDOG_STALE_SEC = _env_int("LED_WATCHDOG_STALE_SEC", DEFAULT_HEARTBEAT_STALE_SEC)
WATCHDOG_CHECK_INTERVAL_SEC = _env_int("LED_WATCHDOG_CHECK_INTERVAL_SEC", 30)


def _default_gateway_ip() -> str | None:
    """Best-effort container->host gateway discovery (no external deps)."""
    try:
        with open("/proc/net/route") as f:
            for line in f.readlines()[1:]:
                parts = line.strip().split()
                if len(parts) < 4:
                    continue
                dest, gw, flags = parts[1], parts[2], parts[3]
                if dest != "00000000":
                    continue
                if int(flags, 16) & 0x2 == 0:
                    continue
                b = bytes.fromhex(gw)
                return ".".join(str(x) for x in b[::-1])
    except Exception:
        return None
    return None


_host_ip = os.environ.get("HOST_IP")
_gw = _default_gateway_ip()
SENTINEL_API_URL = (
    os.environ.get("SENTINEL_API_URL")
    or (f"http://{_host_ip}:8000" if _host_ip else None)
    or (f"http://{_gw}:8000" if _gw else None)
    or "http://172.17.0.1:8000"
)

_session = requests.Session()


def _fetch(path: str) -> dict:
    resp = _session.get(f"{SENTINEL_API_URL}{path}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict[str, Any]) -> None:
    resp = _session.post(f"{SENTINEL_API_URL}{path}", json=payload, timeout=10)
    resp.raise_for_status()


def _ts_to_utc(ts: int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


@dataclass
class BridgeRuntime:
    started_at_ts: int
    next_push_at_ts: int
    next_watchdog_at_ts: int
    last_attempt_ts: int | None = None
    last_success_ts: int | None = None
    last_error_ts: int | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    last_payload: list[int] | None = None


_runtime = BridgeRuntime(
    started_at_ts=int(time.time()),
    next_push_at_ts=int(time.time()),
    next_watchdog_at_ts=int(time.time()),
)


def _report_bridge_health(bridge_ok: bool, watchdog_action: str | None = None) -> None:
    payload = {
        "bridge_ok": bridge_ok,
        "last_attempt_ts": _runtime.last_attempt_ts,
        "last_success_ts": _runtime.last_success_ts,
        "last_error_ts": _runtime.last_error_ts,
        "last_error": _runtime.last_error,
        "consecutive_failures": _runtime.consecutive_failures,
        "watchdog_action": watchdog_action,
        "app_instance": "arduino-app/sentinel",
    }
    try:
        _post("/api/led/bridge/health", payload)
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to report bridge health to API: %s", e)


def _fetch_payload() -> tuple[list[int], dict[str, int]]:
    """Fetch data from Sentinel API and build hm.u payload."""
    portfolio = _fetch("/api/portfolio")
    total_eur = portfolio.get("total_value_eur", 0)
    value = max(0, min(99999999, round(total_eur)))

    return_pct = max(-99, min(99, round(portfolio.get("portfolio_return_pct", 0))))

    has_recs = 0
    try:
        planner = _fetch("/api/planner/recommendations")
        recs = planner.get("recommendations", [])
        has_recs = 1 if recs else 0
    except Exception:  # noqa: BLE001, S110
        pass  # Recommendations are optional; don't block the main update

    broker_connected = 0
    try:
        health = _fetch("/api/health")
        broker_connected = 1 if health.get("broker_connected") else 0
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to fetch broker health state: %s", e)

    summary = {
        "value": value,
        "return_pct": return_pct,
        "has_recs": has_recs,
        "broker_connected": broker_connected,
    }
    return [value, return_pct, has_recs, broker_connected], summary


def _force_restart(reason: str) -> None:
    logger.error("Restarting LED app container: %s", reason)
    _report_bridge_health(bridge_ok=False, watchdog_action=reason)
    time.sleep(0.2)
    os._exit(1)


def _push_once(source: str) -> None:
    payload, summary = _fetch_payload()
    _runtime.last_payload = payload
    _runtime.last_attempt_ts = int(time.time())
    logger.info(
        "Portfolio: EUR %d, P/L %d%%, recs=%d, broker_connected=%d, sending to MCU (%s)",
        summary["value"],
        summary["return_pct"],
        summary["has_recs"],
        summary["broker_connected"],
        source,
    )

    last_exc: Exception | None = None
    for attempt in range(1, BRIDGE_RETRIES + 1):
        try:
            Bridge.call("hm.u", payload, timeout=BRIDGE_TIMEOUT_SEC)
            _runtime.last_success_ts = int(time.time())
            _runtime.consecutive_failures = 0
            _runtime.last_error = None
            _runtime.last_error_ts = None
            logger.info("Bridge push success at %s", _ts_to_utc(_runtime.last_success_ts))
            _report_bridge_health(bridge_ok=True)
            return
        except Exception as e:  # noqa: BLE001
            last_exc = e
            logger.warning("Bridge push attempt %d/%d failed: %s", attempt, BRIDGE_RETRIES, e)
            if attempt < BRIDGE_RETRIES and BRIDGE_RETRY_DELAY_SEC > 0:
                time.sleep(BRIDGE_RETRY_DELAY_SEC)

    _runtime.consecutive_failures += 1
    _runtime.last_error_ts = int(time.time())
    _runtime.last_error = str(last_exc) if last_exc is not None else "unknown bridge error"
    _report_bridge_health(bridge_ok=False)
    raise RuntimeError(
        f"Request 'hm.u' failed after {BRIDGE_RETRIES} attempts: {_runtime.last_error} "
        f"(consecutive_failures={_runtime.consecutive_failures})"
    )


def _watchdog_check() -> None:
    now = int(time.time())

    if _runtime.last_success_ts is None:
        if now - _runtime.started_at_ts >= WATCHDOG_STALE_SEC:
            _force_restart("process_exit_no_success_within_stale_window")
        return

    stale_for = now - _runtime.last_success_ts
    if stale_for < WATCHDOG_STALE_SEC:
        return

    if _runtime.last_payload is None:
        _force_restart("process_exit_stale_no_payload")

    logger.error(
        "Bridge stale for %ds (threshold=%ds). Executing watchdog ping.",
        stale_for,
        WATCHDOG_STALE_SEC,
    )
    _runtime.last_attempt_ts = int(time.time())
    try:
        Bridge.call("hm.u", _runtime.last_payload, timeout=BRIDGE_TIMEOUT_SEC)
        _runtime.last_success_ts = int(time.time())
        _runtime.consecutive_failures = 0
        _runtime.last_error = None
        _runtime.last_error_ts = None
        logger.warning("Watchdog ping recovered bridge at %s", _ts_to_utc(_runtime.last_success_ts))
        _report_bridge_health(bridge_ok=True, watchdog_action="watchdog_recovered")
    except Exception as e:  # noqa: BLE001
        _runtime.consecutive_failures += 1
        _runtime.last_error_ts = int(time.time())
        _runtime.last_error = f"watchdog ping failed: {e}"
        _force_restart("process_exit_watchdog_ping_failed")


def _tick() -> None:
    now = int(time.time())

    if now >= _runtime.next_watchdog_at_ts:
        _watchdog_check()
        _runtime.next_watchdog_at_ts = now + WATCHDOG_CHECK_INTERVAL_SEC

    if now >= _runtime.next_push_at_ts:
        try:
            _push_once("scheduled")
        except Exception as e:  # noqa: BLE001
            logger.warning("Heatmap push failed: %s", e)
            if _runtime.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                _force_restart("process_exit_consecutive_bridge_failures")
        _runtime.next_push_at_ts = now + REFRESH_INTERVAL_SEC

    time.sleep(1)


def main() -> None:
    logger.info("Sentinel LED abacus app starting...")
    logger.info(
        "Config: refresh=%ss retries=%s timeout=%ss stale=%ss watchdog=%ss max_failures=%s api=%s",
        REFRESH_INTERVAL_SEC,
        BRIDGE_RETRIES,
        BRIDGE_TIMEOUT_SEC,
        WATCHDOG_STALE_SEC,
        WATCHDOG_CHECK_INTERVAL_SEC,
        MAX_CONSECUTIVE_FAILURES,
        SENTINEL_API_URL,
    )
    try:
        _push_once("startup")
    except Exception as e:  # noqa: BLE001
        logger.warning("Initial push failed: %s", e)
    logger.info(
        "Ready: updates every %ss, watchdog checks every %ss, last_success=%s",
        REFRESH_INTERVAL_SEC,
        WATCHDOG_CHECK_INTERVAL_SEC,
        _ts_to_utc(_runtime.last_success_ts),
    )
    App.run(user_loop=_tick)


if __name__ == "__main__":
    main()
