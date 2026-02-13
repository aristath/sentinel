# pyright: reportMissingImports=false
"""
Sentinel LED App - NeoPixel heatmap display for Arduino UNO Q.

The MCU owns animation/rendering and polls the MPU via Arduino Bridge RPC:

  Bridge.call("heatmap/get") -> [[before40],[after40]]

Each array has 40 scores (clamped to [-0.5, +0.5]) representing per-segment P/L:
  score = (current_price - avg_cost) / avg_cost

The "before" vs "after" difference comes from applying Sentinel's planner
recommendations to weights (as-if executed).
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


SENTINEL_API_URL = os.environ.get("SENTINEL_API_URL", "http://172.17.0.1:8000")
REFRESH_INTERVAL_SEC = 30  # MCU polls every 30s; keep cache roughly aligned.
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


class HeatmapProvider:
    def __init__(self) -> None:
        self._lock = Lock()
        self._last_refresh = 0.0
        self._before: list[float] = [0.0] * PARTS
        self._after: list[float] = [0.0] * PARTS

    def _fetch_portfolio(self) -> dict:
        resp = requests.get(f"{SENTINEL_API_URL}/api/portfolio", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _fetch_recommendations(self) -> list[dict]:
        resp = requests.get(f"{SENTINEL_API_URL}/api/planner/recommendations", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("recommendations", []) or []

    def refresh(self) -> None:
        try:
            portfolio = self._fetch_portfolio()
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
                before40 = [0.0] * PARTS
                after40 = [0.0] * PARTS
            else:
                after_values = dict(before_values)
                try:
                    recs = self._fetch_recommendations()
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
                before40 = before_parts
                after40 = after_parts

            with self._lock:
                self._before = before40
                self._after = after40
                self._last_refresh = time.time()

        except Exception as e:  # noqa: BLE001
            logger.warning("Heatmap refresh failed: %s", e)

    def get(self) -> list[list[float]]:
        # Refresh on demand if cache is stale.
        if time.time() - self._last_refresh > REFRESH_INTERVAL_SEC:
            self.refresh()
        with self._lock:
            return [self._before, self._after]


provider = HeatmapProvider()


def get_heatmap() -> list[list[float]]:
    return provider.get()


def loop() -> None:
    # Keep the cache warm even if MCU doesn't call for a while.
    time.sleep(REFRESH_INTERVAL_SEC)
    provider.refresh()


def main() -> None:
    logger.info("Sentinel LED heatmap app starting...")
    Bridge.provide("heatmap/get", get_heatmap)
    provider.refresh()
    logger.info("Ready: providing heatmap/get")
    App.run(user_loop=loop)


if __name__ == "__main__":
    main()
