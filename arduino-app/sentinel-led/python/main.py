"""
Sentinel LED App - Trade recommendations display for Arduino UNO Q.

Fetches trade recommendations from sentinel API and provides them
to the MCU on demand. MCU pulls next trade when ready (after scrolling).

This runs as an Arduino App via arduino-app-cli.
"""

import logging
import os
import time
from dataclasses import dataclass
from threading import Lock

import requests
from arduino.app_utils import App, Bridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Configuration
SENTINEL_API_URL = os.environ.get("SENTINEL_API_URL", "http://172.17.0.1:8000")
REFRESH_INTERVAL = 300  # Refresh recommendations every 5 minutes


@dataclass
class Trade:
    """A trade recommendation to display."""

    action: str
    amount: float
    symbol: str
    sell_pct: float = 0.0

    def to_display_string(self) -> str:
        """Format trade for LED display."""
        if self.action == "SELL":
            return f"{self.symbol} -${self.amount:,.2f} (-{int(self.sell_pct)}%)"
        else:
            return f"{self.symbol} +${self.amount:,.2f}"


class TradeProvider:
    """Provides trades to MCU on demand."""

    def __init__(self):
        self._trades: list[Trade] = []
        self._index = 0
        self._lock = Lock()
        self._last_fetch = 0

    def fetch_recommendations(self) -> None:
        """Fetch trade recommendations from sentinel API."""
        try:
            resp = requests.get(f"{SENTINEL_API_URL}/api/planner/recommendations", timeout=30)
            resp.raise_for_status()
            data = resp.json()
            recommendations = data.get("recommendations", [])

            with self._lock:
                self._trades = []
                for rec in recommendations:
                    action = rec.get("action", "").upper()
                    value = abs(rec.get("value_delta_eur", 0))
                    symbol = rec.get("symbol", "")
                    current_value = rec.get("current_value_eur", 0)

                    if action == "SELL":
                        sell_pct = (value / current_value * 100) if current_value > 0 else 100
                        trade = Trade(action="SELL", amount=value, symbol=symbol, sell_pct=sell_pct)
                    else:
                        trade = Trade(action="BUY", amount=value, symbol=symbol)

                    self._trades.append(trade)

                self._index = 0
                self._last_fetch = time.time()

            logger.info(f"Fetched {len(self._trades)} trade recommendations")

        except requests.RequestException as e:
            logger.warning(f"Failed to fetch recommendations: {e}")

    def get_next_trade(self) -> str:
        """Get next trade string. Called by MCU via Bridge."""
        # Refresh if needed
        if time.time() - self._last_fetch > REFRESH_INTERVAL:
            self.fetch_recommendations()

        with self._lock:
            if not self._trades:
                return ""

            trade = self._trades[self._index]
            self._index = (self._index + 1) % len(self._trades)

            text = trade.to_display_string()
            logger.debug(f"Providing trade: {text}")
            return text


# Global provider instance
provider = TradeProvider()


def get_next_trade() -> str:
    """Bridge callback - called by MCU to get next trade."""
    return provider.get_next_trade()


def loop():
    """Main loop - refresh recommendations periodically."""
    time.sleep(REFRESH_INTERVAL)
    provider.fetch_recommendations()


def main():
    """Entry point."""
    logger.info("Sentinel LED App starting...")

    # Register callback for MCU to fetch trades
    Bridge.provide("getNextTrade", get_next_trade)

    # Initial fetch
    provider.fetch_recommendations()

    logger.info("Ready - MCU will pull trades on demand")

    # Run app loop
    App.run(user_loop=loop)


if __name__ == "__main__":
    main()
