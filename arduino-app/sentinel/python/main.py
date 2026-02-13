# pyright: reportMissingImports=false
"""
Sentinel LED App - NeoPixel heatmap display for Arduino UNO Q.

Transport follows Arduino router docs and our prior working app:
- The MPU (this Python process) polls Sentinel API, computes before/after scores,
  then *pushes* them to the MCU with `Bridge.call("heatmap/update", before, after)`.
- The MCU registers `Bridge.provide("heatmap/update", ...)` and renders locally.
"""

from __future__ import annotations

import logging
import os
import time
from threading import Lock

import requests
from arduino.app_utils import App, Bridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _default_gateway_ip() -> str | None:
    """Best-effort container->host gateway discovery (no external deps)."""
    try:
        with open("/proc/net/route") as f:
            # Iface  Destination  Gateway  Flags ...
            for line in f.readlines()[1:]:
                parts = line.strip().split()
                if len(parts) < 4:
                    continue
                dest, gw, flags = parts[1], parts[2], parts[3]
                if dest != "00000000":
                    continue
                if int(flags, 16) & 0x2 == 0:
                    continue
                # Gateway is little-endian hex.
                b = bytes.fromhex(gw)
                ip = ".".join(str(x) for x in b[::-1])
                return ip
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
REFRESH_INTERVAL_SEC = 30  # Push cadence to the MCU.
SCORE_CLAMP_ABS = 0.5
PARTS = 40


def clamp_score(x: float) -> float:
    if x < -SCORE_CLAMP_ABS:
        return -SCORE_CLAMP_ABS
    if x > SCORE_CLAMP_ABS:
        return SCORE_CLAMP_ABS
    return x


def largest_remainder_counts(weights: list[float], total_parts: int) -> list[int]:
    total_w = sum(w for w in weights if w > 0)
    if total_w <= 0:
        return [0 for _ in weights]

    scaled = [max(0.0, w) / total_w * total_parts for w in weights]
    floors = [int(x) for x in scaled]
    remainder = total_parts - sum(floors)
    fracs = sorted(((scaled[i] - floors[i], i) for i in range(len(weights))), reverse=True)

    counts = floors[:]
    for _, i in fracs[:remainder]:
        counts[i] += 1
    return counts


class HeatmapPusher:
    def __init__(self) -> None:
        self._lock = Lock()
        self._last_refresh = 0.0
        self._before: list[float] = [0.0] * PARTS
        self._after: list[float] = [0.0] * PARTS
        self._session = requests.Session()

    def _fetch(self, path: str) -> dict:
        resp = self._session.get(f"{SENTINEL_API_URL}{path}", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _compute(self) -> tuple[list[float], list[float]]:
        portfolio = self._fetch("/api/portfolio")
        positions = portfolio.get("positions", []) or []

        before_values: dict[str, float] = {}
        scores: dict[str, float] = {}
        for p in positions:
            sym = str(p.get("symbol") or "")
            if not sym:
                continue
            qty = float(p.get("quantity") or 0.0)
            current_price = float(p.get("current_price") or 0.0)
            avg_cost = float(p.get("avg_cost") or 0.0)

            before_values[sym] = max(0.0, qty * current_price)
            if avg_cost > 0 and current_price > 0:
                score = (current_price - avg_cost) / avg_cost
            else:
                score = 0.0
            scores[sym] = clamp_score(float(score))

        total_before = sum(before_values.values())
        if total_before <= 0 or not scores:
            return [0.0] * PARTS, [0.0] * PARTS

        after_values = dict(before_values)
        try:
            recs = self._fetch("/api/planner/recommendations").get("recommendations", []) or []
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to fetch recommendations; using before state for after: %s", e)
            recs = []

        for r in recs:
            sym = r.get("symbol")
            if not sym:
                continue
            delta = float(r.get("value_delta_eur") or 0.0)
            after_values[sym] = max(0.0, after_values.get(sym, 0.0) + delta)

        total_after = sum(after_values.values()) or total_before

        # Allocate 40 parts by weight, repeating per-security score.
        symbols = sorted(scores.keys())
        w_before = [before_values.get(s, 0.0) / total_before for s in symbols]
        w_after = [after_values.get(s, 0.0) / total_after for s in symbols]
        s_vals = [scores[s] for s in symbols]

        counts_before = largest_remainder_counts(w_before, PARTS)
        counts_after = largest_remainder_counts(w_after, PARTS)

        before_parts: list[float] = []
        after_parts: list[float] = []
        for score, nb, na in zip(s_vals, counts_before, counts_after, strict=False):
            before_parts.extend([score] * int(nb))
            after_parts.extend([score] * int(na))

        # Guard exact length then sort so index corresponds to percentile, not identity.
        before_parts = (before_parts + [0.0] * PARTS)[:PARTS]
        after_parts = (after_parts + [0.0] * PARTS)[:PARTS]
        before_parts.sort()
        after_parts.sort()
        return before_parts, after_parts

    def push_once(self) -> None:
        before40, after40 = self._compute()
        with self._lock:
            self._before = before40
            self._after = after40
            self._last_refresh = time.time()
        # Push to MCU; if it fails, keep cached data for next try.
        Bridge.call("heatmap/update", before40, after40, timeout=10)


pusher = HeatmapPusher()


def loop() -> None:
    try:
        pusher.push_once()
    except Exception as e:  # noqa: BLE001
        logger.warning("Heatmap push failed: %s", e)
    time.sleep(REFRESH_INTERVAL_SEC)


def main() -> None:
    logger.info("Sentinel LED heatmap app starting...")
    try:
        pusher.push_once()
    except Exception as e:  # noqa: BLE001
        logger.warning("Initial heatmap push failed: %s", e)
    logger.info("Ready: pushing heatmap/update every %ss", REFRESH_INTERVAL_SEC)
    App.run(user_loop=loop)


if __name__ == "__main__":
    main()
