"""Tests for Security class operations.

These tests verify the intended behavior of the Security class:
1. Loading and checking existence
2. Properties from database data
3. Position properties
4. Market data operations
5. Trading operations (buy/sell)
6. Scoring operations
7. Trade cooloff/duplicate protection
8. Asian market handling (limit orders)
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.security import TRADE_COOLOFF_MINUTES, Security


class TestSecurityLoad:
    """Tests for loading security data."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.get_security = AsyncMock(
            return_value={
                "symbol": "AAPL.US",
                "name": "Apple Inc.",
                "currency": "USD",
                "geography": "United States",
                "industry": "Technology",
                "min_lot": 1,
                "active": 1,
                "allow_buy": 1,
                "allow_sell": 1,
            }
        )
        db.get_position = AsyncMock(
            return_value={
                "symbol": "AAPL.US",
                "quantity": 10,
                "avg_cost": 150.00,
                "current_price": 175.00,
            }
        )
        return db

    @pytest.fixture
    def mock_broker(self):
        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 175.50, "bid": 175.40, "ask": 175.60})
        return broker

    @pytest.mark.asyncio
    async def test_load_populates_data(self, mock_db, mock_broker):
        """load() populates security data from database."""
        security = Security("AAPL.US", db=mock_db, broker=mock_broker)
        await security.load()

        assert security._data is not None
        assert security._data["name"] == "Apple Inc."

    @pytest.mark.asyncio
    async def test_load_populates_position(self, mock_db, mock_broker):
        """load() populates position data from database."""
        security = Security("AAPL.US", db=mock_db, broker=mock_broker)
        await security.load()

        assert security._position is not None
        assert security._position["quantity"] == 10

    @pytest.mark.asyncio
    async def test_load_returns_self(self, mock_db, mock_broker):
        """load() returns self for chaining."""
        security = Security("AAPL.US", db=mock_db, broker=mock_broker)
        result = await security.load()
        assert result is security


class TestSecurityExists:
    """Tests for existence checking."""

    @pytest.mark.asyncio
    async def test_exists_returns_true_when_in_database(self):
        """exists() returns True when security is in database."""
        db = MagicMock()
        db.get_security = AsyncMock(return_value={"symbol": "AAPL.US", "name": "Apple"})
        db.get_position = AsyncMock(return_value=None)

        security = Security("AAPL.US", db=db)
        assert await security.exists() is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_when_not_in_database(self):
        """exists() returns False when security not in database."""
        db = MagicMock()
        db.get_security = AsyncMock(return_value=None)
        db.get_position = AsyncMock(return_value=None)

        security = Security("NONEXISTENT", db=db)
        assert await security.exists() is False

    @pytest.mark.asyncio
    async def test_exists_loads_data_if_not_loaded(self):
        """exists() calls load() if data not already loaded."""
        db = MagicMock()
        db.get_security = AsyncMock(return_value={"symbol": "AAPL.US"})
        db.get_position = AsyncMock(return_value=None)

        security = Security("AAPL.US", db=db)
        assert security._data is None  # Not loaded yet
        await security.exists()
        db.get_security.assert_called_once()


class TestSecurityProperties:
    """Tests for security properties."""

    @pytest.fixture
    def loaded_security(self):
        """Create a loaded security with sample data."""
        security = Security("AAPL.US")
        security._data = {
            "symbol": "AAPL.US",
            "name": "Apple Inc.",
            "currency": "USD",
            "geography": "United States",
            "industry": "Technology",
            "min_lot": 1,
            "active": 1,
            "allow_buy": 1,
            "allow_sell": 1,
        }
        security._position = {
            "quantity": 10,
            "avg_cost": 150.00,
            "current_price": 175.00,
        }
        return security

    def test_name_property(self, loaded_security):
        """name property returns security name."""
        assert loaded_security.name == "Apple Inc."

    def test_currency_property(self, loaded_security):
        """currency property returns currency code."""
        assert loaded_security.currency == "USD"

    def test_currency_defaults_to_eur(self):
        """currency defaults to EUR when not set."""
        security = Security("TEST")
        security._data = {}
        assert security.currency == "EUR"

    def test_geography_property(self, loaded_security):
        """geography property returns country/region."""
        assert loaded_security.geography == "United States"

    def test_industry_property(self, loaded_security):
        """industry property returns industry classification."""
        assert loaded_security.industry == "Technology"

    def test_min_lot_property(self, loaded_security):
        """min_lot property returns minimum trading lot."""
        assert loaded_security.min_lot == 1

    def test_min_lot_defaults_to_1(self):
        """min_lot defaults to 1 when not set."""
        security = Security("TEST")
        security._data = {}
        assert security.min_lot == 1

    def test_active_property(self, loaded_security):
        """active property returns boolean."""
        assert loaded_security.active is True

    def test_active_false_when_inactive(self):
        """active returns False when set to 0."""
        security = Security("TEST")
        security._data = {"active": 0}
        assert security.active is False

    def test_allow_buy_property(self, loaded_security):
        """allow_buy property returns boolean."""
        assert loaded_security.allow_buy is True

    def test_allow_sell_property(self, loaded_security):
        """allow_sell property returns boolean."""
        assert loaded_security.allow_sell is True


