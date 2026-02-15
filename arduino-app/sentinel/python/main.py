# pyright: reportMissingImports=false
"""
Sentinel LED App — 2-digit portfolio return display for Arduino UNO Q.

Computes overall portfolio return %, sends a single int to MCU.
MCU renders the value as colored digits on a 5×8 NeoPixel shield (landscape).
"""

from __future__ import annotations

import logging
import os
import time

import requests
from arduino.app_utils import App, Bridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SEC = 300  # 5 minutes


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


def push_once() -> None:
    """Compute overall portfolio return % and send to MCU."""
    portfolio = _fetch("/api/portfolio")
    positions = portfolio.get("positions", []) or []

    total_invested = 0.0
    total_current = 0.0
    for p in positions:
        qty = float(p.get("quantity") or 0.0)
        price = float(p.get("current_price") or 0.0)
        avg_cost = float(p.get("avg_cost") or 0.0)
        if qty <= 0 or avg_cost <= 0:
            continue
        total_invested += avg_cost * qty
        total_current += price * qty

    if total_invested > 0:
        return_pct = round((total_current - total_invested) / total_invested * 100)
    else:
        return_pct = 0

    return_pct = max(-99, min(99, return_pct))

    logger.info("Portfolio return: %d%%, sending to MCU", return_pct)
    Bridge.call("hm.u", [return_pct], timeout=10)


def loop() -> None:
    time.sleep(REFRESH_INTERVAL_SEC)
    try:
        push_once()
    except Exception as e:  # noqa: BLE001
        logger.warning("Heatmap push failed: %s", e)


def main() -> None:
    logger.info("Sentinel LED app starting...")
    try:
        push_once()
    except Exception as e:  # noqa: BLE001
        logger.warning("Initial push failed: %s", e)
    logger.info("Ready: updating every %ss", REFRESH_INTERVAL_SEC)
    App.run(user_loop=loop)


if __name__ == "__main__":
    main()
