"""Tradernet (Freedom24) API client service."""

import hashlib
import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import requests
from tradernet import TraderNetAPI

from app.config import settings
from app.infrastructure.events import SystemEvent, emit

# Alias for backward compatibility
Tradernet = TraderNetAPI

logger = logging.getLogger(__name__)


@contextmanager
def _led_api_call():
    """Context manager to emit events during API calls for LED indication."""
    emit(SystemEvent.API_CALL_START)
    try:
        yield
    finally:
        emit(SystemEvent.API_CALL_END)


# Cache for exchange rates (refreshed every hour)
_exchange_rates: dict[str, float] = {}
_rates_updated: Optional[datetime] = None
_rates_lock = threading.Lock()


def get_exchange_rate(from_currency: str, to_currency: str = None) -> float:
    """Get exchange rate from currency to target currency using real-time data (thread-safe)."""
    from app.domain.value_objects.currency import Currency

    global _exchange_rates, _rates_updated

    if to_currency is None:
        to_currency = Currency.EUR

    if from_currency == to_currency:
        return 1.0

    with _rates_lock:
        # Check if cache is valid (less than 1 hour old)
        if _rates_updated and datetime.now() - _rates_updated < timedelta(hours=1):
            cache_key = f"{from_currency}_{to_currency}"
            if cache_key in _exchange_rates:
                return _exchange_rates[cache_key]

        # Fetch fresh rates
        try:
            # Use exchangerate-api (free tier)
            url = f"https://api.exchangerate-api.com/v4/latest/{to_currency}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                rates = data.get("rates", {})

                # Update cache with all rates
                _exchange_rates = {}
                for curr, rate in rates.items():
                    # Store as "how many units of curr per 1 EUR"
                    _exchange_rates[f"{curr}_{to_currency}"] = rate
                _rates_updated = datetime.now()

                cache_key = f"{from_currency}_{to_currency}"
                if cache_key in _exchange_rates:
                    return _exchange_rates[cache_key]
        except Exception as e:
            logger.warning(f"Failed to fetch exchange rates: {e}")

        # Fallback rates if API fails
        fallback_rates = {
            "HKD_EUR": 8.5,  # ~8.5 HKD per EUR
            "USD_EUR": 1.05,  # ~1.05 USD per EUR
            "GBP_EUR": 0.85,  # ~0.85 GBP per EUR
        }
        return fallback_rates.get(f"{from_currency}_{to_currency}", 1.0)


@dataclass
class Position:
    """Portfolio position."""

    symbol: str
    name: str
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    market_value_eur: float  # Market value converted to EUR
    unrealized_pnl: float
    currency: str
    currency_rate: float  # Exchange rate to EUR (1.0 for EUR positions)


@dataclass
class CashBalance:
    """Cash balance in a currency."""

    currency: str
    amount: float


@dataclass
class Quote:
    """Stock quote data."""

    symbol: str
    price: float
    change: float
    change_pct: float
    volume: int
    timestamp: datetime