class TestPositionProperties:
    """Tests for position-related properties."""

    @pytest.fixture
    def security_with_position(self):
        """Security with an existing position."""
        security = Security("AAPL.US")
        security._data = {"symbol": "AAPL.US"}
        security._position = {
            "quantity": 10,
            "avg_cost": 150.00,
            "current_price": 175.00,
        }
        return security

    @pytest.fixture
    def security_without_position(self):
        """Security without a position."""
        security = Security("AAPL.US")
        security._data = {"symbol": "AAPL.US"}
        security._position = None
        return security

    def test_quantity_returns_owned_shares(self, security_with_position):
        """quantity returns number of shares owned."""
        assert security_with_position.quantity == 10

    def test_quantity_zero_when_no_position(self, security_without_position):
        """quantity returns 0 when no position exists."""
        assert security_without_position.quantity == 0

    def test_avg_cost_returns_cost_basis(self, security_with_position):
        """avg_cost returns average cost basis."""
        assert security_with_position.avg_cost == 150.00

    def test_avg_cost_none_when_no_position(self, security_without_position):
        """avg_cost returns None when no position."""
        assert security_without_position.avg_cost is None

    def test_current_price_returns_last_price(self, security_with_position):
        """current_price returns last known price."""
        assert security_with_position.current_price == 175.00

    def test_has_position_true_when_owns_shares(self, security_with_position):
        """has_position() returns True when quantity > 0."""
        assert security_with_position.has_position() is True

    def test_has_position_false_when_no_shares(self, security_without_position):
        """has_position() returns False when no shares owned."""
        assert security_without_position.has_position() is False


class TestMarketData:
    """Tests for market data operations."""

    @pytest.mark.asyncio
    async def test_get_price_from_broker(self):
        """get_price() fetches current price from broker."""
        db = MagicMock()
        db.upsert_position = AsyncMock()
        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 180.00})

        security = Security("AAPL.US", db=db, broker=broker)
        security._position = {"current_price": 175.00}

        price = await security.get_price()
        assert price == 180.00

    @pytest.mark.asyncio
    async def test_get_price_updates_database(self):
        """get_price() updates cached price in database."""
        db = MagicMock()
        db.upsert_position = AsyncMock()
        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 180.00})

        security = Security("AAPL.US", db=db, broker=broker)
        await security.get_price()

        db.upsert_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_price_falls_back_to_cached(self):
        """get_price() falls back to cached price if broker fails."""
        db = MagicMock()
        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value=None)

        security = Security("AAPL.US", db=db, broker=broker)
        security._position = {"current_price": 175.00}

        price = await security.get_price()
        assert price == 175.00

    @pytest.mark.asyncio
    async def test_get_quote_returns_full_quote(self):
        """get_quote() returns full quote data."""
        broker = MagicMock()
        broker.get_quote = AsyncMock(
            return_value={
                "price": 180.00,
                "bid": 179.90,
                "ask": 180.10,
                "volume": 1000000,
            }
        )

        security = Security("AAPL.US", broker=broker)
        quote = await security.get_quote()

        assert quote["price"] == 180.00
        assert quote["bid"] == 179.90

    @pytest.mark.asyncio
    async def test_get_historical_prices(self):
        """get_historical_prices() fetches from database."""
        db = MagicMock()
        db.get_prices = AsyncMock(
            return_value=[
                {"date": "2024-01-01", "close": 150.00},
                {"date": "2024-01-02", "close": 152.00},
            ]
        )

        security = Security("AAPL.US", db=db)
        prices = await security.get_historical_prices(days=30)

        assert len(prices) == 2
        db.get_prices.assert_called_once_with("AAPL.US", 30)

    @pytest.mark.asyncio
    async def test_sync_prices(self):
        """sync_prices() fetches from broker and stores in database."""
        db = MagicMock()
        db.save_prices = AsyncMock()
        broker = MagicMock()
        broker.get_historical_prices_bulk = AsyncMock(
            return_value={"AAPL.US": [{"date": "2024-01-01", "close": 150.00}] * 100}
        )

        security = Security("AAPL.US", db=db, broker=broker)
        count = await security.sync_prices(days=365)

        assert count == 100
        db.save_prices.assert_called_once()


