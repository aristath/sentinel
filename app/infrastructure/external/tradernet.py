"""Tradernet (Freedom24) API client service."""

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


def get_exchange_rate(from_currency: str, to_currency: Optional[str] = None) -> float:
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


def _parse_price_data_string(data, symbol: str):
    """Parse price data if it's a JSON string."""
    if isinstance(data, str):
        import json

        try:
            return json.loads(data)
        except json.JSONDecodeError:
            logger.warning(
                f"Received non-JSON string response for {symbol}: {data[:100]}"
            )
            return []
    return data


def _parse_hloc_format(data: dict, symbol: str, start: datetime) -> list[OHLC]:
    """Parse hloc format: {'hloc': {'SYMBOL': [[high, low, open, close], ...]}}."""
    hloc_data = data.get("hloc", {})
    if not hloc_data or not isinstance(hloc_data, dict):
        return []

    symbol_data = hloc_data.get(symbol, [])
    if not symbol_data or not isinstance(symbol_data, list):
        return []

    result = []
    current_date = start
    for candle_array in symbol_data:
        if isinstance(candle_array, list) and len(candle_array) >= 4:
            if len(candle_array) == 4:
                high = float(candle_array[0])
                low = float(candle_array[1])
                open_price = float(candle_array[2])
                close = float(candle_array[3])
            else:
                high = float(candle_array[0]) if len(candle_array) > 0 else 0
                low = float(candle_array[1]) if len(candle_array) > 1 else 0
                open_price = float(candle_array[2]) if len(candle_array) > 2 else 0
                close = float(candle_array[3]) if len(candle_array) > 3 else 0

            result.append(
                OHLC(
                    timestamp=current_date,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=0,
                )
            )
            current_date += timedelta(days=1)

    return result


def _parse_candles_format(data: dict) -> list[OHLC]:
    """Parse candles format from dict."""
    candles = data.get("candles", [])
    result = []
    for candle in candles:
        if isinstance(candle, dict):
            result.append(
                OHLC(
                    timestamp=datetime.fromtimestamp(candle.get("t", 0)),
                    open=float(candle.get("o", 0)),
                    high=float(candle.get("h", 0)),
                    low=float(candle.get("l", 0)),
                    close=float(candle.get("c", 0)),
                    volume=int(candle.get("v", 0)),
                )
            )
    return result


def _parse_candles_list(data: list) -> list[OHLC]:
    """Parse direct list of candles."""
    result = []
    for candle in data:
        if isinstance(candle, dict):
            result.append(
                OHLC(
                    timestamp=datetime.fromtimestamp(candle.get("t", 0)),
                    open=float(candle.get("o", 0)),
                    high=float(candle.get("h", 0)),
                    low=float(candle.get("l", 0)),
                    close=float(candle.get("c", 0)),
                    volume=int(candle.get("v", 0)),
                )
            )
    return result


def _get_trading_mode() -> str:
    """Get trading mode from cache."""
    from app.infrastructure.cache import get_cache

    cache = get_cache()
    trading_mode = "research"
    try:
        cached_settings = cache.get("settings:all")
        if cached_settings and "trading_mode" in cached_settings:
            trading_mode = cached_settings["trading_mode"]
    except Exception:
        pass
    return trading_mode


def _create_research_mode_order(
    symbol: str, side: str, quantity: float, client
) -> OrderResult:
    """Create a mock order result for research mode."""
    try:
        quote = client.get_quote(symbol)
        mock_price = quote.price if quote else 0.0
    except Exception:
        mock_price = 0.0

    return OrderResult(
        order_id=f"RESEARCH_{symbol}_{datetime.now().timestamp()}",
        symbol=symbol,
        side=side.upper(),
        quantity=quantity,
        price=mock_price,
        status="submitted",
    )


def _create_order_result(
    result, symbol: str, side: str, quantity: float
) -> OrderResult:
    """Create OrderResult from API response."""
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


def _parse_cps_history_params(params_str) -> dict:
    """Parse params JSON string from CPS history record."""
    import json as json_lib

    try:
        return json_lib.loads(params_str) if isinstance(params_str, str) else params_str
    except (json_lib.JSONDecodeError, TypeError):
        return {}


def _extract_amount_and_currency(params: dict, type_doc_id: int) -> tuple[float, str]:
    """Extract amount and currency from params based on transaction type."""
    amount = 0.0
    currency = "EUR"

    try:
        if "totalMoneyOut" in params:
            amount = float(params.get("totalMoneyOut", 0))
            currency = params.get("currency", "EUR")
        elif "totalMoneyIn" in params:
            amount = float(params.get("totalMoneyIn", 0))
            currency = params.get("currency", "EUR")
        elif "structured_product_trade_sum" in params:
            amount = float(params.get("structured_product_trade_sum", 0))
            currency = params.get("structured_product_currency", "USD")
        elif "amount" in params:
            amount = float(params.get("amount", 0))
            currency = params.get("currency", "EUR")
        elif "sum" in params:
            amount = float(params.get("sum", 0))
            currency = params.get("currency", "EUR")
    except (ValueError, TypeError):
        pass

    return amount, currency


