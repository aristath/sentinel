"""
Broker - Single source of truth for all broker (Tradernet) operations.

Usage:
    broker = Broker()
    await broker.connect()
    quote = await broker.get_quote('AAPL.US')
    await broker.buy('AAPL.US', quantity=10)
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sentinel.database import Database
from sentinel.settings import Settings
from sentinel.utils.decorators import singleton

logger = logging.getLogger(__name__)

# Tradernet's `getAllSecurities` rate-limits at ~30 calls/min and stays in 429
# mode for ~60s once tripped. If we get rate-limited, back off well past the
# window length and try once more — but do not escalate further: the daily
# sync cycle will pick up anything still missing on the next run.
RATE_LIMIT_BACKOFF_S = 60


@singleton
class Broker:
    """Single source of truth for broker operations."""

    _api = None
    _trading = None
    _settings: "Settings"
    _db: "Database"

    def __init__(self):
        self._settings = Settings()
        self._db = Database()

    def _parse_quotes_response(self, response: dict) -> list[dict]:
        """Extract quotes list from API response (handles both response formats)."""
        if not response:
            return []
        if "quotes" in response:
            return response["quotes"]
        if "result" in response and "q" in response["result"]:
            return response["result"]["q"]
        return []

    def _map_quote_fields(self, raw_quote: dict) -> dict:
        """Map raw API quote fields to convenience names."""
        quote = dict(raw_quote)
        quote["symbol"] = raw_quote.get("c")
        quote["price"] = raw_quote.get("ltp")
        quote["bid"] = raw_quote.get("bbp")
        quote["ask"] = raw_quote.get("bap")
        quote["change"] = raw_quote.get("chg")
        quote["change_percent"] = raw_quote.get("pcp")
        return quote

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
            for q in self._parse_quotes_response(response):
                if q.get("c") == symbol:
                    return self._map_quote_fields(q)
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
        return None

    async def get_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """Get quotes for multiple symbols (cached for 5 minutes)."""
        if not self._api:
            logger.warning("get_quotes: API not initialized")
            return {}

        cache_key = "quotes:" + ",".join(sorted(symbols))
        cached = await self._db.cache_get(cache_key)
        if cached is not None:
            logger.info(f"get_quotes: Cache hit for {len(symbols)} symbols")
            return json.loads(cached)

        try:
            logger.info(f"get_quotes: Requesting {len(symbols)} symbols from API")
            response = self._api.get_quotes(symbols)
            result = {}
            quotes_list = self._parse_quotes_response(response)
            if quotes_list:
                logger.info(f"get_quotes: Found {len(quotes_list)} quotes in response")
                for q in quotes_list:
                    if q.get("c"):
                        result[q["c"]] = self._map_quote_fields(q)
            else:
                logger.warning(
                    f"get_quotes: No quotes in response. Keys: {list(response.keys()) if response else None}"
                )

            await self._db.cache_set(cache_key, json.dumps(result), ttl_seconds=300)
            return result
        except Exception as e:
            logger.error(f"Failed to get quotes: {e}")
            return {}

    async def get_user_stock_lists(self) -> dict | None:
        """Get the user's saved ticker lists from TraderNet."""
        if not self._api:
            logger.warning("get_user_stock_lists: API not initialized")
            return None

        try:
            response = self._api.authorized_request("getUserStockLists")
        except Exception as e:
            logger.error(f"Failed to get user stock lists: {e}")
            return None

        if not isinstance(response, dict):
            logger.error(f"Unexpected getUserStockLists response type: {type(response).__name__}")
            return None
        if response.get("errMsg"):
            logger.error(f"TraderNet getUserStockLists error: {response.get('errMsg')} (code={response.get('code')})")
            return None
        if not isinstance(response.get("userStockLists"), list):
            logger.error("TraderNet getUserStockLists response missing userStockLists")
            return None

        return response

    async def get_default_stock_list(self) -> dict | None:
        """Return the broker's default saved ticker list."""
        lists_payload = await self.get_user_stock_lists()
        if not lists_payload:
            return None

        default_id = lists_payload.get("defaultId")
        user_lists = lists_payload.get("userStockLists") or []
        for item in user_lists:
            if isinstance(item, dict) and item.get("id") == default_id:
                return item

        logger.error("TraderNet user stock lists response did not include defaultId=%s", default_id)
        return None

    async def add_stock_list_ticker(self, ticker: str) -> bool:
        """Add a ticker to the default saved ticker list."""
        if not self._api:
            logger.warning("add_stock_list_ticker: API not initialized")
            return False

        stock_list = await self.get_default_stock_list()
        if not stock_list:
            return False

        tickers = stock_list.get("tickers") or []
        if ticker in tickers:
            return True

        list_id = stock_list.get("id")
        if list_id is None:
            logger.error("Cannot add %s to default stock list without list id", ticker)
            return False

        try:
            response = self._api.authorized_request(
                "addStockListTicker",
                {"id": list_id, "ticker": ticker, "index": len(tickers)},
            )
        except Exception as e:
            logger.error(f"Failed to add {ticker} to default stock list: {e}")
            return False

        updated_tickers = self._stock_list_response_tickers(response, list_id)
        return updated_tickers is not None and ticker in updated_tickers

    async def delete_stock_list_ticker(self, ticker: str) -> bool:
        """Remove a ticker from the default saved ticker list."""
        if not self._api:
            logger.warning("delete_stock_list_ticker: API not initialized")
            return False

        stock_list = await self.get_default_stock_list()
        if not stock_list:
            return False

        tickers = stock_list.get("tickers") or []
        if ticker not in tickers:
            return True

        list_id = stock_list.get("id")
        if list_id is None:
            logger.error("Cannot delete %s from default stock list without list id", ticker)
            return False

        try:
            response = self._api.authorized_request("deleteStockListTicker", {"id": list_id, "ticker": ticker})
        except Exception as e:
            logger.error(f"Failed to delete {ticker} from default stock list: {e}")
            return False

        updated_tickers = self._stock_list_response_tickers(response, list_id)
        return updated_tickers is not None and ticker not in updated_tickers

    def _stock_list_response_tickers(self, response: object, list_id: int) -> set[str] | None:
        if not isinstance(response, dict):
            logger.error("Unexpected stock-list mutation response type: %s", type(response).__name__)
            return None
        if response.get("errMsg"):
            logger.error(
                "TraderNet stock-list mutation error: %s (code=%s)",
                response.get("errMsg"),
                response.get("code"),
            )
            return None

        user_lists = response.get("userStockLists")
        if not isinstance(user_lists, list):
            logger.error("TraderNet stock-list mutation response missing userStockLists")
            return None

        for item in user_lists:
            if isinstance(item, dict) and item.get("id") == list_id:
                tickers = item.get("tickers")
                if not isinstance(tickers, list):
                    logger.error("TraderNet stock-list mutation response has invalid tickers")
                    return None
                return {ticker for ticker in tickers if isinstance(ticker, str)}

        logger.error("TraderNet stock-list mutation response missing list id %s", list_id)
        return None

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

    async def get_historical_prices_bulk(
        self,
        symbols: list[str],
        years: int = 20,
        *,
        raise_on_error: bool = False,
    ) -> dict[str, list[dict]]:
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
            response.raise_for_status()
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
            if raise_on_error:
                raise
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
                            "close_price": pos.get("close_price"),
                            "previous_close_price": pos.get("profit_price") or pos.get("close_price"),
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

    async def buy(self, symbol: str, quantity: int, price: float | None = None) -> Optional[str]:
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
            if price is not None:
                response = self._trading.buy(symbol, quantity=quantity, price=price)
            else:
                response = self._trading.buy(symbol, quantity=quantity)
            logger.info(f"Buy {symbol} response: {response}")
            return response.get("order_id") if response else None
        except Exception as e:
            logger.error(f"Failed to buy {symbol}: {e}")
            return None

    async def sell(self, symbol: str, quantity: int, price: float | None = None) -> Optional[str]:
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
            if price is not None:
                response = self._trading.sell(symbol, quantity=quantity, price=price)
            else:
                response = self._trading.sell(symbol, quantity=quantity)
            logger.info(f"Sell {symbol} response: {response}")
            return response.get("order_id") if response else None
        except Exception as e:
            logger.error(f"Failed to sell {symbol}: {e}")
            return None

    async def has_pending_orders(self) -> bool:
        """Return True if the broker has any active (unfilled) orders.

        Used to prevent submitting duplicate orders while previous ones are
        still outstanding. **Fail-safe: any uncertainty returns True**, so the
        trading loop refuses to place new orders rather than risk duplicates.

        Tradernet's ``get_placed(active=True)`` returns
        ``{"result": {"orders": {"order": [...]}}}`` when there are active
        orders, and omits the ``"order"`` key when there are none (see
        ``tradernet.client.Tradernet.cancel_all`` for the canonical access
        pattern). Note that ``authorized_request`` does *not* raise on API
        errors — it just logs them and returns ``{"errMsg": ..., "code": ...}``
        — so we must inspect the payload, not rely on exceptions.
        """
        if not self._trading:
            # Broker not connected. trading_execute already gates on
            # broker.connected upstream, so reaching here means another caller
            # invoked us without a live trading client. We can't query, so
            # fail safe.
            logger.warning("has_pending_orders called without trading client; failing safe")
            return True
        try:
            placed = self._trading.get_placed(active=True)
        except Exception as e:
            logger.error(f"Failed to fetch active orders: {e}")
            return True

        # Defensively validate every level of the response. Any deviation from
        # the documented shape is treated as an error and fails safe.
        if not isinstance(placed, dict):
            logger.error(f"Unexpected get_placed response type: {type(placed).__name__}; failing safe")
            return True
        if "errMsg" in placed:
            logger.error(
                f"Broker returned error from get_placed: {placed.get('errMsg')!r} "
                f"(code={placed.get('code')!r}); failing safe"
            )
            return True

        result = placed.get("result")
        if not isinstance(result, dict):
            logger.error("get_placed response missing 'result' dict; failing safe")
            return True

        orders = result.get("orders")
        if not isinstance(orders, dict):
            logger.error("get_placed response missing 'result.orders' dict; failing safe")
            return True

        order_field = orders.get("order")
        if order_field is None:
            return False
        # The API normally returns a list. Defensively treat a single-order
        # dict as "pending" too. Any other type is unexpected -> fail safe.
        if isinstance(order_field, dict):
            return True
        if isinstance(order_field, list):
            return len(order_field) > 0
        logger.error(f"Unexpected get_placed 'order' field type: {type(order_field).__name__}; failing safe")
        return True

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

    async def get_security_metadata(self, symbol: str) -> Optional[dict]:
        """Fetch country-of-risk and TRBC industry for one ticker from `getAllSecurities`.

        `getSecurityInfo` returns a thin payload (market, lot, currency). The richer
        `getAllSecurities` endpoint exposes `attributes.CntryOfRisk` (ISO-2 country
        where the issuer's economic risk lives — distinct from the listing venue or
        registration country, which Tradernet leaves as `"0"`) and `sector_code`
        (Refinitiv/LSEG TRBC industry name as a free-text string).

        Returns the normalized fields the sync job needs, or `None` when the broker
        is offline, the ticker is unknown, or the call fails. On HTTP 429 we sleep
        once and retry; if the second attempt is also rate-limited we give up and
        rely on the next sync cycle.
        """
        if not self._api:
            return None

        payload = {
            "take": 1,
            "skip": 0,
            "filter": {"filters": [{"field": "ticker", "operator": "eq", "value": symbol}]},
        }
        response = None
        for attempt in (1, 2):
            try:
                response = self._api.authorized_request("getAllSecurities", payload)
                break
            except Exception as e:
                rate_limited = "429" in str(e)
                if rate_limited and attempt == 1:
                    logger.warning(
                        f"Rate-limited fetching metadata for {symbol}; backing off {RATE_LIMIT_BACKOFF_S}s",
                    )
                    await asyncio.sleep(RATE_LIMIT_BACKOFF_S)
                    continue
                logger.error(f"Failed to get security metadata for {symbol}: {e}")
                return None

        if response is None:
            return None

        rows = (response or {}).get("securities") or []
        if not rows:
            return None

        row = rows[0]
        attrs = row.get("attributes")
        # The SDK parses attributes to a dict; the raw HTTP call returns a JSON
        # string. Anything else (None, list, ...) is treated as missing — we
        # never want a malformed shape from upstream to crash the sync loop.
        if isinstance(attrs, str):
            try:
                attrs = json.loads(attrs)
            except (json.JSONDecodeError, TypeError):
                attrs = {}
        if not isinstance(attrs, dict):
            attrs = {}

        return {
            # `or ""` collapses None and Tradernet's "0" / 0 "unclassified"
            # sentinel to a blank string — the same signal we use for ETFs.
            "geography": str(attrs.get("CntryOfRisk") or ""),
            "industry": str(row.get("sector_code") or ""),
            "instr_kind_c": row.get("instr_kind_c"),
            "mkt_short_code": row.get("mkt_short_code"),
            "name": row.get("name"),
        }

    async def get_all_indices(self) -> Optional[list[dict]]:
        """Return Tradernet's full universe of market indices.

        Calls `getAllSecurities` filtered to `instr_type_c == 5` (Tradernet's
        "Indices" type) and paginates until the reported `total` is exhausted.
        Returns a list of normalized dicts with `symbol`, `name`,
        `mkt_short_code`, `instr_kind_c`, `currency` — the fields the
        `benchmarks` table stores.

        Returns `None` if the broker is offline or the call fails outright.
        Per-page 429s are recovered with the same one-shot back-off used by
        `get_security_metadata`.
        """
        if not self._api:
            return None

        results: list[dict] = []
        skip = 0
        page_size = 50
        seen_total: int | None = None

        while True:
            payload = {
                "take": page_size,
                "skip": skip,
                "filter": {"filters": [{"field": "instr_type_c", "operator": "eq", "value": 5}]},
            }
            response = None
            for attempt in (1, 2):
                try:
                    response = self._api.authorized_request("getAllSecurities", payload)
                    break
                except Exception as e:
                    rate_limited = "429" in str(e)
                    if rate_limited and attempt == 1:
                        logger.warning(
                            f"Rate-limited fetching indices page (skip={skip}); backing off {RATE_LIMIT_BACKOFF_S}s",
                        )
                        await asyncio.sleep(RATE_LIMIT_BACKOFF_S)
                        continue
                    logger.error(f"Failed to fetch indices page (skip={skip}): {e}")
                    return None

            if not isinstance(response, dict):
                return None

            rows = response.get("securities") or []
            for row in rows:
                ticker = row.get("ticker")
                if not ticker:
                    continue
                results.append(
                    {
                        "symbol": ticker,
                        "name": row.get("name") or row.get("latname") or ticker,
                        "mkt_short_code": row.get("mkt_short_code"),
                        "instr_kind_c": row.get("instr_kind_c"),
                        "currency": row.get("face_curr_c"),
                    }
                )

            if seen_total is None:
                seen_total = int(response.get("total") or 0)

            skip += len(rows)
            # Stop when this page returned nothing OR we've drained the total.
            if not rows or skip >= seen_total:
                break

        return results

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

    async def get_trades_history(
        self,
        start_date: str = "2020-01-01",
        end_date: str | None = None,
    ) -> list[dict]:
        """
        Fetch trade history from Tradernet API.

        Args:
            start_date: Start date in YYYY-MM-DD format (default: 2020-01-01)
            end_date: End date in YYYY-MM-DD format (default: today)

        Returns:
            List of trade dicts with extracted symbol and side fields
        """
        if not self._api:
            return []

        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        try:
            response = self._api.get_trades_history(
                start=start_date,
                end=end_date,
                limit=1000,  # Fetch all available trades
            )

            trades = []
            if response and "trades" in response:
                # API returns {"trades": {"trade": [...], "max_trade_id": [...]}}
                raw_trades = response.get("trades", {}).get("trade", [])

                for trade in raw_trades:
                    # Extract key fields for indexing
                    symbol = trade.get("instr_nm", "")
                    trade_type = str(trade.get("type", ""))  # API returns "1" = BUY, "2" = SELL as strings
                    side = "BUY" if trade_type == "1" else "SELL"

                    # Add convenience fields to the trade dict
                    trade["symbol"] = symbol
                    trade["side"] = side

                    trades.append(trade)

            logger.info(f"Fetched {len(trades)} trades from Tradernet API")
            return trades

        except Exception as e:
            logger.error(f"Failed to get trades history: {e}")
            return []

    async def get_cash_flows(
        self,
        start_date: str = "2020-01-01",
        end_date: str | None = None,
    ) -> list[dict]:
        """
        Fetch cash flow history (deposits, withdrawals, dividends, taxes) from Tradernet API.

        Args:
            start_date: Start date in YYYY-MM-DD format (default: 2020-01-01)
            end_date: End date in YYYY-MM-DD format (default: today)

        Returns:
            List of cash flow entries with type_id: card, card_payout, dividend, tax, block, unblock
        """
        if not self._api:
            return []

        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        try:
            response = self._api.get_broker_report(
                start=start_date,
                end=end_date,
                data_block_type="in_outs",
            )

            cash_flows = []
            if response and "report" in response:
                detailed = response.get("report", {}).get("detailed", [])
                cash_flows = detailed

            logger.info(f"Fetched {len(cash_flows)} cash flow entries from Tradernet API")
            return cash_flows

        except Exception as e:
            logger.error(f"Failed to get cash flows: {e}")
            return []

    async def get_corporate_actions(
        self,
        start_date: str = "2020-01-01",
        end_date: str | None = None,
    ) -> list[dict]:
        """
        Fetch corporate actions (dividends, maturities, etc.) from Tradernet API.

        Args:
            start_date: Start date in YYYY-MM-DD format (default: 2020-01-01)
            end_date: End date in YYYY-MM-DD format (default: today)

        Returns:
            List of corporate action entries from the broker report
        """
        if not self._api:
            return []

        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        try:
            response = self._api.get_broker_report(
                start=start_date,
                end=end_date,
                data_block_type="corporate_actions",
            )

            actions = []
            if response and "report" in response:
                detailed = response.get("report", {}).get("detailed", [])
                actions = detailed

            logger.info(f"Fetched {len(actions)} corporate actions from Tradernet API")
            return actions

        except Exception as e:
            logger.error(f"Failed to get corporate actions: {e}")
            return []

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