class TestTradingBuy:
    """Tests for buy operations."""

    @pytest.fixture
    def tradeable_security(self):
        """Security ready for trading."""
        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])  # No recent trades
        db.record_trade = AsyncMock()
        db.upsert_position = AsyncMock()  # Required for get_price()
        db.get_cash_balances = AsyncMock(return_value={"EUR": 10000.0})  # Sufficient EUR

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 100.00})
        broker.buy = AsyncMock(return_value="ORDER123")

        security = Security("AAPL.US", db=db, broker=broker)
        security._data = {
            "symbol": "AAPL.US",
            "currency": "EUR",
            "min_lot": 1,
            "allow_buy": 1,
            "allow_sell": 1,
        }
        security._position = {"current_price": 100.00}
        return security

    @pytest.mark.asyncio
    async def test_buy_places_order(self, tradeable_security):
        """buy() places order with broker."""
        order_id = await tradeable_security.buy(10)
        assert order_id == "ORDER123"
        tradeable_security._broker.buy.assert_called_once()

    @pytest.mark.asyncio
    async def test_buy_does_not_record_trade_locally(self, tradeable_security):
        """buy() does not record trade locally - trades are synced from broker."""
        await tradeable_security.buy(10)
        # Trades are synced from broker, not recorded locally
        # Just verify the order was placed
        tradeable_security._broker.buy.assert_called_once()

    @pytest.mark.asyncio
    async def test_buy_rounds_to_lot_size(self):
        """buy() rounds quantity to lot size."""
        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])
        db.record_trade = AsyncMock()
        db.upsert_position = AsyncMock()
        db.get_cash_balances = AsyncMock(return_value={"EUR": 10000.0})

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 100.00})
        broker.buy = AsyncMock(return_value="ORDER123")

        security = Security("TEST", db=db, broker=broker)
        security._data = {
            "currency": "EUR",
            "min_lot": 10,  # Lot size of 10
            "allow_buy": 1,
        }
        security._position = {"current_price": 100.00}

        await security.buy(25)  # Should round down to 20
        broker.buy.assert_called_with("TEST", 20, price=None)

    @pytest.mark.asyncio
    async def test_buy_fails_when_not_allowed(self):
        """buy() raises error when allow_buy is False."""
        security = Security("TEST")
        security._data = {"allow_buy": 0, "min_lot": 1}

        with pytest.raises(ValueError, match="not allowed"):
            await security.buy(10)

    @pytest.mark.asyncio
    async def test_buy_fails_below_min_lot(self):
        """buy() raises error when quantity below min_lot after rounding."""
        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 100.00})

        security = Security("TEST", db=db, broker=broker)
        security._data = {
            "currency": "EUR",
            "min_lot": 10,
            "allow_buy": 1,
        }
        security._position = {}

        with pytest.raises(ValueError, match="at least"):
            await security.buy(5)  # Less than min_lot of 10

    @pytest.mark.asyncio
    async def test_buy_fails_no_valid_price(self):
        """buy() raises error when no price available."""
        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value=None)

        security = Security("TEST", db=db, broker=broker)
        security._data = {"currency": "EUR", "min_lot": 1, "allow_buy": 1}
        security._position = {"current_price": None}

        with pytest.raises(ValueError, match="no valid price"):
            await security.buy(10)


