"""Market timing checks for jobs."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, Protocol

logger = logging.getLogger(__name__)

# How often to refresh market data (5 minutes)
MARKET_DATA_TTL = timedelta(minutes=5)


class MarketChecker(Protocol):
    """Protocol for checking market status."""

    def is_any_market_open(self) -> bool:
        """Check if any market is currently open."""
        ...

    def is_security_market_open(self, symbol: str) -> bool:
        """Check if the market for a specific security is open."""
        ...

    def are_all_markets_closed(self) -> bool:
        """Check if all markets are closed."""
        ...


class BrokerMarketChecker:
    """Real market checker using broker API with automatic refresh."""

    def __init__(self, broker, ttl: timedelta = MARKET_DATA_TTL):
        self._broker = broker
        self._market_data: dict = {}
        self._last_fetch: Optional[datetime] = None
        self._ttl = ttl
        self._refresh_in_progress = False

    def _is_stale(self) -> bool:
        """Check if market data needs refresh."""
        if self._last_fetch is None:
            return True
        return datetime.now() - self._last_fetch > self._ttl

    async def refresh(self) -> None:
        """Fetch current market status from broker."""
        if self._refresh_in_progress:
            return
        self._refresh_in_progress = True
        try:
            data = await self._broker.get_market_status("*")
            if data:
                self._market_data = {m.get("n2"): m for m in data.get("m", [])}
                self._last_fetch = datetime.now()
                logger.debug(f"Market data refreshed: {len(self._market_data)} markets")
        except Exception as e:
            logger.warning(f"Failed to refresh market data: {e}")
        finally:
            self._refresh_in_progress = False

    async def ensure_fresh(self) -> None:
        """Refresh market data if stale."""
        if self._is_stale():
            await self.refresh()

    def is_any_market_open(self) -> bool:
        """Check if any market is currently open."""
        return any(m.get("s") == "OPEN" for m in self._market_data.values())

    def is_security_market_open(self, symbol: str) -> bool:
        """Check if the market for a specific security is open."""
        if "." not in symbol:
            return False
        suffix = symbol.split(".")[-1]
        market_map = {"US": "NASDAQ", "GR": "XETRA", "L": "LSE"}
        market_name = market_map.get(suffix)
        if not market_name:
            return False
        market = self._market_data.get(market_name)
        return market is not None and market.get("s") == "OPEN"

    def are_all_markets_closed(self) -> bool:
        """Check if all markets are closed."""
        if not self._market_data:
            return True
        return all(m.get("s") != "OPEN" for m in self._market_data.values())