def _convert_amount_to_eur(amount: float, currency: str) -> float:
    """Convert amount to EUR using exchange rate."""
    if currency == "EUR" or amount == 0:
        return amount

    try:
        rate = get_exchange_rate(currency, "EUR")
        if rate > 0:
            return amount / rate
    except Exception:
        pass

    return amount


def _create_transaction_id(record: dict, type_doc_id) -> str:
    """Create unique transaction ID from record."""
    import hashlib
    import json as json_lib

    transaction_id = (
        record.get("id") or record.get("transaction_id") or record.get("doc_id")
    )

    if not transaction_id:
        unique_str = f"{type_doc_id}_{record.get('date_crt', '')}_{record.get('status_c', '')}_{json_lib.dumps(record.get('params', {}), sort_keys=True)}"
        transaction_id = (
            f"{type_doc_id}_{hashlib.md5(unique_str.encode()).hexdigest()[:8]}"
        )

    return str(transaction_id)


def _extract_withdrawal_fee(
    params: dict, transaction_id: str, date: str, currency: str, status: str, status_c
) -> Optional[dict]:
    """Extract withdrawal fee as separate transaction."""
    if "total_commission" not in params:
        return None

    withdrawal_fee = params.get("total_commission", 0)
    if not withdrawal_fee or float(withdrawal_fee) <= 0:
        return None

    fee_currency = params.get("commission_currency", currency)
    fee_amount_eur = _convert_amount_to_eur(float(withdrawal_fee), fee_currency)

    return {
        "transaction_id": f"{transaction_id}_fee",
        "type_doc_id": "withdrawal_fee",
        "transaction_type": "withdrawal_fee",
        "date": date,
        "amount": float(withdrawal_fee),
        "currency": fee_currency,
        "amount_eur": round(fee_amount_eur, 2),
        "status": status,
        "status_c": status_c,
        "description": f"Withdrawal fee for {params.get('totalMoneyOut', 0)} {currency} withdrawal",
        "params": {"withdrawal_id": transaction_id, **params},
    }


def _extract_structured_product_fee(
    params: dict, transaction_id: str, date: str, currency: str, status: str, status_c
) -> Optional[dict]:
    """Extract structured product commission as separate transaction."""
    if "structured_product_trade_commission" not in params:
        return None

    sp_commission = params.get("structured_product_trade_commission", 0)
    if not sp_commission or float(sp_commission) <= 0:
        return None

    sp_comm_eur = _convert_amount_to_eur(float(sp_commission), currency)

    return {
        "transaction_id": f"{transaction_id}_fee",
        "type_doc_id": "structured_product_fee",
        "transaction_type": "structured_product_fee",
        "date": date,
        "amount": float(sp_commission),
        "currency": currency,
        "amount_eur": round(sp_comm_eur, 2),
        "status": status,
        "status_c": status_c,
        "description": "Structured product commission",
        "params": {"product_id": transaction_id, **params},
    }


def _process_cps_history_record(record: dict, type_mapping: dict) -> list[dict]:
    """Process a single CPS history record and return transactions."""
    transactions: list[dict] = []

    try:
        params = _parse_cps_history_params(record.get("params", "{}"))
        type_doc_id = record.get("type_doc_id")
        if type_doc_id is None:
            return transactions

        status_c = record.get("status_c")
        transaction_type = type_mapping.get(type_doc_id, f"type_{type_doc_id}")

        amount, currency = _extract_amount_and_currency(params, type_doc_id)
        amount_eur = _convert_amount_to_eur(amount, currency)

        transaction_id = _create_transaction_id(record, type_doc_id)

        date_crt = record.get("date_crt", "")
        date = (
            date_crt[:10]
            if len(date_crt) >= 10
            else date_crt or datetime.now().strftime("%Y-%m-%d")
        )

        description = record.get("name", "") or record.get("description", "")

        status_map: dict[int, str] = {
            1: "pending",
            2: "processing",
            3: "completed",
            4: "cancelled",
            5: "rejected",
        }
        status = status_map.get(status_c or 0, f"status_{status_c}")

        transactions.append(
            {
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
            }
        )

        fee_transaction = _extract_withdrawal_fee(
            params, transaction_id, date, currency, status, status_c
        )
        if fee_transaction:
            transactions.append(fee_transaction)

        sp_fee_transaction = _extract_structured_product_fee(
            params, transaction_id, date, currency, status, status_c
        )
        if sp_fee_transaction:
            transactions.append(sp_fee_transaction)

    except Exception as e:
        logger.error(f"Failed to process transaction record: {e}")

    return transactions


