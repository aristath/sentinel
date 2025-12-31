"""Tradernet API client implementation."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from tradernet import TraderNetAPI

from app.config import settings
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.infrastructure.external.tradernet.models import (
    OHLC,
    CashBalance,
    OrderResult,
    Position,
    Quote,
)
from app.infrastructure.external.tradernet.parsers import (
    create_order_result,
    create_research_mode_order,
    get_trading_mode,
    parse_candles_format,
    parse_candles_list,
    parse_hloc_format,
    parse_price_data_string,
)
from app.infrastructure.external.tradernet.transactions import (
    get_corporate_action_transactions,
    get_cps_history_transactions,
    get_trade_fee_transactions,
    parse_withdrawal_record,
)
from app.infrastructure.external.tradernet.utils import (
    get_exchange_rate_sync,
    led_api_call,
    set_exchange_rate_service,
)
from app.shared.domain.value_objects.currency import Currency

logger = logging.getLogger(__name__)


class TradernetClient:
    """Client for Tradernet/Freedom24 API."""

    def __init__(self, exchange_rate_service: Optional[ExchangeRateService] = None):
        """Initialize the Tradernet client.

        Args:
            exchange_rate_service: Optional ExchangeRateService for currency conversions.
                                  If provided, sets global service for sync helper functions.
        """
        self._client: Optional[TraderNetAPI] = None
        self._connected = False
        self._exchange_rate_service = exchange_rate_service

        # Set global service for sync helper functions
        if exchange_rate_service is not None:
            set_exchange_rate_service(exchange_rate_service)

    def connect(self) -> bool:
        """Connect to Tradernet API."""
        if not settings.tradernet_api_key or not settings.tradernet_api_secret:
            logger.warning("Tradernet API credentials not configured")
            return False

        try:
            client = TraderNetAPI(
                settings.tradernet_api_key, settings.tradernet_api_secret
            )
            # Test connection by fetching user info
            client.user_info()
            self._client = client
            self._connected = True
            logger.info("Connected to Tradernet API")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Tradernet: {e}")
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected and self._client is not None

    @classmethod
    def shared(cls) -> "TradernetClient":
        """Get the shared singleton instance."""
        from app.infrastructure.external.tradernet.client import get_tradernet_client

        return get_tradernet_client()

    def get_account_summary(self) -> dict:
        """Get full account summary including positions and cash."""
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with led_api_call():
                return self._client.account_summary()
        except Exception as e:
            logger.error(f"Failed to get account summary: {e}")
            return {}

    def get_portfolio(self) -> list[Position]:
        """Get current portfolio positions."""
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with led_api_call():
                summary = self._client.account_summary()
            positions = []

            # Parse positions from result.ps.pos
            ps_data = summary.get("result", {}).get("ps", {})
            pos_data = ps_data.get("pos", [])

            for item in pos_data:
                avg_price = float(item.get("bal_price_a", 0))
                current_price = float(item.get("mkt_price", 0))
                quantity = float(item.get("q", 0))
                # Calculate market_value ourselves - don't trust API's market_value
                # (Tradernet sometimes returns wrong values, e.g., ETF's AUM instead of position value)
                market_value = quantity * current_price
                currency = item.get("curr", Currency.EUR)

                # Get real-time exchange rate instead of API's currval
                currency_rate = get_exchange_rate_sync(currency, Currency.EUR)

                # Convert market_value to default currency (EUR)
                if currency == Currency.EUR:
                    market_value_eur = market_value
                else:
                    market_value_eur = (
                        market_value / currency_rate
                        if currency_rate > 0
                        else market_value
                    )

                positions.append(
                    Position(
                        symbol=item.get("i", ""),
                        quantity=quantity,
                        avg_price=avg_price,
                        current_price=current_price,
                        market_value=market_value,
                        market_value_eur=market_value_eur,
                        unrealized_pnl=float(item.get("profit_close", 0)),
                        currency=currency,
                        currency_rate=currency_rate,
                    )
                )

            return positions
        except Exception as e:
            logger.error(f"Failed to get portfolio: {e}")
            return []

    def get_cash_balances(self) -> list[CashBalance]:
        """Get cash balances in all currencies (including negative and zero balances)."""
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with led_api_call():
                summary = self._client.account_summary()
            balances = []

            # Parse cash from result.ps.acc
            ps_data = summary.get("result", {}).get("ps", {})
            acc_data = ps_data.get("acc", [])

            for item in acc_data:
                amount = float(item.get("s", 0))
                currency = item.get("curr", "")

                # Include ALL balances (positive, negative, zero)
                balances.append(
                    CashBalance(
                        currency=currency,
                        amount=amount,
                    )
                )

                # Log warning if negative balance detected
                if amount < 0:
                    logger.warning(
                        f"Negative cash balance detected: {amount:.2f} {currency}"
                    )

            return balances
        except Exception as e:
            logger.error(f"Failed to get cash balances: {e}")
            return []

    def get_total_portfolio_value_eur(self) -> float:
        """Get total portfolio value (positions + cash) in EUR."""
        positions = self.get_portfolio()
        cash = self.get_total_cash_eur()
        total_positions = sum(p.market_value_eur for p in positions)
        return total_positions + cash

    def get_total_cash_eur(self) -> float:
        """Get total cash balance converted to EUR (including negative balances)."""
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with led_api_call():
                summary = self._client.account_summary()
            total = 0.0

            # Parse cash from result.ps.acc
            ps_data = summary.get("result", {}).get("ps", {})
            acc_data = ps_data.get("acc", [])

            for item in acc_data:
                amount = float(item.get("s", 0))
                currency = item.get("curr", Currency.EUR)

                if currency == Currency.EUR:
                    # Include ALL EUR balances (positive, negative, zero)
                    total += amount
                else:
                    # Include ALL balances (positive, negative, zero) - convert to EUR
                    rate = get_exchange_rate_sync(currency, Currency.EUR)
                    if rate > 0:
                        total += amount / rate

            return total
        except Exception as e:
            logger.error(f"Failed to get total cash: {e}")
            return 0.0

    def get_quote(self, symbol: str) -> Optional[Quote]:
        """Get current quote for a symbol."""
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with led_api_call():
                quotes = self._client.get_quotes([symbol])
            if quotes and len(quotes) > 0:
                # quotes can be list or dict depending on API response
                data = quotes[0] if isinstance(quotes, list) else quotes  # type: ignore[index]
                return Quote(
                    symbol=symbol,
                    price=float(data.get("ltp", data.get("last_price", 0))),
                    change=float(data.get("chg", data.get("change", 0))),
                    change_pct=float(data.get("chg_pc", data.get("change_pct", 0))),
                    volume=int(data.get("v", data.get("volume", 0))),
                    timestamp=datetime.now(),
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            return None

    def get_quotes_raw(self, symbols: list[str]) -> dict:
        """
        Get raw quote data for multiple symbols.

        Returns the raw API response including x_curr (trading currency).
        Useful for syncing currency information.
        """
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with led_api_call():
                return self._client.get_quotes(symbols)
        except Exception as e:
            logger.error(f"Failed to get raw quotes: {e}")
            return {}

    def find_symbol(self, symbol: str, exchange: Optional[str] = None) -> dict:
        """
        Search for stock symbols/instruments by symbol or ISIN.

        This method accepts both Tradernet symbols and ISINs.
        Useful for resolving ISINs to Tradernet symbols.

        Args:
            symbol: Symbol name or ISIN to search for (e.g., "AAPL", "US0378331005")
            exchange: Optional exchange filter (refbook name)

        Returns:
            Dict with 'found' key containing list of matching instruments.
            Each instrument has: 't' (symbol), 'nm' (name), 'x_curr' (currency),
            'isin', 'mkt' (market), 'codesub' (exchange code), etc.
        """
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with led_api_call():
                return self._client.find_symbol(symbol, exchange=exchange)
        except Exception as e:
            logger.error(f"Failed to find symbol {symbol}: {e}")
            return {}

    def get_pending_orders(self) -> list[dict]:
        """
        Get all pending/active orders from Tradernet.

        Returns list of order dicts with keys: id, symbol, side, quantity, price, currency
        """
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with led_api_call():
                response = self._client.get_placed(active=True)

            orders_data = response.get("result", {}).get("orders", {})
            order_list = orders_data.get("order", [])

            # Handle single order (not in list) vs multiple orders
            if isinstance(order_list, dict):
                order_list = [order_list]

            pending = []
            for order in order_list:
                pending.append(
                    {
                        "id": order.get("id"),
                        "symbol": order.get("instr_name"),
                        "side": order.get("buy_sell"),  # "buy" or "sell"
                        "quantity": float(order.get("qty", 0)),
                        "price": float(order.get("price", 0)),
                        "currency": order.get("curr"),
                    }
                )

            return pending
        except Exception as e:
            logger.error(f"Failed to get pending orders: {e}")
            return []

    def get_pending_order_totals(self) -> dict[str, float]:
        """
        Get total value of pending BUY orders grouped by currency.

        Returns dict like: {"EUR": 500.0, "USD": 200.0}
        """
        pending = self.get_pending_orders()
        totals: dict[str, float] = {}

        for order in pending:
            if order["side"] and order["side"].lower() == "buy":
                currency = order["currency"] or "EUR"
                value = order["quantity"] * order["price"]
                totals[currency] = totals.get(currency, 0) + value

        return totals

    def has_pending_order_for_symbol(self, symbol: str) -> bool:
        """
        Check if a pending order exists for the given symbol (broker API only).

        Args:
            symbol: Stock symbol to check (e.g., "AAPL.US")

        Returns:
            True if any pending order exists for this symbol (regardless of side)
        """
        pending = self.get_pending_orders()
        for order in pending:
            if order["symbol"] == symbol:
                return True
        return False

    def get_historical_prices(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        days: Optional[int] = None,  # Backward compatibility
    ) -> list[OHLC]:
        """
        Get historical OHLC data for a symbol.

        Args:
            symbol: Stock symbol
            start: Start date (defaults to 2010-01-01 if not provided)
            end: End date (defaults to now if not provided)
            days: Optional backward compatibility - calculates start date from days ago
        """
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        # Handle backward compatibility with days parameter
        if days is not None:
            end = datetime.now()
            start = end - timedelta(days=days)
        else:
            # Default to 2010-01-01 if start not provided
            if start is None:
                start = datetime(2010, 1, 1)
            if end is None:
                end = datetime.now()

        try:
            with led_api_call():
                data = self._client.get_candles(symbol, start=start, end=end)
            result = []

            # Debug: log what we received
            logger.info(
                f"get_candles response for {symbol}: type={type(data)}, value={str(data)[:200] if data else 'None'}"
            )

            data = parse_price_data_string(data, symbol)
            if isinstance(data, dict):
                result = parse_hloc_format(data, symbol, start) or parse_candles_format(
                    data
                )
            elif isinstance(data, list):
                result = parse_candles_list(data)

            return result
        except Exception as e:
            logger.error(f"Failed to get historical prices for {symbol}: {e}")
            return []

    def get_security_info(self, symbol: str) -> Optional[dict]:
        """
        Get security info including lot size from Tradernet API.

        Args:
            symbol: Stock symbol (e.g., "XIAO.1810.AS")

        Returns:
            Dict with security info including 'lot' (minimum lot size) if available,
            None if the request fails.
        """
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with led_api_call():
                info = self._client.security_info(symbol)
            return info
        except Exception as e:
            logger.warning(f"Failed to get security info for {symbol}: {e}")
            return None

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> Optional[OrderResult]:
        """
        Place an order.

        Args:
            symbol: Stock symbol (e.g., "AAPL.US")
            side: "BUY" or "SELL"
            quantity: Number of shares
            order_type: "market" or "limit"
            limit_price: Price for limit orders

        Returns:
            OrderResult if successful, None otherwise
        """
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        trading_mode = get_trading_mode()
        if trading_mode == "research":
            return create_research_mode_order(symbol, side, quantity, self)

        try:
            # Convert quantity to int as Tradernet API expects int
            quantity_int = int(quantity)
            if side.upper() == "BUY":
                result = self._client.buy(symbol, quantity_int)  # type: ignore[arg-type]
            elif side.upper() == "SELL":
                result = self._client.sell(symbol, quantity_int)  # type: ignore[arg-type]
            else:
                raise ValueError(f"Invalid side: {side}")

            return create_order_result(result, symbol, side, quantity)
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            # Tradernet API expects int, but we use str internally
            # Try to convert, or pass as-is if conversion fails
            try:
                order_id_int = int(order_id)
                self._client.cancel(order_id_int)  # type: ignore[arg-type]
            except (ValueError, TypeError):
                # If conversion fails, try passing as string (some APIs accept both)
                self._client.cancel(order_id)  # type: ignore[arg-type]
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def _parse_trade_side(self, trade_type) -> str:
        """Parse trade side from type field (1=BUY, 2=SELL)."""
        if trade_type == "1" or trade_type == 1:
            return "BUY"
        elif trade_type == "2" or trade_type == 2:
            return "SELL"
        return ""

    def _parse_trade(self, trade: dict) -> Optional[dict]:
        """Parse a single trade dict from Tradernet response."""
        try:
            order_id = str(trade.get("id") or trade.get("order_id") or "")
            if not order_id:
                return None

            qty_str = trade.get("q") or trade.get("qty") or "0"
            quantity = float(qty_str) if qty_str else 0

            price_str = trade.get("price") or trade.get("p") or "0"
            price = float(price_str) if price_str else 0

            trade_date = trade.get("date") or trade.get("d") or ""
            trade_type = trade.get("type") or ""
            side = self._parse_trade_side(trade_type)

            return {
                "order_id": order_id,
                "symbol": trade.get("instr_nm") or trade.get("i") or "",
                "side": side,
                "quantity": quantity,
                "price": price,
                "executed_at": trade_date,
            }
        except Exception as e:
            logger.warning(f"Failed to parse trade: {e}")
            return None

    def get_executed_trades(self, limit: int = 500) -> list[dict]:
        """
        Get executed trades from Tradernet.

        Returns list of trade dicts with: order_id, symbol, side, quantity, price, executed_at
        """
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with led_api_call():
                trades_data = self._client.get_trades_history()

            trade_list = trades_data.get("trades", {}).get("trade", [])
            if isinstance(trade_list, dict):
                trade_list = [trade_list]

            executed = []
            for trade in trade_list[:limit]:
                parsed = self._parse_trade(trade)
                if parsed:
                    executed.append(parsed)

            logger.info(f"Fetched {len(executed)} executed trades from Tradernet")
            return executed
        except Exception as e:
            logger.error(f"Failed to get executed trades: {e}")
            return []

    def get_cash_movements(self) -> dict:
        """
        Get withdrawal history from account.

        Note: The Tradernet API only returns withdrawal records (type_doc_id=337).
        Deposits are NOT available via API and must be tracked manually.

        Returns dict with:
        - total_withdrawals: Sum of all completed withdrawals in EUR
        - withdrawals: List of individual withdrawal transactions
        """
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with led_api_call():
                # Get client history - only withdrawals (337) are returned
                history = self._client.authorized_request(
                    "getClientCpsHistory", {"limit": 500}, version=2
                )

            total_withdrawals = 0.0
            withdrawals = []

            # Parse the response - it's a list of transactions
            records = history if isinstance(history, list) else []

            for record in records:
                withdrawal = parse_withdrawal_record(record)
                if withdrawal:
                    total_withdrawals += withdrawal["amount_eur"]
                    withdrawals.append(withdrawal)

            return {
                "total_withdrawals": round(total_withdrawals, 2),
                "withdrawals": withdrawals,
            }
        except Exception as e:
            logger.error(f"Failed to get cash movements: {e}")
            return {
                "total_withdrawals": 0,
                "withdrawals": [],
                "error": str(e),
            }

    def get_all_cash_flows(self, limit: int = 1000) -> list[dict]:
        """
        Get all cash flow transactions from account history.

        Returns all transaction types from multiple sources:
        - getClientCpsHistory: Withdrawals, structured product purchases, etc.
        - corporate_actions: Dividends, coupons, maturities
        - get_trades_history: Trading fees/commissions

        Args:
            limit: Maximum number of records to retrieve per source (default: 1000)

        Returns:
            List of transaction dictionaries with normalized fields:
            - transaction_id: Unique transaction identifier
            - type_doc_id: Transaction type identifier from API (or 'dividend', 'coupon', 'fee', etc.)
            - transaction_type: Human-readable type
            - date: Transaction date (YYYY-MM-DD)
            - amount: Transaction amount in original currency
            - currency: Original currency code
            - amount_eur: Amount converted to EUR
            - status: Transaction status
            - status_c: Status code from API (if applicable)
            - description: Transaction description
            - params: Full params dictionary
        """
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        all_transactions = []

        try:
            all_transactions.extend(get_cps_history_transactions(self._client, limit))
            all_transactions.extend(get_corporate_action_transactions(self._client))
            all_transactions.extend(get_trade_fee_transactions(self._client))
            return all_transactions
        except Exception as e:
            logger.error(f"Failed to get all cash flows: {e}")
            return []

    def get_most_traded(
        self,
        instrument_type: str = "stock",
        exchange: Optional[str] = None,
        gainers: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        """
        Get most traded or fastest-growing securities.

        Args:
            instrument_type: Type of instrument ("stock", "etf", etc.)
            exchange: Exchange filter (e.g., "usa", "europe", "asia")
            gainers: If True, get fastest-growing; if False, get most traded
            limit: Maximum number of results

        Returns:
            List of security dictionaries with symbol, exchange, volume, name, country
        """
        if not self.is_connected or self._client is None:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with led_api_call():
                # Call underlying SDK method if available
                # Note: This may need to be adjusted based on actual SDK method signature
                if hasattr(self._client, "get_most_traded"):
                    kwargs: dict = {
                        "instrument_type": instrument_type,
                        "gainers": gainers,
                        "limit": limit,
                    }
                    if exchange is not None:
                        kwargs["exchange"] = exchange
                    logger.debug(f"Calling get_most_traded with parameters: {kwargs}")
                    result = self._client.get_most_traded(**kwargs)
                else:
                    # Fallback: return empty list if method not available
                    logger.warning("get_most_traded not available in Tradernet SDK")
                    return []

            # Normalize response to expected format
            if isinstance(result, list):
                logger.debug(f"get_most_traded returned list with {len(result)} items")
                return result
            elif isinstance(result, dict):
                # Try common response keys
                if "tickers" in result:
                    # API returns tickers as a list of symbol strings
                    tickers = result["tickers"]
                    if isinstance(tickers, list):
                        logger.debug(
                            f"get_most_traded returned dict with 'tickers' key: {len(tickers)} items"
                        )
                        # Convert ticker strings to dict format expected by discovery service
                        # Each ticker is a string like "FRHC.US", "TSLA.US", etc.
                        securities = []
                        for ticker in tickers:
                            if isinstance(ticker, str):
                                # Parse ticker format: "SYMBOL.EXCHANGE" or just "SYMBOL"
                                parts = ticker.split(".")
                                symbol = parts[0].upper()
                                exchange_code = (
                                    parts[1].lower() if len(parts) > 1 else "unknown"
                                )
                                # Map exchange codes to full exchange names
                                # "US" -> "usa", "EU" -> "europe", etc.
                                exchange_map = {
                                    "us": "usa",
                                    "eu": "europe",
                                    "uk": "ukraine",  # Tradernet uses "ukraine" for UK
                                }
                                exchange = exchange_map.get(
                                    exchange_code, exchange_code
                                )
                                securities.append(
                                    {
                                        "symbol": symbol,
                                        "exchange": exchange,
                                        "ticker": ticker,
                                    }
                                )
                            elif isinstance(ticker, dict):
                                # Already in dict format
                                securities.append(ticker)
                        logger.debug(
                            f"Converted {len(tickers)} tickers to {len(securities)} securities"
                        )
                        return securities
                    else:
                        logger.warning(
                            f"get_most_traded 'tickers' key is not a list: {type(tickers)}"
                        )
                        return []
                elif "result" in result:
                    data = result["result"]
                    if isinstance(data, list):
                        logger.debug(
                            f"get_most_traded returned dict with 'result' key: {len(data)} items"
                        )
                        return data
                    else:
                        logger.warning(
                            f"get_most_traded 'result' key is not a list: {type(data)}"
                        )
                        return []
                elif "data" in result:
                    data = result["data"]
                    if isinstance(data, list):
                        logger.debug(
                            f"get_most_traded returned dict with 'data' key: {len(data)} items"
                        )
                        return data
                    else:
                        logger.warning(
                            f"get_most_traded 'data' key is not a list: {type(data)}"
                        )
                        return []
                elif "securities" in result:
                    data = result["securities"]
                    if isinstance(data, list):
                        logger.debug(
                            f"get_most_traded returned dict with 'securities' key: {len(data)} items"
                        )
                        return data
                    else:
                        logger.warning(
                            f"get_most_traded 'securities' key is not a list: {type(data)}"
                        )
                        return []
                else:
                    # Check if this is an error response
                    if "error" in result or "errMsg" in result:
                        error_msg = result.get(
                            "errMsg", result.get("error", "Unknown error")
                        )
                        error_code = result.get("code", "unknown")
                        logger.error(
                            f"Tradernet API error in get_most_traded: {error_msg} (code: {error_code})"
                        )
                        logger.info(
                            f"Parameters used: instrument_type={instrument_type}, "
                            f"exchange={exchange}, gainers={gainers}, limit={limit}"
                        )
                        return []

                    # Log the actual structure for debugging
                    logger.warning(
                        f"Unexpected get_most_traded response format: dict with keys {list(result.keys())}"
                    )
                    # Log first 500 chars of the response to help debug
                    import json

                    try:
                        response_str = json.dumps(result, default=str, indent=2)[:500]
                        logger.info(
                            f"Response structure (first 500 chars): {response_str}"
                        )
                    except Exception:
                        logger.info(
                            f"Response (repr, first 500 chars): {repr(result)[:500]}"
                        )
                    return []
            else:
                logger.warning(
                    f"Unexpected get_most_traded response format: {type(result)}"
                )
                return []
        except Exception as e:
            logger.error(f"Failed to get most traded securities: {e}")
            return []


# Singleton instance
_client: Optional[TradernetClient] = None


def get_tradernet_client(
    exchange_rate_service: Optional[ExchangeRateService] = None,
) -> TradernetClient:
    """Get or create the Tradernet client singleton.

    Args:
        exchange_rate_service: Optional ExchangeRateService for currency conversions.
                             If provided and client doesn't exist, will be passed to new client.
    """
    global _client
    if _client is None:
        _client = TradernetClient(exchange_rate_service=exchange_rate_service)
    elif exchange_rate_service is not None and _client._exchange_rate_service is None:
        # Update existing client with service if not already set
        _client._exchange_rate_service = exchange_rate_service
        set_exchange_rate_service(exchange_rate_service)
    return _client
