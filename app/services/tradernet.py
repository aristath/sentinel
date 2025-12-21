"""Tradernet (Freedom24) API client service."""

import logging
import requests
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from tradernet import Tradernet

from app.config import settings
from app.led.display import get_led_display

logger = logging.getLogger(__name__)


@contextmanager
def _led_api_call():
    """Context manager to show LED API call indicator during API calls."""
    display = get_led_display()
    display.set_api_call_active(True)
    if display.is_connected:
        display.show_api_call()
    try:
        yield
    finally:
        display.set_api_call_active(False)

# Cache for exchange rates (refreshed every hour)
_exchange_rates: dict[str, float] = {}
_rates_updated: Optional[datetime] = None


def get_exchange_rate(from_currency: str, to_currency: str = "EUR") -> float:
    """Get exchange rate from currency to EUR using real-time data."""
    global _exchange_rates, _rates_updated

    if from_currency == to_currency:
        return 1.0

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

            for item in pos_data:
                avg_price = float(item.get("bal_price_a", 0))
                current_price = float(item.get("mkt_price", 0))
                quantity = float(item.get("q", 0))
                market_value = float(item.get("market_value", 0))
                currency = item.get("curr", "EUR")

                # Get real-time exchange rate instead of API's currval
                currency_rate = get_exchange_rate(currency, "EUR")

                # Convert market_value to EUR
                if currency == "EUR":
                    market_value_eur = market_value
                else:
                    market_value_eur = market_value / currency_rate

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

            for item in acc_data:
                amount = float(item.get("s", 0))
                currency = item.get("curr", "")

                if currency == "EUR":
                    total += amount
                elif amount > 0:
                    # Convert to EUR using real-time exchange rate
                    rate = get_exchange_rate(currency, "EUR")
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

    def get_historical_prices(
        self,
        symbol: str,
        days: int = 200
    ) -> list[OHLC]:
        """Get historical OHLC data for a symbol."""
        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with _led_api_call():
                data = self._client.get_candles(symbol, count=days)
            result = []

            if isinstance(data, dict):
                candles = data.get("candles", data.get("hloc", []))
                for candle in candles:
                    result.append(OHLC(
                        timestamp=datetime.fromtimestamp(candle.get("t", 0)),
                        open=float(candle.get("o", 0)),
                        high=float(candle.get("h", 0)),
                        low=float(candle.get("l", 0)),
                        close=float(candle.get("c", 0)),
                        volume=int(candle.get("v", 0)),
                    ))

            return result[-days:] if len(result) > days else result
        except Exception as e:
            logger.error(f"Failed to get historical prices for {symbol}: {e}")
            return []

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

    def get_cash_movements(self) -> dict:
        """
        Get total deposits and withdrawals from account.

        Returns dict with:
        - total_deposits: Sum of all deposits in EUR
        - total_withdrawals: Sum of all withdrawals in EUR
        - net_deposits: total_deposits - total_withdrawals
        """
        import json as json_lib

        if not self.is_connected:
            raise ConnectionError("Not connected to Tradernet")

        try:
            with _led_api_call():
                # Get cash movement history
                # status_c: 3 = completed transactions
                history = self._client.authorized_request(
                    "getClientCpsHistory",
                    {"limit": 500},
                    version=2
                )

            total_deposits = 0.0
            total_withdrawals = 0.0

            # Parse the response - it's a list of transactions
            records = history if isinstance(history, list) else []

            for record in records:
                # Only process completed transactions (status_c = 3)
                if record.get("status_c") != 3:
                    continue

                # Parse the params JSON string
                params_str = record.get("params", "{}")
                try:
                    params = json_lib.loads(params_str) if isinstance(params_str, str) else params_str
                except json_lib.JSONDecodeError:
                    continue

                type_doc_id = record.get("type_doc_id")
                currency = params.get("currency", "EUR")

                # Determine amount and type
                # type_doc_id 337 = withdrawal
                # type_doc_id 336 or others = deposit
                if type_doc_id == 337:  # Withdrawal
                    amount = float(params.get("totalMoneyOut", 0))
                    if currency != "EUR" and amount > 0:
                        rate = get_exchange_rate(currency, "EUR")
                        if rate > 0:
                            amount = amount / rate
                    total_withdrawals += abs(amount)
                elif type_doc_id in [336, 335, 334]:  # Various deposit types
                    amount = float(params.get("amount", params.get("totalMoneyIn", 0)))
                    if currency != "EUR" and amount > 0:
                        rate = get_exchange_rate(currency, "EUR")
                        if rate > 0:
                            amount = amount / rate
                    total_deposits += abs(amount)

            return {
                "total_deposits": round(total_deposits, 2),
                "total_withdrawals": round(total_withdrawals, 2),
                "net_deposits": round(total_deposits - total_withdrawals, 2),
            }
        except Exception as e:
            logger.error(f"Failed to get cash movements: {e}")
            return {
                "total_deposits": 0,
                "total_withdrawals": 0,
                "net_deposits": 0,
                "error": str(e),
            }


# Singleton instance
_client: Optional[TradernetClient] = None


def get_tradernet_client() -> TradernetClient:
    """Get or create the Tradernet client singleton."""
    global _client
    if _client is None:
        _client = TradernetClient()
    return _client
