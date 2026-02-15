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
    """Fetch total portfolio value in EUR and send to MCU."""
    portfolio = _fetch("/api/portfolio")
    total_eur = portfolio.get("total_value_eur", 0)
    value = max(0, min(99999999, round(total_eur)))

    logger.info("Portfolio value: EUR %d, sending to MCU", value)
    Bridge.call("hm.u", [value], timeout=10)


def loop() -> None:
    time.sleep(REFRESH_INTERVAL_SEC)
    try:
        push_once()
    except Exception as e:  # noqa: BLE001
        logger.warning("Heatmap push failed: %s", e)


def main() -> None:
    logger.info("Sentinel LED abacus app starting...")
    try:
        push_once()
    except Exception as e:  # noqa: BLE001
        logger.warning("Initial push failed: %s", e)
    logger.info("Ready: updating every %ss", REFRESH_INTERVAL_SEC)
    App.run(user_loop=loop)


if __name__ == "__main__":
    main()