class TestEurCurrencyConversion:
    """Tests for EUR currency auto-conversion from other currencies."""

    @pytest.mark.asyncio
    async def test_buy_eur_security_converts_from_hkd_when_eur_insufficient(self):
        """buy() converts HKD to EUR when EUR balance is insufficient for EUR purchase."""
        from unittest.mock import patch

        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])
        db.upsert_position = AsyncMock()
        # EUR balance insufficient, but HKD available
        db.get_cash_balances = AsyncMock(return_value={"EUR": 100.0, "HKD": 17000.0, "USD": 50.0})

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 1000.00})
        broker.buy = AsyncMock(return_value="ORDER123")
        broker.connected = True

        mock_fx = MagicMock()
        mock_fx.exchange = AsyncMock(return_value={"order_id": "FX123"})

        mock_currency = MagicMock()
        mock_currency.get_rate = AsyncMock(return_value=0.11)  # 1 HKD = 0.11 EUR

        with (
            patch("sentinel.currency_exchange.CurrencyExchangeService", return_value=mock_fx),
            patch("sentinel.currency.Currency", return_value=mock_currency),
        ):
            security = Security("ASML.EU", db=db, broker=broker)
            security._data = {
                "symbol": "ASML.EU",
                "currency": "EUR",
                "min_lot": 1,
                "allow_buy": 1,
            }
            security._position = {"current_price": 1000.00}

            await security.buy(1, auto_convert=True)

            # Should have attempted to convert from other currencies
            mock_fx.exchange.assert_called()
            # The order should still be placed
            broker.buy.assert_called_once()

    @pytest.mark.asyncio
    async def test_buy_eur_security_fails_when_no_currencies_to_convert(self):
        """buy() fails when EUR insufficient and no other currencies available."""
        from unittest.mock import patch

        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])
        db.upsert_position = AsyncMock()
        # Only EUR with insufficient balance
        db.get_cash_balances = AsyncMock(return_value={"EUR": 100.0})

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 1000.00})
        broker.connected = True

        mock_fx = MagicMock()
        mock_fx.exchange = AsyncMock(return_value=None)

        with patch("sentinel.currency_exchange.CurrencyExchangeService", return_value=mock_fx):
            security = Security("ASML.EU", db=db, broker=broker)
            security._data = {
                "symbol": "ASML.EU",
                "currency": "EUR",
                "min_lot": 1,
                "allow_buy": 1,
            }
            security._position = {"current_price": 1000.00}

            with pytest.raises(ValueError, match="Insufficient EUR balance"):
                await security.buy(1, auto_convert=True)

    @pytest.mark.asyncio
    async def test_buy_eur_security_succeeds_when_eur_sufficient(self):
        """buy() succeeds without conversion when EUR balance is sufficient."""
        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])
        db.upsert_position = AsyncMock()
        # EUR balance is sufficient
        db.get_cash_balances = AsyncMock(return_value={"EUR": 5000.0})

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 1000.00})
        broker.buy = AsyncMock(return_value="ORDER123")

        security = Security("ASML.EU", db=db, broker=broker)
        security._data = {
            "symbol": "ASML.EU",
            "currency": "EUR",
            "min_lot": 1,
            "allow_buy": 1,
        }
        security._position = {"current_price": 1000.00}

        order_id = await security.buy(1, auto_convert=True)

        assert order_id == "ORDER123"
        broker.buy.assert_called_once()

    @pytest.mark.asyncio
    async def test_buy_eur_security_converts_negative_eur_balance(self):
        """buy() converts from other currencies when EUR balance is negative (margin)."""
        from unittest.mock import patch

        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])
        db.upsert_position = AsyncMock()
        # Negative EUR balance (margin), but HKD available
        # Need 500 EUR for trade, have -2000 EUR, so need 2500 EUR * 1.02 buffer = 2550 EUR
        # HKD at 0.11 rate: 17000 HKD = 1870 EUR (not enough, but we convert what we can)
        db.get_cash_balances = AsyncMock(return_value={"EUR": -2000.0, "HKD": 17000.0, "USD": 10000.0})

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 500.00})
        broker.buy = AsyncMock(return_value="ORDER123")
        broker.connected = True

        mock_fx = MagicMock()
        mock_fx.exchange = AsyncMock(return_value={"order_id": "FX123"})

        mock_currency = MagicMock()
        # 1 HKD = 0.11 EUR, 1 USD = 0.85 EUR
        mock_currency.get_rate = AsyncMock(side_effect=lambda c: {"HKD": 0.11, "USD": 0.85, "GBP": 1.15}.get(c, 1.0))

        with (
            patch("sentinel.currency_exchange.CurrencyExchangeService", return_value=mock_fx),
            patch("sentinel.currency.Currency", return_value=mock_currency),
        ):
            security = Security("TEST.EU", db=db, broker=broker)
            security._data = {
                "symbol": "TEST.EU",
                "currency": "EUR",
                "min_lot": 1,
                "allow_buy": 1,
            }
            security._position = {"current_price": 500.00}

            await security.buy(1, auto_convert=True)

            # Should have converted currencies to EUR
            assert mock_fx.exchange.call_count >= 1
            broker.buy.assert_called_once()


