"""
LED Controller - Displays trade recommendations as scrolling text.

Fetches trade recommendations from the Planner and displays them
one at a time on the LED matrix as scrolling text.
"""

import asyncio
import logging
from typing import Optional

from sentinel.led.bridge import LEDBridge
from sentinel.led.state import Trade
from sentinel.planner import Planner
from sentinel.settings import Settings

logger = logging.getLogger(__name__)


class LEDController:
    """Controller for LED trade display.

    Fetches trade recommendations and displays them as scrolling
    text on the Arduino UNO Q LED matrix.
    """

    SYNC_INTERVAL = 300  # Refetch recommendations every 5 minutes

    def __init__(self):
        self._planner = Planner()
        self._settings = Settings()
        self._bridge = LEDBridge()
        self._trades: list[Trade] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the LED controller.

        Checks if LED display is enabled in settings, connects to
        the MCU bridge, and begins the display loop.
        """
        enabled = await self._settings.get("led_display_enabled", False)
        if not enabled:
            logger.info("LED display disabled by setting")
            return

        if not await self._bridge.connect():
            logger.warning("LED Bridge unavailable (not on Arduino UNO Q?)")
            return

        logger.info("LED controller starting")
        self._running = True

        # Main loop: fetch recommendations and display them
        while self._running:
            await self._fetch_and_display()

    def stop(self) -> None:
        """Stop the LED controller."""
        self._running = False
        logger.info("LED controller stopped")

    async def _fetch_and_display(self) -> None:
        """Fetch trade recommendations and display them."""
        try:
            recommendations = await self._planner.get_recommendations()

            if not recommendations:
                logger.debug("No trade recommendations to display")
                await asyncio.sleep(self.SYNC_INTERVAL)
                return

            # Convert recommendations to Trade objects
            self._trades = []
            for rec in recommendations:
                if rec.action == "sell":
                    # Calculate sell percentage
                    if rec.current_value_eur > 0:
                        sell_pct = (abs(rec.value_delta_eur) / rec.current_value_eur) * 100
                    else:
                        sell_pct = 100
                    trade = Trade(
                        action="SELL",
                        amount=abs(rec.value_delta_eur),
                        symbol=rec.symbol,
                        sell_pct=sell_pct,
                    )
                else:
                    trade = Trade(
                        action="BUY",
                        amount=rec.value_delta_eur,
                        symbol=rec.symbol,
                    )
                self._trades.append(trade)

            logger.info(f"Displaying {len(self._trades)} trade recommendations")

            # Display each trade one at a time
            for trade in self._trades:
                if not self._running:
                    break

                text = trade.to_display_string()
                await self._bridge.set_text(text)

                # Small delay between trades
                await asyncio.sleep(1)

            # Wait before fetching new recommendations
            if self._running:
                await asyncio.sleep(self.SYNC_INTERVAL)

        except Exception as e:
            logger.error(f"Error in LED display loop: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute on error

    async def force_refresh(self) -> None:
        """Force an immediate refresh of trade recommendations."""
        await self._fetch_and_display()

    @property
    def is_running(self) -> bool:
        """Check if controller is running."""
        return self._running

    @property
    def trade_count(self) -> int:
        """Get number of trades to display."""
        return len(self._trades)
