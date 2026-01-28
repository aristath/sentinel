"""
Broker - Single source of truth for all broker (Tradernet) operations.

Usage:
    broker = Broker()
    await broker.connect()
    quote = await broker.get_quote('AAPL.US')
    await broker.buy('AAPL.US', quantity=10)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sentinel.database import Database
from sentinel.settings import Settings

logger = logging.getLogger(__name__)


class Broker:
    """Single source of truth for broker operations."""

    _instance: Optional["Broker"] = None
    _api = None
    _trading = None

    def __new__(cls):
        """Singleton pattern - one broker connection."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._settings = Settings()
        self._db = Database()

    async def connect(self) -> bool:
        """Connect to Tradernet API."""
        if self._api is not None:
            return True

        api_key = await self._settings.get("tradernet_api_key")
        api_secret = await self._settings.get("tradernet_api_secret")

        if not api_key or not api_secret:
            return False

        try:
            from tradernet import TraderNetAPI, Trading

            self._api = TraderNetAPI(public=api_key, private=api_secret)
            self._trading = Trading(public=api_key, private=api_secret)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Tradernet: {e}")
            return False

    @property
    def connected(self) -> bool:
        """Check if connected to broker."""
        return self._api is not None

    # -------------------------------------------------------------------------
    # Market Data
    # -------------------------------------------------------------------------

    async def get_quote(self, symbol: str) -> Optional[dict]:
        """Get current quote for a symbol."""
        if not self._api:
            return None
        try:
            response = self._api.get_quotes([symbol])
            # Handle both response formats: {'quotes': [...]} and {'result': {'q': [...]}}
            quotes_list = None
            if response:
                if "quotes" in response:
                    quotes_list = response["quotes"]
                elif "result" in response and "q" in response["result"]:
                    quotes_list = response["result"]["q"]

            if quotes_list:
                for q in quotes_list:
                    if q.get("c") == symbol:
                        # Start with all raw API data, then add mapped convenience fields
                        result = dict(q)
                        result["symbol"] = symbol
                        result["price"] = q.get("ltp")
                        result["bid"] = q.get("bbp")
                        result["ask"] = q.get("bap")
                        result["change"] = q.get("chg")
                        result["change_percent"] = q.get("pcp")
                        return result
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
        return None

    async def get_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """Get quotes for multiple symbols (cached for 5 minutes)."""
        if not self._api:
            logger.warning("get_quotes: API not initialized")
            return {}

        # Check DB cache first (5 minute TTL)
        cache_key = "quotes:" + ",".join(sorted(symbols))
        cached = await self._db.cache_get(cache_key)
        if cached is not None:
            logger.info(f"get_quotes: Cache hit for {len(symbols)} symbols")
            return json.loads(cached)

        try:
            logger.info(f"get_quotes: Requesting {len(symbols)} symbols from API")
            response = self._api.get_quotes(symbols)
            logger.info(f"get_quotes: Response keys={list(response.keys()) if response else None}")
            result = {}
            # Handle both response formats: {'quotes': [...]} and {'result': {'q': [...]}}
            quotes_list = None
            if response:
                if "quotes" in response:
                    quotes_list = response["quotes"]
                elif "result" in response and "q" in response["result"]:
                    quotes_list = response["result"]["q"]

            if quotes_list:
                logger.info(f"get_quotes: Found {len(quotes_list)} quotes in response")
                for q in quotes_list:
                    symbol = q.get("c")
                    if symbol:
                        # Start with all raw API data, then add mapped convenience fields
                        quote = dict(q)
                        quote["symbol"] = symbol
                        quote["price"] = q.get("ltp")
                        quote["bid"] = q.get("bbp")
                        quote["ask"] = q.get("bap")
                        quote["change"] = q.get("chg")
                        quote["change_percent"] = q.get("pcp")
                        result[symbol] = quote
            else:
                logger.warning(
                    f"get_quotes: No quotes in response. Keys: {list(response.keys()) if response else None}"
                )

            # Cache the result (5 minutes = 300 seconds)
            await self._db.cache_set(cache_key, json.dumps(result), ttl_seconds=300)
            return result
        except Exception as e:
            logger.error(f"Failed to get quotes: {e}")
            return {}

    async def get_historical_prices(self, symbol: str, days: int = 365) -> list[dict]:
        """Get historical prices for a symbol."""
        if not self._api:
            return []
        try:
            end = datetime.now()
            start = end - timedelta(days=days)
            response = self._api.get_candles(symbol, start=start, end=end)
            if response and "candles" in response:
                return [
                    {
                        "date": c.get("d"),
                        "open": c.get("o"),
                        "high": c.get("h"),
                        "low": c.get("l"),
                        "close": c.get("c"),
                        "volume": c.get("v"),
                    }
                    for c in response["candles"]
                ]
        except Exception as e:
            logger.error(f"Failed to get history for {symbol}: {e}")
        return []

    async def get_historical_prices_bulk(self, symbols: list[str], years: int = 10) -> dict[str, list[dict]]:
        """Get historical prices for multiple symbols in one request."""
        import json

        import requests

        if not symbols:
            return {}

        try:
            end = datetime.now()
            start = end - timedelta(days=years * 365)

            params = {
                "cmd": "getHloc",
                "params": {
                    "id": ",".join(symbols),
                    "count": -1,
                    "timeframe": 1440,  # Daily
                    "date_from": start.strftime("%d.%m.%Y 00:00"),
                    "date_to": end.strftime("%d.%m.%Y 23:59"),
                    "intervalMode": "ClosedRay",
                },
            }

            response = requests.get("https://tradernet.com/api/", params={"q": json.dumps(params)}, timeout=60)
            data = response.json()

            result = {}
            if "hloc" in data and "xSeries" in data:
                for symbol in symbols:
                    if symbol in data["hloc"] and symbol in data["xSeries"]:
                        hloc = data["hloc"][symbol]
                        timestamps = data["xSeries"][symbol]
                        volumes = data.get("vl", {}).get(symbol, [])

                        prices = []
                        for i, (candle, ts) in enumerate(zip(hloc, timestamps, strict=False)):
                            # candle is [high, low, open, close]
                            prices.append(
                                {
                                    "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                                    "high": candle[0],
                                    "low": candle[1],
                                    "open": candle[2],
                                    "close": candle[3],
                                    "volume": volumes[i] if i < len(volumes) else 0,
                                }
                            )
                        result[symbol] = prices

            return result
        except Exception as e:
            logger.error(f"Failed to get bulk history: {e}")
            return {}

    # -------------------------------------------------------------------------
    # Portfolio
    # -------------------------------------------------------------------------

    async def get_portfolio(self) -> dict:
        """Get current portfolio from broker."""
        if not self._api:
            return {"positions": [], "cash": {}}
        try:
            response = self._api.account_summary()
            positions = []
            cash = {}

            if response and "result" in response:
                ps = response["result"].get("ps", {})

                # Parse positions from ps.pos
                for pos in ps.get("pos", []):
                    positions.append(
                        {
                            "symbol": pos.get("i"),  # instrument
                            "quantity": pos.get("q"),
                            "avg_cost": pos.get("bal_price_a"),  # average cost
                            "current_price": pos.get("mkt_price"),
                            "currency": pos.get("curr", "EUR"),
                            "name": pos.get("name"),
                            "market_value": pos.get("market_value"),
                            "profit": pos.get("profit_close"),
                        }
                    )

                # Parse cash balances from ps.acc
                for acc in ps.get("acc", []):
                    curr = acc.get("curr", "EUR")
                    cash[curr] = acc.get("s", 0)  # 's' is the balance

            return {"positions": positions, "cash": cash}
        except Exception as e:
            logger.error(f"Failed to get portfolio: {e}")
            return {"positions": [], "cash": {}}

    # -------------------------------------------------------------------------
    # Trading
    # -------------------------------------------------------------------------

    async def _is_live_mode(self) -> bool:
        """Check if we're in live trading mode."""
        mode = await self._settings.get("trading_mode", "research")
        return mode == "live"

    async def buy(self, symbol: str, quantity: int, price: float = None) -> Optional[str]:
        """Place a buy order. Returns order ID if successful.

        Args:
            symbol: The security symbol
            quantity: Number of shares to buy
            price: Limit price (optional). If provided, places a limit order.

        In research mode, returns a simulated order ID without executing.
        """
        if not await self._is_live_mode():
            price_info = f" @ {price}" if price else ""
            logger.debug(f"[RESEARCH MODE] Would buy {quantity} of {symbol}{price_info}")
            return f"RESEARCH-BUY-{symbol}-{quantity}"

        if not self._trading:
            return None
        try:
            kwargs = {"quantity": quantity}
            if price is not None:
                kwargs["price"] = price
            response = self._trading.buy(symbol, **kwargs)
            logger.info(f"Buy {symbol} response: {response}")
            return response.get("order_id") if response else None
        except Exception as e:
            logger.error(f"Failed to buy {symbol}: {e}")
            return None

    async def sell(self, symbol: str, quantity: int, price: float = None) -> Optional[str]:
        """Place a sell order. Returns order ID if successful.

        Args:
            symbol: The security symbol
            quantity: Number of shares to sell
            price: Limit price (optional). If provided, places a limit order.

        In research mode, returns a simulated order ID without executing.
        """
        if not await self._is_live_mode():
            price_info = f" @ {price}" if price else ""
            logger.debug(f"[RESEARCH MODE] Would sell {quantity} of {symbol}{price_info}")
            return f"RESEARCH-SELL-{symbol}-{quantity}"

        if not self._trading:
            return None
        try:
            kwargs = {"quantity": quantity}
            if price is not None:
                kwargs["price"] = price
            response = self._trading.sell(symbol, **kwargs)
            logger.info(f"Sell {symbol} response: {response}")
            return response.get("order_id") if response else None
        except Exception as e:
            logger.error(f"Failed to sell {symbol}: {e}")
            return None

    async def get_order_status(self, order_id: str) -> Optional[dict]:
        """Get status of an order."""
        if not self._trading:
            return None
        try:
            placed = self._trading.get_placed()
            if placed:
                for order in placed.get("orders", []):
                    if order.get("id") == order_id:
                        return order
            return None
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None

    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------

    async def get_security_info(self, symbol: str) -> Optional[dict]:
        """Get security metadata from Tradernet."""
        if not self._api:
            return None
        try:
            return self._api.security_info(symbol)
        except Exception as e:
            logger.error(f"Failed to get security info for {symbol}: {e}")
            return None

    async def get_market_status(self, market: str = "*") -> Optional[dict]:
        """Get market status from Tradernet.

        Args:
            market: Market code (e.g., 'EU', 'ATHEX', 'HKEX') or '*' for all

        Returns:
            Dict with market statuses including open/close times and current status
        """
        if not self._api:
            return None
        try:
            result = self._api.get_market_status(market)
            return result.get("result", {}).get("markets", {})
        except Exception as e:
            logger.error(f"Failed to get market status: {e}")
            return None

    async def is_market_open(self, market_id: str) -> bool:
        """Check if a specific market is currently open."""
        status = await self.get_market_status(market_id)
        if not status:
            return False

        markets = status.get("m", [])
        for m in markets:
            if m.get("n2") == market_id or str(m.get("mkt_id")) == str(market_id):
                return m.get("s") == "OPEN"
        return False

    async def get_available_securities(self) -> list[str]:
        """
        Get list of top tradeable EU securities from Tradernet API.

        Calls getTopSecurities API for European stocks by trading volume,
        filtered to EU market only.

        Returns:
            List of ticker symbols (e.g., ['ASML.EU', 'SAP.EU', ...])
        """
        try:
            import json

            import requests

            params = {
                "cmd": "getTopSecurities",
                "params": {
                    "type": "stocks",
                    "exchange": "europe",
                    "gainers": 0,  # Top by trading volume
                    "limit": 100,
                },
            }

            response = requests.get("https://tradernet.com/api/", params={"q": json.dumps(params)}, timeout=60)
            data = response.json()

            if "error" in data:
                logger.error(f"API error: {data.get('error')}")
                # Fallback to database
                securities = await self._db.get_all_securities(active_only=True)
                return [s["symbol"] for s in securities]

            tickers = data.get("tickers", [])

            logger.info(f"Found {len(tickers)} securities from Tradernet API")
            return tickers

        except Exception as e:
            logger.error(f"Failed to get available securities: {e}")
            # Fallback to database
            securities = await self._db.get_all_securities(active_only=True)
            return [s["symbol"] for s in securities]