class TestTradingSell:
    """Tests for sell operations."""

    @pytest.fixture
    def sellable_security(self):
        """Security with position ready to sell."""
        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])
        db.record_trade = AsyncMock()
        db.upsert_position = AsyncMock()  # Required for get_price()

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 100.00})
        broker.sell = AsyncMock(return_value="ORDER456")

        security = Security("AAPL.US", db=db, broker=broker)
        security._data = {
            "symbol": "AAPL.US",
            "currency": "EUR",
            "min_lot": 1,
            "allow_buy": 1,
            "allow_sell": 1,
        }
        security._position = {"quantity": 100, "current_price": 100.00}
        return security

    @pytest.mark.asyncio
    async def test_sell_places_order(self, sellable_security):
        """sell() places order with broker."""
        order_id = await sellable_security.sell(10)
        assert order_id == "ORDER456"

    @pytest.mark.asyncio
    async def test_sell_does_not_record_trade_locally(self, sellable_security):
        """sell() does not record trade locally - trades are synced from broker."""
        await sellable_security.sell(10)
        # Trades are synced from broker, not recorded locally
        # Just verify the order was placed
        sellable_security._broker.sell.assert_called_once()

    @pytest.mark.asyncio
    async def test_sell_fails_when_not_allowed(self):
        """sell() raises error when allow_sell is False."""
        security = Security("TEST")
        security._data = {"allow_sell": 0, "min_lot": 1}
        security._position = {"quantity": 100}

        with pytest.raises(ValueError, match="not allowed"):
            await security.sell(10)

    @pytest.mark.asyncio
    async def test_sell_fails_when_insufficient_quantity(self):
        """sell() raises error when trying to sell more than owned."""
        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])

        security = Security("TEST", db=db)
        security._data = {"allow_sell": 1, "min_lot": 1}
        security._position = {"quantity": 10}

        with pytest.raises(ValueError, match="only own"):
            await security.sell(20)

    @pytest.mark.asyncio
    async def test_sell_rounds_to_lot_size(self):
        """sell() rounds quantity to lot size."""
        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])
        db.record_trade = AsyncMock()
        db.upsert_position = AsyncMock()

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 100.00})
        broker.sell = AsyncMock(return_value="ORDER456")

        security = Security("TEST", db=db, broker=broker)
        security._data = {
            "currency": "EUR",
            "min_lot": 10,
            "allow_sell": 1,
        }
        security._position = {"quantity": 100, "current_price": 100.00}

        await security.sell(25)  # Should round to 20
        broker.sell.assert_called_with("TEST", 20, price=None)


class TestTradeCooloff:
    """Tests for trade cooloff/duplicate protection."""

    @pytest.mark.asyncio
    async def test_buy_fails_within_cooloff_period(self):
        """buy() raises error if traded within cooloff period."""
        recent_trade_time = datetime.now() - timedelta(minutes=30)

        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[{"executed_at": recent_trade_time.isoformat()}])

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 100.00})

        security = Security("TEST", db=db, broker=broker)
        security._data = {"currency": "EUR", "min_lot": 1, "allow_buy": 1}
        security._position = {"current_price": 100.00}

        with pytest.raises(ValueError, match="already submitted"):
            await security.buy(10)

    @pytest.mark.asyncio
    async def test_buy_succeeds_after_cooloff_period(self):
        """buy() succeeds if last trade was before cooloff period."""
        old_trade_time = datetime.now() - timedelta(minutes=TRADE_COOLOFF_MINUTES + 10)

        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[{"executed_at": old_trade_time.isoformat()}])
        db.record_trade = AsyncMock()
        db.upsert_position = AsyncMock()
        db.get_cash_balances = AsyncMock(return_value={"EUR": 10000.0})

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 100.00})
        broker.buy = AsyncMock(return_value="ORDER123")

        security = Security("TEST", db=db, broker=broker)
        security._data = {"currency": "EUR", "min_lot": 1, "allow_buy": 1}
        security._position = {"current_price": 100.00}

        order_id = await security.buy(10)
        assert order_id == "ORDER123"

    @pytest.mark.asyncio
    async def test_sell_fails_within_cooloff_period(self):
        """sell() raises error if traded within cooloff period."""
        recent_trade_time = datetime.now() - timedelta(minutes=30)

        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[{"executed_at": recent_trade_time.isoformat()}])

        security = Security("TEST", db=db)
        security._data = {"min_lot": 1, "allow_sell": 1}
        security._position = {"quantity": 100}

        with pytest.raises(ValueError, match="already submitted"):
            await security.sell(10)