def _process_corporate_action(action: dict) -> Optional[dict]:
    """Process a single corporate action and return transaction dict."""
    action_type = action.get("type", "").lower()

    if action_type not in ["dividend", "coupon", "maturity", "partial_maturity"]:
        return None

    amount_per_one = float(action.get("amount_per_one", 0))
    executed_count = int(action.get("executed_count", 0))
    amount = amount_per_one * executed_count

    if amount == 0:
        return None

    currency = action.get("currency", "USD")
    pay_date = action.get("pay_date", action.get("ex_date", ""))
    date = pay_date[:10] if len(pay_date) >= 10 else pay_date

    amount_eur = _convert_amount_to_eur(amount, currency)

    action_id = action.get("id") or action.get("corporate_action_id", "")
    transaction_id = f"corp_action_{action_type}_{action_id}"

    ticker = action.get("ticker", "")
    description = f"{action_type.title()}: {ticker} ({executed_count} shares × {amount_per_one} {currency})"

    return {
        "transaction_id": transaction_id,
        "type_doc_id": f"corp_{action_type}",
        "transaction_type": action_type,
        "date": date,
        "amount": amount,
        "currency": currency,
        "amount_eur": round(amount_eur, 2),
        "status": "completed",
        "status_c": None,
        "description": description,
        "params": action,
    }


def _process_trade_fee(trade: dict) -> Optional[dict]:
    """Process a single trade fee and return transaction dict."""
    commission_str = trade.get("commission", "0")
    try:
        commission = float(commission_str) if commission_str else 0.0
    except (ValueError, TypeError):
        commission = 0.0

    if commission == 0:
        return None

    currency = trade.get("commission_currency", trade.get("curr_c", "EUR"))
    trade_date = trade.get("date", "")
    date = trade_date[:10] if len(trade_date) >= 10 else trade_date

    amount_eur = _convert_amount_to_eur(commission, currency)

    trade_id = trade.get("id") or trade.get("order_id", "")
    transaction_id = f"trade_fee_{trade_id}"

    instr_name = trade.get("instr_nm", "")
    description = f"Trading fee: {instr_name}"

    return {
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
    }


def _get_cps_history_transactions(client, limit: int) -> list[dict]:
    """Get transactions from CPS history."""
    try:
        with _led_api_call():
            history = client.authorized_request(
                "getClientCpsHistory", {"limit": limit}, version=2
            )

        records = history if isinstance(history, list) else []
        type_mapping = {337: "withdrawal", 297: "structured_product_purchase"}

        transactions = []
        for record in records:
            transactions.extend(_process_cps_history_record(record, type_mapping))
        return transactions
    except Exception as e:
        logger.warning(f"Failed to get CPS history: {e}")
        return []


def _get_corporate_action_transactions(client) -> list[dict]:
    """Get transactions from corporate actions."""
    try:
        with _led_api_call():
            corporate_actions = client.corporate_actions()

        executed_actions = [
            a
            for a in corporate_actions
            if isinstance(a, dict) and a.get("executed", False)
        ]

        transactions = []
        for action in executed_actions:
            transaction = _process_corporate_action(action)
            if transaction:
                transactions.append(transaction)
        return transactions
    except Exception as e:
        logger.warning(f"Failed to get corporate actions: {e}")
        return []


def _parse_withdrawal_record(record: dict) -> Optional[dict]:
    """Parse a withdrawal record and return withdrawal dict."""
    import json as json_lib

    if record.get("type_doc_id") != 337:
        return None

    if record.get("status_c") != 3:
        return None

    params_str = record.get("params", "{}")
    try:
        params = (
            json_lib.loads(params_str) if isinstance(params_str, str) else params_str
        )
    except json_lib.JSONDecodeError:
        return None

    currency = params.get("currency", "EUR")
    amount = float(params.get("totalMoneyOut", 0))

    if currency != "EUR" and amount > 0:
        rate = get_exchange_rate(currency, "EUR")
        if rate > 0:
            amount = amount / rate

    date_crt = record.get("date_crt", "")
    date = date_crt[:10] if len(date_crt) >= 10 else date_crt

    return {
        "date": date,
        "amount": amount,
        "amount_eur": round(amount, 2),
        "currency": currency,
        "description": record.get("name", ""),
    }


def _get_trade_fee_transactions(client) -> list[dict]:
    """Get transactions from trade fees."""
    try:
        with _led_api_call():
            trades_data = client.get_trades_history()

        trade_list = trades_data.get("trades", {}).get("trade", [])

        transactions = []
        for trade in trade_list:
            transaction = _process_trade_fee(trade)
            if transaction:
                transactions.append(transaction)
        return transactions
    except Exception as e:
        logger.warning(f"Failed to get trades history: {e}")
        return []


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
                result = _parse_hloc_format(
                    data, symbol, start
                ) or _parse_candles_format(data)
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
            # Convert quantity to int as Tradernet API expects int
            quantity_int = int(quantity)
            if side.upper() == "BUY":
                result = self._client.buy(symbol, quantity_int)  # type: ignore[arg-type]
            elif side.upper() == "SELL":
                result = self._client.sell(symbol, quantity_int)  # type: ignore[arg-type]
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
