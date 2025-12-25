"""Tradernet (Freedom24) API client service."""

import logging
import requests
import threading
import hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from tradernet import TraderNetAPI

# Alias for backward compatibility
Tradernet = TraderNetAPI

from app.config import settings
from app.infrastructure.events import emit, SystemEvent

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
    from app.domain.constants import DEFAULT_CURRENCY
    
    global _exchange_rates, _rates_updated
    
    if to_currency is None:
        to_currency = DEFAULT_CURRENCY

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
            "HKD_EUR": 8.5,   # ~8.5 HKD per EUR
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
                settings.tradernet_api_key,
                settings.tradernet_api_secret
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

            from app.domain.constants import DEFAULT_CURRENCY
            
            for item in pos_data:
                avg_price = float(item.get("bal_price_a", 0))
                current_price = float(item.get("mkt_price", 0))
                quantity = float(item.get("q", 0))
                # Calculate market_value ourselves - don't trust API's market_value
                # (Tradernet sometimes returns wrong values, e.g., ETF's AUM instead of position value)
                market_value = quantity * current_price
                currency = item.get("curr", DEFAULT_CURRENCY)

                # Get real-time exchange rate instead of API's currval
                currency_rate = get_exchange_rate(currency, DEFAULT_CURRENCY)

                # Convert market_value to default currency (EUR)
                if currency == DEFAULT_CURRENCY:
                    market_value_eur = market_value
                else:
                    market_value_eur = market_value / currency_rate if currency_rate > 0 else market_value

                positions.append(Position(
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
                ))

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
                    balances.append(CashBalance(
                        currency=item.get("curr", ""),
                        amount=amount,
                    ))

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

            from app.domain.constants import DEFAULT_CURRENCY
            
            for item in acc_data:
                amount = float(item.get("s", 0))
                currency = item.get("curr", DEFAULT_CURRENCY)

                if currency == DEFAULT_CURRENCY:
                    total += amount
                elif amount > 0:
                    # Convert to EUR using real-time exchange rate
                    rate = get_exchange_rate(currency, DEFAULT_CURRENCY)
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
                pending.append({
                    "id": order.get("id"),
                    "symbol": order.get("instr_name"),
                    "side": order.get("buy_sell"),  # "buy" or "sell"
                    "quantity": float(order.get("qty", 0)),
                    "price": float(order.get("price", 0)),
                    "currency": order.get("curr"),
                })

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
        Check if a pending order exists for the given symbol.

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
        days: Optional[int] = None  # Backward compatibility
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
            logger.info(f"get_candles response for {symbol}: type={type(data)}, value={str(data)[:200] if data else 'None'}")

            # Handle different response types
            if isinstance(data, str):
                # If it's a JSON string, parse it
                import json
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning(f"Received non-JSON string response for {symbol}: {data[:100]}")
                    return []

            if isinstance(data, dict):
                # Check for hloc format: {'hloc': {'SYMBOL': [[high, low, open, close], ...]}}
                hloc_data = data.get("hloc", {})
                if hloc_data and isinstance(hloc_data, dict):
                    # Get the data for this symbol
                    symbol_data = hloc_data.get(symbol, [])
                    if symbol_data and isinstance(symbol_data, list):
                        # Calculate start date for timestamps (assuming daily candles)
                        current_date = start
                        for candle_array in symbol_data:
                            if isinstance(candle_array, list) and len(candle_array) >= 4:
                                # Format appears to be [high, low, open, close] or [open, high, low, close]
                                # Try both interpretations
                                if len(candle_array) == 4:
                                    # Assume [high, low, open, close] based on typical OHLC order
                                    high = float(candle_array[0])
                                    low = float(candle_array[1])
                                    open_price = float(candle_array[2])
                                    close = float(candle_array[3])
                                else:
                                    # Fallback
                                    high = float(candle_array[0]) if len(candle_array) > 0 else 0
                                    low = float(candle_array[1]) if len(candle_array) > 1 else 0
                                    open_price = float(candle_array[2]) if len(candle_array) > 2 else 0
                                    close = float(candle_array[3]) if len(candle_array) > 3 else 0
                                
                                result.append(OHLC(
                                    timestamp=current_date,
                                    open=open_price,
                                    high=high,
                                    low=low,
                                    close=close,
                                    volume=0,  # Volume not provided in this format
                                ))
                                # Move to next day
                                current_date += timedelta(days=1)
                
                # Fallback: try candles format (dict with keys)
                if not result:
                    candles = data.get("candles", [])
                    for candle in candles:
                        if isinstance(candle, dict):
                            result.append(OHLC(
                                timestamp=datetime.fromtimestamp(candle.get("t", 0)),
                                open=float(candle.get("o", 0)),
                                high=float(candle.get("h", 0)),
                                low=float(candle.get("l", 0)),
                                close=float(candle.get("c", 0)),
                                volume=int(candle.get("v", 0)),
                            ))
            elif isinstance(data, list):
                # Direct list of candles (dict format)
                for candle in data:
                    if isinstance(candle, dict):
                        result.append(OHLC(
                            timestamp=datetime.fromtimestamp(candle.get("t", 0)),
                            open=float(candle.get("o", 0)),
                            high=float(candle.get("h", 0)),
                            low=float(candle.get("l", 0)),
                            close=float(candle.get("c", 0)),
                            volume=int(candle.get("v", 0)),
                        ))

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
        limit_price: Optional[float] = None
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

        try:
            if side.upper() == "BUY":
                result = self._client.buy(symbol, quantity)
            elif side.upper() == "SELL":
                result = self._client.sell(symbol, quantity)
            else:
                raise ValueError(f"Invalid side: {side}")

            if isinstance(result, dict):
                return OrderResult(
                    order_id=str(result.get("order_id", result.get("orderId", ""))),
                    symbol=symbol,
                    side=side.upper(),
                    quantity=quantity,
                    price=float(result.get("price", 0)),
                    status=result.get("status", "submitted"),
                )
            return OrderResult(
                order_id=str(result) if result else "",
                symbol=symbol,
                side=side.upper(),
                quantity=quantity,
                price=0,
                status="submitted",
            )
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

            # Parse trades - response format: {"trades": {"trade": [...]}}
            trade_list = trades_data.get("trades", {}).get("trade", [])

            # Handle single trade (dict) vs multiple trades (list)
            if isinstance(trade_list, dict):
                trade_list = [trade_list]

            executed = []
            for trade in trade_list[:limit]:
                try:
                    # Get order ID - try multiple possible fields
                    order_id = str(trade.get("id") or trade.get("order_id") or "")
                    if not order_id:
                        continue

                    # Parse quantity
                    qty_str = trade.get("q") or trade.get("qty") or "0"
                    quantity = float(qty_str) if qty_str else 0

                    # Parse price
                    price_str = trade.get("price") or trade.get("p") or "0"
                    price = float(price_str) if price_str else 0

                    # Parse date
                    trade_date = trade.get("date") or trade.get("d") or ""

                    # Parse side (BUY/SELL) - type field: 1=BUY, 2=SELL
                    trade_type = trade.get("type") or ""
                    if trade_type == "1" or trade_type == 1:
                        side = "BUY"
                    elif trade_type == "2" or trade_type == 2:
                        side = "SELL"
                    else:
                        side = ""

                    executed.append({
                        "order_id": order_id,
                        "symbol": trade.get("instr_nm") or trade.get("i") or "",
                        "side": side,
                        "quantity": quantity,
                        "price": price,
                        "executed_at": trade_date,
                    })
                except Exception as e:
                    logger.warning(f"Failed to parse trade: {e}")
                    continue

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
                    "getClientCpsHistory",
                    {"limit": 500},
                    version=2
                )

            total_withdrawals = 0.0
            withdrawals = []

            # Parse the response - it's a list of transactions
            records = history if isinstance(history, list) else []

            for record in records:
                # Only process completed withdrawals (type_doc_id=337, status_c=3)
                if record.get("type_doc_id") != 337:
                    continue
                if record.get("status_c") != 3:
                    continue

                # Parse the params JSON string
                params_str = record.get("params", "{}")
                try:
                    params = json_lib.loads(params_str) if isinstance(params_str, str) else params_str
                except json_lib.JSONDecodeError:
                    continue

                from app.domain.constants import DEFAULT_CURRENCY
                currency = params.get("currency", DEFAULT_CURRENCY)
                amount = float(params.get("totalMoneyOut", 0))

                # Convert to default currency (EUR) if needed
                if currency != DEFAULT_CURRENCY and amount > 0:
                    rate = get_exchange_rate(currency, DEFAULT_CURRENCY)
                    if rate > 0:
                        amount = amount / rate

                total_withdrawals += amount
                withdrawals.append({
                    "date": record.get("date_crt", "")[:10],
                    "amount_eur": round(amount, 2),
                    "currency": currency,
                })

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
            # 1. Get transactions from getClientCpsHistory
            with _led_api_call():
                history = self._client.authorized_request(
                    "getClientCpsHistory",
                    {"limit": limit},
                    version=2
                )

            records = history if isinstance(history, list) else []
            
            # Map of known type_doc_id to transaction types
            # Based on API exploration, these are the cash flow related types:
            type_mapping = {
                337: "withdrawal",  # Cash withdrawals
                297: "structured_product_purchase",  # Structured product purchases
                # Other types (217, 269, 278, 290, 355, 356) are document/account management, not cash flows
            }

            for record in records:
                try:
                    # Parse the params JSON string
                    params_str = record.get("params", "{}")
                    try:
                        params = json_lib.loads(params_str) if isinstance(params_str, str) else params_str
                    except (json_lib.JSONDecodeError, TypeError):
                        params = {}
                        logger.warning(f"Failed to parse params for record: {record.get('id', 'unknown')}")

                    type_doc_id = record.get("type_doc_id")
                    if type_doc_id is None:
                        logger.warning(f"Skipping record with no type_doc_id: {record}")
                        continue
                    
                    status_c = record.get("status_c")
                    
                    # Infer transaction type
                    transaction_type = type_mapping.get(type_doc_id, f"type_{type_doc_id}")
                    
                    # Try to determine amount and currency from params
                    # Different transaction types may have different field names
                    amount = 0.0
                    currency = "EUR"
                    
                    # Check common field names based on transaction type
                    try:
                        if "totalMoneyOut" in params:
                            # Withdrawals (type 337)
                            amount = float(params.get("totalMoneyOut", 0))
                            currency = params.get("currency", "EUR")
                        elif "totalMoneyIn" in params:
                            # Deposits (if any)
                            amount = float(params.get("totalMoneyIn", 0))
                            currency = params.get("currency", "EUR")
                        elif "structured_product_trade_sum" in params:
                            # Structured product purchases (type 297)
                            amount = float(params.get("structured_product_trade_sum", 0))
                            currency = params.get("structured_product_currency", "USD")
                        elif "amount" in params:
                            amount = float(params.get("amount", 0))
                            currency = params.get("currency", "EUR")
                        elif "sum" in params:
                            amount = float(params.get("sum", 0))
                            currency = params.get("currency", "EUR")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse amount for transaction {type_doc_id}: {e}")
                        amount = 0.0
                    
                    # Convert to EUR
                    amount_eur = amount
                    if currency and currency != "EUR" and amount != 0:
                        try:
                            rate = get_exchange_rate(currency, "EUR")
                            if rate > 0:
                                amount_eur = amount / rate
                        except Exception as e:
                            logger.warning(f"Failed to convert {currency} to EUR: {e}")
                            # Keep original amount if conversion fails

                    # Get transaction ID - try multiple possible ID fields
                    # The API may provide: id, transaction_id, doc_id, or we construct one
                    transaction_id = (
                        record.get("id") or 
                        record.get("transaction_id") or 
                        record.get("doc_id")
                    )
                    
                    # If no explicit ID, create a unique one from record fields
                    if not transaction_id:
                        # Use a combination of fields that should be unique
                        unique_str = f"{type_doc_id}_{record.get('date_crt', '')}_{record.get('status_c', '')}_{amount}_{json_lib.dumps(params, sort_keys=True)}"
                        # Create a short hash for uniqueness
                        transaction_id = f"{type_doc_id}_{hashlib.md5(unique_str.encode()).hexdigest()[:8]}"
                    
                    # Ensure it's a string
                    transaction_id = str(transaction_id)
                    
                    # Get date
                    date_crt = record.get("date_crt", "")
                    date = date_crt[:10] if len(date_crt) >= 10 else date_crt
                    if not date:
                        # Fallback to current date if no date provided
                        date = datetime.now().strftime("%Y-%m-%d")
                    
                    # Get description
                    description = record.get("name", "") or record.get("description", "")
                    
                    # Map status code to status text
                    status_map = {
                        1: "pending",
                        2: "processing",
                        3: "completed",
                        4: "cancelled",
                        5: "rejected",
                    }
                    status = status_map.get(status_c, f"status_{status_c}")

                    all_transactions.append({
                        "transaction_id": transaction_id,
                        "type_doc_id": type_doc_id,
                        "transaction_type": transaction_type,
                        "date": date,
                        "amount": amount,
                        "currency": currency or "EUR",
                        "amount_eur": round(amount_eur, 2),
                        "status": status,
                        "status_c": status_c,
                        "description": description,
                        "params": params,
                    })
                    
                    # Extract fees from withdrawals and structured products as separate transactions
                    if type_doc_id == 337 and "total_commission" in params:
                        # Withdrawal fee
                        withdrawal_fee = params.get("total_commission", 0)
                        if withdrawal_fee and float(withdrawal_fee) > 0:
                            fee_currency = params.get("commission_currency", currency)
                            fee_amount_eur = float(withdrawal_fee)
                            if fee_currency != "EUR":
                                try:
                                    rate = get_exchange_rate(fee_currency, "EUR")
                                    if rate > 0:
                                        fee_amount_eur = float(withdrawal_fee) / rate
                                except Exception:
                                    pass
                            
                            fee_transaction_id = f"{transaction_id}_fee"
                            all_transactions.append({
                                "transaction_id": fee_transaction_id,
                                "type_doc_id": "withdrawal_fee",
                                "transaction_type": "withdrawal_fee",
                                "date": date,
                                "amount": float(withdrawal_fee),
                                "currency": fee_currency,
                                "amount_eur": round(fee_amount_eur, 2),
                                "status": status,
                                "status_c": status_c,
                                "description": f"Withdrawal fee for {amount} {currency} withdrawal",
                                "params": {"withdrawal_id": transaction_id, **params},
                            })
                    elif type_doc_id == 297 and "structured_product_trade_commission" in params:
                        # Structured product commission
                        sp_commission = params.get("structured_product_trade_commission", 0)
                        if sp_commission and float(sp_commission) > 0:
                            sp_comm_currency = currency
                            sp_comm_eur = float(sp_commission)
                            if sp_comm_currency != "EUR":
                                try:
                                    rate = get_exchange_rate(sp_comm_currency, "EUR")
                                    if rate > 0:
                                        sp_comm_eur = float(sp_commission) / rate
                                except Exception:
                                    pass
                            
                            fee_transaction_id = f"{transaction_id}_fee"
                            all_transactions.append({
                                "transaction_id": fee_transaction_id,
                                "type_doc_id": "structured_product_fee",
                                "transaction_type": "structured_product_fee",
                                "date": date,
                                "amount": float(sp_commission),
                                "currency": sp_comm_currency,
                                "amount_eur": round(sp_comm_eur, 2),
                                "status": status,
                                "status_c": status_c,
                                "description": f"Structured product commission",
                                "params": {"product_id": transaction_id, **params},
                            })
                except Exception as e:
                    logger.error(f"Failed to process transaction record: {e}")
                    logger.debug(f"Record data: {record}")
                    continue

            # 2. Get dividends, coupons, and other corporate actions
            try:
                with _led_api_call():
                    corporate_actions = self._client.corporate_actions()
                
                # Filter for executed actions that result in cash flows
                executed_actions = [
                    a for a in corporate_actions 
                    if isinstance(a, dict) and a.get("executed", False)
                ]
                
                for action in executed_actions:
                    try:
                        action_type = action.get("type", "").lower()
                        
                        # Only process cash flow generating actions
                        if action_type not in ["dividend", "coupon", "maturity", "partial_maturity"]:
                            continue
                        
                        # Calculate amount
                        amount_per_one = float(action.get("amount_per_one", 0))
                        executed_count = int(action.get("executed_count", 0))
                        amount = amount_per_one * executed_count
                        
                        if amount == 0:
                            continue
                        
                        currency = action.get("currency", "USD")
                        pay_date = action.get("pay_date", action.get("ex_date", ""))
                        date = pay_date[:10] if len(pay_date) >= 10 else pay_date
                        
                        # Convert to EUR
                        amount_eur = amount
                        if currency != "EUR" and amount != 0:
                            try:
                                rate = get_exchange_rate(currency, "EUR")
                                if rate > 0:
                                    amount_eur = amount / rate
                            except Exception as e:
                                logger.warning(f"Failed to convert {currency} to EUR: {e}")
                        
                        # Create transaction ID
                        action_id = action.get("id") or action.get("corporate_action_id", "")
                        transaction_id = f"corp_action_{action_type}_{action_id}"
                        
                        # Description
                        ticker = action.get("ticker", "")
                        description = f"{action_type.title()}: {ticker} ({executed_count} shares × {amount_per_one} {currency})"
                        
                        all_transactions.append({
                            "transaction_id": transaction_id,
                            "type_doc_id": f"corp_{action_type}",  # Use string ID for corporate actions
                            "transaction_type": action_type,
                            "date": date,
                            "amount": amount,
                            "currency": currency,
                            "amount_eur": round(amount_eur, 2),
                            "status": "completed",  # Executed actions are completed
                            "status_c": None,
                            "description": description,
                            "params": action,
                        })
                    except Exception as e:
                        logger.error(f"Failed to process corporate action: {e}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Failed to get corporate actions: {e}")
            
            # 3. Get trading fees/commissions from trades
            try:
                with _led_api_call():
                    trades_data = self._client.get_trades_history()
                
                trade_list = trades_data.get("trades", {}).get("trade", [])
                
                for trade in trade_list:
                    try:
                        # Get commission
                        commission_str = trade.get("commission", "0")
                        try:
                            commission = float(commission_str) if commission_str else 0.0
                        except (ValueError, TypeError):
                            commission = 0.0
                        
                        if commission == 0:
                            continue
                        
                        currency = trade.get("commission_currency", trade.get("curr_c", "EUR"))
                        trade_date = trade.get("date", "")
                        date = trade_date[:10] if len(trade_date) >= 10 else trade_date
                        
                        # Convert to EUR
                        amount_eur = commission
                        if currency != "EUR" and commission != 0:
                            try:
                                rate = get_exchange_rate(currency, "EUR")
                                if rate > 0:
                                    amount_eur = commission / rate
                            except Exception as e:
                                logger.warning(f"Failed to convert {currency} to EUR: {e}")
                        
                        # Create transaction ID
                        trade_id = trade.get("id") or trade.get("order_id", "")
                        transaction_id = f"trade_fee_{trade_id}"
                        
                        # Description
                        instr_name = trade.get("instr_nm", "")
                        description = f"Trading fee: {instr_name}"
                        
                        all_transactions.append({
                            "transaction_id": transaction_id,
                            "type_doc_id": "trade_fee",
                            "transaction_type": "trading_fee",
                            "date": date,
                            "amount": commission,
                            "currency": currency,
                            "amount_eur": round(amount_eur, 2),
                            "status": "completed",
                            "status_c": None,
                            "description": description,
                            "params": trade,
                        })
                    except Exception as e:
                        logger.error(f"Failed to process trade fee: {e}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Failed to get trades history: {e}")

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