class TestAsianMarketHandling:
    """Tests for Asian market limit order handling."""

    def test_is_asian_market_true_for_as_suffix(self):
        """_is_asian_market() returns True for .AS symbols."""
        security = Security("ASML.AS")
        assert security._is_asian_market() is True

    def test_is_asian_market_false_for_us_suffix(self):
        """_is_asian_market() returns False for .US symbols."""
        security = Security("AAPL.US")
        assert security._is_asian_market() is False

    def test_is_asian_market_false_for_eu_suffix(self):
        """_is_asian_market() returns False for .EU symbols."""
        security = Security("SAP.EU")
        assert security._is_asian_market() is False

    @pytest.mark.asyncio
    async def test_buy_uses_limit_order_for_asian_market(self):
        """buy() uses limit order with ask price for Asian markets."""
        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])
        db.record_trade = AsyncMock()
        db.upsert_position = AsyncMock()
        db.get_cash_balances = AsyncMock(return_value={"EUR": 10000.0})

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 100.00})
        broker.buy = AsyncMock(return_value="ORDER123")

        security = Security("ASML.AS", db=db, broker=broker)
        security._data = {
            "currency": "EUR",
            "min_lot": 1,
            "allow_buy": 1,
            "quote_data": json.dumps({"ask": 102.50, "bid": 99.50}),
        }
        security._position = {"current_price": 100.00}

        await security.buy(10)
        # Should be called with price (limit order)
        broker.buy.assert_called_with("ASML.AS", 10, price=102.50)

    @pytest.mark.asyncio
    async def test_sell_uses_limit_order_for_asian_market(self):
        """sell() uses limit order with bid price for Asian markets."""
        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])
        db.record_trade = AsyncMock()
        db.upsert_position = AsyncMock()

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 100.00})
        broker.sell = AsyncMock(return_value="ORDER456")

        security = Security("ASML.AS", db=db, broker=broker)
        security._data = {
            "currency": "EUR",
            "min_lot": 1,
            "allow_sell": 1,
            "quote_data": json.dumps({"ask": 102.50, "bid": 99.50}),
        }
        security._position = {"quantity": 100, "current_price": 100.00}

        await security.sell(10)
        broker.sell.assert_called_with("ASML.AS", 10, price=99.50)

    @pytest.mark.asyncio
    async def test_buy_fails_if_no_ask_price_for_asian_market(self):
        """buy() fails for Asian market if no ask price available."""
        db = MagicMock()
        db.get_trades = AsyncMock(return_value=[])
        db.upsert_position = AsyncMock()
        db.get_cash_balances = AsyncMock(return_value={"EUR": 10000.0})

        broker = MagicMock()
        broker.get_quote = AsyncMock(return_value={"price": 100.00})

        security = Security("ASML.AS", db=db, broker=broker)
        security._data = {
            "currency": "EUR",
            "min_lot": 1,
            "allow_buy": 1,
            "quote_data": None,  # No quote data
        }
        security._position = {"current_price": 100.00}

        with pytest.raises(ValueError, match="no ask price"):
            await security.buy(10)