@dataclass
class OHLC:
    """OHLC candle data."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class OrderResult:
    """Order execution result."""

    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    status: str


class TradernetClient:
    """Client for Tradernet/Freedom24 API."""

    def __init__(self):
        """Initialize the Tradernet client."""
        self._client: Optional[Tradernet] = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to Tradernet API."""
        if not settings.tradernet_api_key or not settings.tradernet_api_secret:
            logger.warning("Tradernet API credentials not configured")
            return False

        try:
            self._client = Tradernet(
                settings.tradernet_api_key, settings.tradernet_api_secret
            )
            # Test connection by fetching user info
            self._client.user_info()
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

    def get_account_summary(self) -> dict:
        """Get full account summary including positions and cash."""
        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with _led_api_call():
                return self._client.account_summary()
        except Exception as e:
            logger.error(f"Failed to get account summary: {e}")
            return {}

    def get_portfolio(self) -> list[Position]:
        """Get current portfolio positions."""
        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with _led_api_call():
                summary = self._client.account_summary()
            positions = []

            # Parse positions from result.ps.pos
            ps_data = summary.get("result", {}).get("ps", {})
            pos_data = ps_data.get("pos", [])

            from app.domain.value_objects.currency import Currency

            for item in pos_data:
                avg_price = float(item.get("bal_price_a", 0))
                current_price = float(item.get("mkt_price", 0))
                quantity = float(item.get("q", 0))
                # Calculate market_value ourselves - don't trust API's market_value
                # (Tradernet sometimes returns wrong values, e.g., ETF's AUM instead of position value)
                market_value = quantity * current_price
                currency = item.get("curr", Currency.EUR)

                # Get real-time exchange rate instead of API's currval
                currency_rate = get_exchange_rate(currency, Currency.EUR)

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
                        name=item.get("name", item.get("name2", "")),
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
        """Get cash balances in all currencies."""
        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with _led_api_call():
                summary = self._client.account_summary()
            balances = []

            # Parse cash from result.ps.acc
            ps_data = summary.get("result", {}).get("ps", {})
            acc_data = ps_data.get("acc", [])

            for item in acc_data:
                amount = float(item.get("s", 0))
                if amount > 0:  # Only include non-zero balances
                    balances.append(
                        CashBalance(
                            currency=item.get("curr", ""),
                            amount=amount,
                        )
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
        """Get total cash balance converted to EUR."""
        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with _led_api_call():
                summary = self._client.account_summary()
            total = 0.0

            # Parse cash from result.ps.acc
            ps_data = summary.get("result", {}).get("ps", {})
            acc_data = ps_data.get("acc", [])

            from app.domain.value_objects.currency import Currency

            for item in acc_data:
                amount = float(item.get("s", 0))
                currency = item.get("curr", Currency.EUR)

                if currency == Currency.EUR:
                    total += amount
                elif amount > 0:
                    # Convert to EUR using real-time exchange rate
                    rate = get_exchange_rate(currency, Currency.EUR)
                    total += amount / rate

            return total
        except Exception as e:
            logger.error(f"Failed to get total cash: {e}")
            return 0.0

    def get_quote(self, symbol: str) -> Optional[Quote]:
        """Get current quote for a symbol."""
        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with _led_api_call():
                quotes = self._client.get_quotes([symbol])
            if quotes and len(quotes) > 0:
                data = quotes[0] if isinstance(quotes, list) else quotes
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
        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with _led_api_call():
                return self._client.get_quotes(symbols)
        except Exception as e:
            logger.error(f"Failed to get raw quotes: {e}")
            return {}

    def get_pending_orders(self) -> list[dict]:
        """
        Get all pending/active orders from Tradernet.

        Returns list of order dicts with keys: id, symbol, side, quantity, price, currency
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with _led_api_call():
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
        totals = {}

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
        if not self.is_connected:
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
            with _led_api_call():
                data = self._client.get_candles(symbol, start=start, end=end)
            result = []

            # Debug: log what we received
            logger.info(
                f"get_candles response for {symbol}: type={type(data)}, value={str(data)[:200] if data else 'None'}"
            )

            data = _parse_price_data_string(data, symbol)
            if isinstance(data, dict):
                result = _parse_hloc_format(data, symbol, start) or _parse_candles_format(
                    data
                )
            elif isinstance(data, list):
                result = _parse_candles_list(data)

            return result
        except Exception as e:
            logger.error(f"Failed to get historical prices for {symbol}: {e}")
            return []

    def get_security_info(self, symbol: str) -> dict | None:
        """
        Get security info including lot size from Tradernet API.

        Args:
            symbol: Stock symbol (e.g., "XIAO.1810.AS")

        Returns:
            Dict with security info including 'lot' (minimum lot size) if available,
            None if the request fails.
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with _led_api_call():
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
        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        trading_mode = _get_trading_mode()
        if trading_mode == "research":
            return _create_research_mode_order(symbol, side, quantity, self)

        try:
            if side.upper() == "BUY":
                result = self._client.buy(symbol, quantity)
            elif side.upper() == "SELL":
                result = self._client.sell(symbol, quantity)
            else:
                raise ValueError(f"Invalid side: {side}")

            return _create_order_result(result, symbol, side, quantity)
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            self._client.cancel(order_id)
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

    def _parse_trade(self, trade: dict) -> dict | None:
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
        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with _led_api_call():
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
        import json as json_lib

        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with _led_api_call():
                # Get client history - only withdrawals (337) are returned
                history = self._client.authorized_request(
                    "getClientCpsHistory", {"limit": 500}, version=2
                )

            total_withdrawals = 0.0
            withdrawals = []

            # Parse the response - it's a list of transactions
            records = history if isinstance(history, list) else []

            for record in records:
                withdrawal = _parse_withdrawal_record(record)
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
        import json as json_lib

        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        all_transactions = []

        try:
            all_transactions.extend(_get_cps_history_transactions(self._client, limit))
            all_transactions.extend(_get_corporate_action_transactions(self._client))
            all_transactions.extend(_get_trade_fee_transactions(self._client))
            return all_transactions
        except Exception as e:
            logger.error(f"Failed to get all cash flows: {e}")
            return []


# Singleton instance
_client: Optional[TradernetClient] = None


def get_tradernet_client() -> TradernetClient:
    """Get or create the Tradernet client singleton."""
    global _client
    if _client is None:
        _client = TradernetClient()
    return _client
