"""Core Tradernet service wrapping the SDK."""

import logging
from datetime import datetime
from typing import Optional

from app.config import settings
from app.models.tradernet_models import (
    OHLC,
    CashBalance,
    CashTransaction,
    OrderResult,
    PendingOrder,
    Position,
    Quote,
    SecurityInfo,
    Trade,
)
from tradernet import TraderNetAPI

logger = logging.getLogger(__name__)


class TradernetService:
    """Service wrapping Tradernet SDK."""

    def __init__(self):
        """Initialize the Tradernet service."""
        self._client: Optional[TraderNetAPI] = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to Tradernet API (for backward compatibility).

        Returns:
            True if connection successful, False otherwise
        """
        if not settings.tradernet_api_key or not settings.tradernet_api_secret:
            logger.warning("Tradernet API credentials not configured")
            return False

        try:
            client = TraderNetAPI(
                settings.tradernet_api_key, settings.tradernet_api_secret
            )
            # Test connection
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
        """Check if client is connected (for backward compatibility)."""
        return self._connected and self._client is not None

    def _get_client(
        self, api_key: Optional[str] = None, api_secret: Optional[str] = None
    ) -> TraderNetAPI:
        """Get a TraderNetAPI client with credentials.

        Args:
            api_key: Optional API key (if not provided, uses settings)
            api_secret: Optional API secret (if not provided, uses settings)

        Returns:
            TraderNetAPI client instance

        Raises:
            ValueError: If credentials are not available
        """
        # Use provided credentials or fall back to settings
        key = api_key if api_key else settings.tradernet_api_key
        secret = api_secret if api_secret else settings.tradernet_api_secret

        if not key or not secret:
            raise ValueError("Tradernet API credentials not provided")

        # Create new client instance with credentials
        return TraderNetAPI(key, secret)

    # Trading operations
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> Optional[OrderResult]:
        """Place an order.

        Args:
            symbol: Security symbol (e.g., "AAPL.US")
            side: "BUY" or "SELL"
            quantity: Number of shares
            api_key: Optional API key (if not provided, uses settings)
            api_secret: Optional API secret (if not provided, uses settings)

        Returns:
            OrderResult if successful, None otherwise
        """
        try:
            client = self._get_client(api_key, api_secret)
            quantity_int = int(quantity)

            if side.upper() == "BUY":
                result = client.buy(symbol, quantity_int)  # type: ignore
            elif side.upper() == "SELL":
                result = client.sell(symbol, quantity_int)  # type: ignore
            else:
                raise ValueError(f"Invalid side: {side}")

            # Parse result
            order_id = str(result.get("id", "") or result.get("orderId", ""))
            price = float(result.get("price", 0) or result.get("p", 0))

            return OrderResult(
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
            )
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None

    def get_pending_orders(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> list[PendingOrder]:
        """Get all pending/active orders."""
        try:
            client = self._get_client(api_key, api_secret)
            response = client.get_placed(active=True)  # type: ignore
            orders_data = response.get("result", {}).get("orders", {})
            order_list = orders_data.get("order", [])

            if isinstance(order_list, dict):
                order_list = [order_list]

            pending = []
            for order in order_list:
                pending.append(
                    PendingOrder(
                        id=str(order.get("id", "")),
                        symbol=order.get("instr_name", ""),
                        side=order.get("buy_sell", ""),
                        quantity=float(order.get("qty", 0)),
                        price=float(order.get("price", 0)),
                        currency=order.get("curr", ""),
                    )
                )

            return pending
        except Exception as e:
            logger.error(f"Failed to get pending orders: {e}")
            return []

    def has_pending_order_for_symbol(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> bool:
        """Check if a pending order exists for the given symbol."""
        pending = self.get_pending_orders(api_key, api_secret)
        for order in pending:
            if order.symbol == symbol:
                return True
        return False

    def get_pending_order_totals(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> dict[str, float]:
        """Get total value of pending BUY orders grouped by currency."""
        pending = self.get_pending_orders(api_key, api_secret)
        totals: dict[str, float] = {}

        for order in pending:
            if order.side and order.side.lower() == "buy":
                currency = order.currency or "EUR"
                value = order.quantity * order.price
                totals[currency] = totals.get(currency, 0) + value

        return totals

    # Portfolio operations
    def get_portfolio(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> list[Position]:
        """Get current portfolio positions."""
        try:
            client = self._get_client(api_key, api_secret)
            summary = client.account_summary()  # type: ignore
            positions = []

            ps_data = summary.get("result", {}).get("ps", {})
            pos_data = ps_data.get("pos", [])

            for item in pos_data:
                avg_price = float(item.get("bal_price_a", 0))
                current_price = float(item.get("mkt_price", 0))
                quantity = float(item.get("q", 0))
                market_value = quantity * current_price
                currency = item.get("curr", "EUR")

                # Simple exchange rate - in production would use ExchangeRateService
                # For now, assume EUR or use simple conversion
                currency_rate = 1.0  # Simplified - will be handled by Go service
                market_value_eur = market_value

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

    def get_cash_balances(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> list[CashBalance]:
        """Get cash balances in all currencies."""
        try:
            client = self._get_client(api_key, api_secret)
            summary = client.account_summary()  # type: ignore
            balances = []

            ps_data = summary.get("result", {}).get("ps", {})
            acc_data = ps_data.get("acc", [])

            for item in acc_data:
                amount = float(item.get("s", 0))
                currency = item.get("curr", "")

                balances.append(
                    CashBalance(
                        currency=currency,
                        amount=amount,
                    )
                )

                if amount < 0:
                    logger.warning(f"Negative cash balance: {amount:.2f} {currency}")

            return balances
        except Exception as e:
            logger.error(f"Failed to get cash balances: {e}")
            return []

    def get_total_cash_eur(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> float:
        """Get total cash balance in EUR (simplified - no conversion)."""
        balances = self.get_cash_balances(api_key, api_secret)
        total = sum(b.amount for b in balances if b.currency == "EUR")
        return total

    # Transactions
    def get_cash_movements(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> dict:
        """Get withdrawal history."""
        try:
            client = self._get_client(api_key, api_secret)
            history = client.authorized_request(  # type: ignore
                "getClientCpsHistory", {"limit": 500}, version=2
            )

            total_withdrawals = 0.0
            withdrawals = []

            records = history if isinstance(history, list) else []

            for record in records:
                # Parse withdrawal records (simplified)
                amount = float(record.get("amount", 0))
                total_withdrawals += amount
                withdrawals.append(
                    {
                        "transaction_id": str(record.get("id", "")),
                        "date": record.get("date", ""),
                        "amount": amount,
                        "currency": record.get("currency", "EUR"),
                        "amount_eur": amount,  # Simplified
                        "status": "completed",
                    }
                )

            return {
                "total_withdrawals": round(total_withdrawals, 2),
                "withdrawals": withdrawals,
                "note": "Deposits are not available via API",
            }
        except Exception as e:
            logger.error(f"Failed to get cash movements: {e}")
            return {
                "total_withdrawals": 0,
                "withdrawals": [],
                "error": str(e),
            }

    def get_all_cash_flows(
        self,
        limit: int = 1000,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> list[CashTransaction]:
        """Get all cash flow transactions (simplified implementation)."""
        # This is a simplified version - full implementation would combine
        # multiple API calls as in the original Python client
        # Credentials accepted for consistency, but not used in current implementation
        return []

    def get_executed_trades(
        self,
        limit: int = 500,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> list[Trade]:
        """Get executed trades history."""
        try:
            client = self._get_client(api_key, api_secret)
            trades_data = client.get_trades_history()  # type: ignore
            trade_list = trades_data.get("trades", {}).get("trade", [])

            if isinstance(trade_list, dict):
                trade_list = [trade_list]

            executed = []
            for trade in trade_list[:limit]:
                order_id = str(trade.get("id") or trade.get("order_id") or "")
                if not order_id:
                    continue

                quantity = float(trade.get("q") or trade.get("qty") or 0)
                price = float(trade.get("price") or trade.get("p") or 0)
                trade_type = trade.get("type", "")
                side = "BUY" if trade_type in ("1", 1) else "SELL"

                executed.append(
                    Trade(
                        order_id=order_id,
                        symbol=trade.get("instr_nm") or trade.get("i") or "",
                        side=side,
                        quantity=quantity,
                        price=price,
                        executed_at=trade.get("date") or trade.get("d") or "",
                    )
                )

            return executed
        except Exception as e:
            logger.error(f"Failed to get executed trades: {e}")
            return []

    # Market data
    def get_quote(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> Optional[Quote]:
        """Get current quote for a symbol."""
        try:
            client = self._get_client(api_key, api_secret)
            quotes = client.get_quotes([symbol])  # type: ignore
            if quotes:
                if isinstance(quotes, list) and len(quotes) > 0:
                    data = quotes[0]
                elif isinstance(quotes, dict):
                    data = quotes
                else:
                    return None
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

    def get_quotes_raw(
        self,
        symbols: list[str],
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> dict:
        """Get raw quote data for multiple symbols."""
        try:
            client = self._get_client(api_key, api_secret)
            return client.get_quotes(symbols)  # type: ignore
        except Exception as e:
            logger.error(f"Failed to get raw quotes: {e}")
            return {}

    def get_historical_prices(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> list[OHLC]:
        """Get historical OHLC data."""
        if start is None:
            start = datetime(2010, 1, 1)
        if end is None:
            end = datetime.now()

        try:
            client = self._get_client(api_key, api_secret)
            data = client.get_candles(symbol, start=start, end=end)  # type: ignore

            # Simplified parsing - full implementation would handle multiple formats
            if isinstance(data, list):
                result = []
                for candle in data:
                    result.append(
                        OHLC(
                            date=candle.get("date", ""),
                            open=float(candle.get("o", 0)),
                            high=float(candle.get("h", 0)),
                            low=float(candle.get("l", 0)),
                            close=float(candle.get("c", 0)),
                            volume=int(candle.get("v", 0)),
                        )
                    )
                return result

            return []
        except Exception as e:
            logger.error(f"Failed to get historical prices for {symbol}: {e}")
            return []

    # Security lookup
    def find_symbol(
        self,
        symbol: str,
        exchange: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> dict:
        """Find security by symbol or ISIN."""
        try:
            client = self._get_client(api_key, api_secret)
            result = client.find_symbol(symbol, exchange=exchange)  # type: ignore

            # Parse results
            found = result.get("found", [])
            securities = []

            for item in found:
                securities.append(
                    SecurityInfo(
                        symbol=item.get("t", ""),
                        name=item.get("nm", ""),
                        isin=item.get("isin", ""),
                        currency=item.get("x_curr", ""),
                        market=item.get("mkt", ""),
                        exchange_code=item.get("codesub", ""),
                    )
                )

            return {"found": [s.dict() for s in securities]}
        except Exception as e:
            logger.error(f"Failed to find symbol {symbol}: {e}")
            return {"found": []}

    def get_security_info(
        self,
        symbol: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ) -> Optional[dict]:
        """Get security info including lot size."""
        try:
            client = self._get_client(api_key, api_secret)
            info = client.security_info(symbol)  # type: ignore
            return info
        except Exception as e:
            logger.warning(f"Failed to get security info for {symbol}: {e}")
            return None


# Singleton instance
_service: Optional[TradernetService] = None


def get_tradernet_service() -> TradernetService:
    """Get or create the Tradernet service singleton."""
    global _service
    if _service is None:
        _service = TradernetService()
    return _service