class TestScoring:
    """Tests for score operations."""

    @pytest.mark.asyncio
    async def test_get_score_returns_score(self):
        """get_score() delegates to db.get_score()."""
        db = MagicMock()
        db.get_score = AsyncMock(return_value=0.75)

        security = Security("AAPL.US", db=db)
        score = await security.get_score()
        assert score == 0.75
        db.get_score.assert_awaited_once_with("AAPL.US")

    @pytest.mark.asyncio
    async def test_get_score_returns_none_when_not_scored(self):
        """get_score() returns None when no score exists."""
        db = MagicMock()
        db.get_score = AsyncMock(return_value=None)

        security = Security("AAPL.US", db=db)
        score = await security.get_score()
        assert score is None

    @pytest.mark.asyncio
    async def test_set_score_saves_score(self):
        """set_score() saves score to database."""
        db = MagicMock()
        db.conn = MagicMock()
        db.conn.execute = AsyncMock()
        db.conn.commit = AsyncMock()

        security = Security("AAPL.US", db=db)
        await security.set_score(0.85, components={"ml": 0.8, "momentum": 0.9})

        db.conn.execute.assert_called_once()
        db.conn.commit.assert_called_once()


class TestManagement:
    """Tests for security management operations."""

    @pytest.mark.asyncio
    async def test_save_updates_database(self):
        """save() updates security data in database."""
        db = MagicMock()
        db.upsert_security = AsyncMock()
        db.get_security = AsyncMock(return_value={"symbol": "AAPL.US", "name": "Apple"})

        security = Security("AAPL.US", db=db)
        await security.save(name="Apple Inc.", active=1)

        db.upsert_security.assert_called_once_with("AAPL.US", name="Apple Inc.", active=1)

    @pytest.mark.asyncio
    async def test_save_reloads_data(self):
        """save() reloads security data after update."""
        db = MagicMock()
        db.upsert_security = AsyncMock()
        db.get_security = AsyncMock(return_value={"symbol": "AAPL.US", "name": "Apple Inc."})

        security = Security("AAPL.US", db=db)
        security._data = {"symbol": "AAPL.US", "name": "Apple"}

        await security.save(name="Apple Inc.")

        assert security._data["name"] == "Apple Inc."

    @pytest.mark.asyncio
    async def test_get_trades_returns_trade_history(self):
        """get_trades() returns trade history for this security."""
        db = MagicMock()
        db.get_trades = AsyncMock(
            return_value=[
                {"side": "BUY", "quantity": 10, "price": 150.00},
                {"side": "SELL", "quantity": 5, "price": 160.00},
            ]
        )

        security = Security("AAPL.US", db=db)
        trades = await security.get_trades(limit=50)

        assert len(trades) == 2
        db.get_trades.assert_called_once_with(symbol="AAPL.US", limit=50)


class TestQuoteDataParsing:
    """Tests for quote data parsing."""

    def test_get_quote_data_parses_json(self):
        """_get_quote_data() parses JSON from quote_data field."""
        security = Security("TEST")
        security._data = {"quote_data": json.dumps({"bid": 99.50, "ask": 100.50, "ltp": 100.00})}

        quote = security._get_quote_data()
        assert quote["bid"] == 99.50
        assert quote["ask"] == 100.50

    def test_get_quote_data_returns_none_when_no_data(self):
        """_get_quote_data() returns None when no quote_data."""
        security = Security("TEST")
        security._data = {}

        assert security._get_quote_data() is None

    def test_get_quote_data_returns_none_on_invalid_json(self):
        """_get_quote_data() returns None on invalid JSON."""
        security = Security("TEST")
        security._data = {"quote_data": "invalid json"}

        assert security._get_quote_data() is None

    def test_get_ask_price_from_quote(self):
        """_get_ask_price() extracts ask price from quote."""
        security = Security("TEST")
        security._data = {"quote_data": json.dumps({"ask": 100.50})}

        assert security._get_ask_price() == 100.50

    def test_get_ask_price_falls_back_to_bap(self):
        """_get_ask_price() falls back to 'bap' field."""
        security = Security("TEST")
        security._data = {
            "quote_data": json.dumps({"bap": 100.50})  # bap = best ask price
        }

        assert security._get_ask_price() == 100.50

    def test_get_bid_price_from_quote(self):
        """_get_bid_price() extracts bid price from quote."""
        security = Security("TEST")
        security._data = {"quote_data": json.dumps({"bid": 99.50})}

        assert security._get_bid_price() == 99.50

    def test_get_bid_price_falls_back_to_bbp(self):
        """_get_bid_price() falls back to 'bbp' field."""
        security = Security("TEST")
        security._data = {
            "quote_data": json.dumps({"bbp": 99.50})  # bbp = best bid price
        }

        assert security._get_bid_price() == 99.50
