"""
Security - Single source of truth for operations on a single security.

Usage:
    security = Security('AAPL.US')
    await security.load()
    price = await security.get_price()
    await security.buy(10)
    score = await security.get_score()
"""

from datetime import datetime, timedelta
from typing import Optional

from sentinel.broker import Broker
from sentinel.database import Database
from sentinel.settings import Settings

# Duplicate trade protection: skip if traded within this many minutes
TRADE_COOLOFF_MINUTES = 60


class Security:
    """Represents a single security with all its operations."""

    def __init__(self, symbol: str, db=None, broker=None):
        self.symbol = symbol
        self._db = db if db is not None else Database()
        self._broker = broker if broker is not None else Broker()
        self._settings = Settings()
        self._data: Optional[dict] = None
        self._position: Optional[dict] = None

    async def load(self) -> "Security":
        """Load security data from database."""
        self._data = await self._db.get_security(self.symbol)
        self._position = await self._db.get_position(self.symbol)
        return self

    async def exists(self) -> bool:
        """Check if security exists in universe."""
        if self._data is None:
            await self.load()
        return self._data is not None

    # -------------------------------------------------------------------------
    # Properties (from database)
    # -------------------------------------------------------------------------

    @property
    def name(self) -> Optional[str]:
        return self._data.get("name") if self._data else None

    @property
    def currency(self) -> str:
        return self._data.get("currency", "EUR") if self._data else "EUR"

    @property
    def geography(self) -> Optional[str]:
        return self._data.get("geography") if self._data else None

    @property
    def industry(self) -> Optional[str]:
        return self._data.get("industry") if self._data else None

    @property
    def aliases(self) -> Optional[str]:
        return self._data.get("aliases") if self._data else None

    @property
    def min_lot(self) -> int:
        return self._data.get("min_lot", 1) if self._data else 1

    @property
    def active(self) -> bool:
        return bool(self._data.get("active", 1)) if self._data else False

    @property
    def allow_buy(self) -> bool:
        return bool(self._data.get("allow_buy", 1)) if self._data else True

    @property
    def allow_sell(self) -> bool:
        return bool(self._data.get("allow_sell", 1)) if self._data else True

    # -------------------------------------------------------------------------
    # Position
    # -------------------------------------------------------------------------

    @property
    def quantity(self) -> float:
        """Current position quantity."""
        return self._position.get("quantity", 0) if self._position else 0

    @property
    def avg_cost(self) -> Optional[float]:
        """Average cost basis."""
        return self._position.get("avg_cost") if self._position else None

    @property
    def current_price(self) -> Optional[float]:
        """Last known price."""
        return self._position.get("current_price") if self._position else None

    def has_position(self) -> bool:
        """Check if we own this security."""
        return self.quantity > 0

    # -------------------------------------------------------------------------
    # Market Data
    # -------------------------------------------------------------------------

    async def get_price(self) -> Optional[float]:
        """Get current price from broker."""
        quote = await self._broker.get_quote(self.symbol)
        if quote and quote.get("price"):
            # Update cached price in database
            await self._db.upsert_position(self.symbol, current_price=quote["price"], updated_at="now")
            return quote["price"]
        return self.current_price

    async def get_quote(self) -> Optional[dict]:
        """Get full quote from broker."""
        return await self._broker.get_quote(self.symbol)

    async def sync_prices(self, days: int = 365) -> int:
        """Sync historical prices from broker to database."""
        years = max(1, days // 365)
        prices_data = await self._broker.get_historical_prices_bulk([self.symbol], years=years)
        prices = prices_data.get(self.symbol, [])
        if prices:
            await self._db.save_prices(self.symbol, prices)
        return len(prices)

    async def get_historical_prices(
        self,
        days: int | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """Get historical prices from database."""
        return await self._db.get_prices(self.symbol, days=days, end_date=end_date)

    # -------------------------------------------------------------------------
    # Trading
    # -------------------------------------------------------------------------

    async def _has_recent_trade(self) -> bool:
        """Check if there's been a recent trade on this symbol (duplicate protection)."""
        trades = await self._db.get_trades(symbol=self.symbol, limit=1)
        if not trades:
            return False
        last_trade = trades[0]
        executed_at = datetime.fromtimestamp(last_trade["executed_at"])
        cutoff = datetime.now() - timedelta(minutes=TRADE_COOLOFF_MINUTES)
        return executed_at > cutoff

    def _is_asian_market(self) -> bool:
        """Check if this security is on an Asian market (requires limit orders)."""
        return self.symbol.endswith(".AS")

    def _get_quote_data(self) -> Optional[dict]:
        """Get parsed quote data from the security."""
        import json

        if not self._data:
            return None
        quote_str = self._data.get("quote_data")
        if not quote_str:
            return None
        try:
            return json.loads(quote_str)
        except (json.JSONDecodeError, TypeError):
            return None

    def _get_ask_price(self) -> Optional[float]:
        """Get the ask price from quote data (for buy orders)."""
        quote = self._get_quote_data()
        if not quote:
            return None
        return quote.get("ask") or quote.get("bap")

    def _get_bid_price(self) -> Optional[float]:
        """Get the bid price from quote data (for sell orders)."""
        quote = self._get_quote_data()
        if not quote:
            return None
        return quote.get("bid") or quote.get("bbp")

    async def buy(self, quantity: int, auto_convert: bool = True) -> Optional[str]:
        """Buy this security. Returns order ID if successful.

        Args:
            quantity: Number of shares to buy
            auto_convert: If True, automatically converts EUR to target currency if needed
        """
        if not self.allow_buy:
            raise ValueError(f"Buying {self.symbol} is not allowed")

        # Duplicate trade protection
        if await self._has_recent_trade():
            raise ValueError(f"Trade on {self.symbol} already submitted within last {TRADE_COOLOFF_MINUTES} minutes")

        # Round to lot size
        quantity = (quantity // self.min_lot) * self.min_lot
        if quantity < self.min_lot or quantity == 0:
            raise ValueError(f"Quantity must be at least {self.min_lot}")

        # Get price to calculate trade value
        price = await self.get_price()
        if not price or price <= 0:
            raise ValueError(f"Cannot buy {self.symbol}: no valid price")

        trade_value = price * quantity

        # Auto-convert currency if needed and enabled
        if auto_convert:
            from sentinel.currency_exchange import CurrencyExchangeService

            fx = CurrencyExchangeService()

            if self.currency != "EUR":
                # Non-EUR purchase: convert EUR to target currency
                converted = await fx.ensure_balance(self.currency, trade_value, source_currency="EUR")
                if not converted:
                    raise ValueError(
                        f"Insufficient {self.currency} balance and auto-conversion failed. "
                        f"Need {trade_value:.2f} {self.currency}"
                    )
            else:
                # EUR purchase: ensure we have enough EUR, convert from other currencies if needed
                balances = await self._db.get_cash_balances()
                eur_balance = balances.get("EUR", 0)

                if eur_balance < trade_value:
                    # Calculate how much EUR we need (with 2% buffer for fees/slippage)
                    needed_eur = (trade_value - eur_balance) * 1.02
                    estimated_eur_from_conversions = 0.0

                    # Get currency converter once (not inside loop)
                    from sentinel.currency import Currency

                    currency_converter = Currency()

                    # Try to convert from other currencies with positive balances
                    # Priority order: USD, GBP, HKD
                    for source_curr in ["USD", "GBP", "HKD"]:
                        if needed_eur <= estimated_eur_from_conversions:
                            break  # We have enough pending conversions

                        source_balance = balances.get(source_curr, 0)
                        if source_balance <= 0:
                            continue

                        # Calculate how much of this currency we need to convert
                        rate = await currency_converter.get_rate(source_curr)  # rate = 1 source_curr in EUR

                        if rate <= 0:
                            continue

                        # How much EUR can we get from this currency?
                        max_eur_from_source = source_balance * rate
                        still_needed = needed_eur - estimated_eur_from_conversions

                        if max_eur_from_source <= still_needed:
                            # Convert all of this currency
                            convert_amount = source_balance
                            eur_gained = max_eur_from_source
                        else:
                            # Convert only what we need
                            convert_amount = still_needed / rate
                            eur_gained = still_needed

                        # Execute conversion
                        result = await fx.exchange(source_curr, "EUR", convert_amount)
                        if result:
                            estimated_eur_from_conversions += eur_gained

                    # Check if we have enough (current + pending conversions)
                    total_expected_eur = eur_balance + estimated_eur_from_conversions
                    if total_expected_eur < trade_value:
                        raise ValueError(
                            f"Insufficient EUR balance. Have {eur_balance:.2f} EUR + "
                            f"{estimated_eur_from_conversions:.2f} EUR pending from conversions = "
                            f"{total_expected_eur:.2f} EUR, but need {trade_value:.2f} EUR."
                        )

        # For Asian markets, use limit order at ask price (market orders not supported)
        limit_price = None
        if self._is_asian_market():
            limit_price = self._get_ask_price()
            if not limit_price:
                raise ValueError(f"Cannot buy {self.symbol}: no ask price available for limit order")

        order_id = await self._broker.buy(self.symbol, quantity, price=limit_price)
        # Note: Trades are synced from broker, not recorded locally
        return order_id

    async def sell(self, quantity: int) -> Optional[str]:
        """Sell this security. Returns order ID if successful."""
        if not self.allow_sell:
            raise ValueError(f"Selling {self.symbol} is not allowed")

        # Duplicate trade protection
        if await self._has_recent_trade():
            raise ValueError(f"Trade on {self.symbol} already submitted within last {TRADE_COOLOFF_MINUTES} minutes")

        if quantity > self.quantity:
            raise ValueError(f"Cannot sell {quantity}, only own {self.quantity}")

        # Round to lot size
        quantity = (quantity // self.min_lot) * self.min_lot
        if quantity < self.min_lot or quantity == 0:
            raise ValueError(f"Quantity must be at least {self.min_lot}")

        # For Asian markets, use limit order at bid price (market orders not supported)
        limit_price = None
        if self._is_asian_market():
            limit_price = self._get_bid_price()
            if not limit_price:
                raise ValueError(f"Cannot sell {self.symbol}: no bid price available for limit order")

        order_id = await self._broker.sell(self.symbol, quantity, price=limit_price)
        # Note: Trades are synced from broker, not recorded locally
        return order_id

    # -------------------------------------------------------------------------
    # Scoring
    # -------------------------------------------------------------------------

    async def get_score(self) -> Optional[float]:
        """Get the calculated score for this security."""
        return await self._db.get_score(self.symbol)

    async def set_score(self, score: float, components: dict | None = None) -> None:
        """Set the calculated score for this security."""
        import json
        import time

        await self._db.conn.execute(
            """INSERT INTO scores (symbol, score, components, calculated_at)
               VALUES (?, ?, ?, ?)""",
            (self.symbol, score, json.dumps(components) if components else None, int(time.time())),
        )
        await self._db.conn.commit()

    # -------------------------------------------------------------------------
    # Management
    # -------------------------------------------------------------------------

    async def save(self, **data) -> None:
        """Update security data."""
        await self._db.upsert_security(self.symbol, **data)
        self._data = await self._db.get_security(self.symbol)

    async def get_trades(self, limit: int = 50) -> list[dict]:
        """Get trade history for this security."""
        return await self._db.get_trades(symbol=self.symbol, limit=limit)
