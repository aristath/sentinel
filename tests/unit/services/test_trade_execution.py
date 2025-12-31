"""Tests for trade_execution_service module - validates trade safety checks.

These tests ensure trades are validated correctly before execution.
Wrong validation could cause trades that shouldn't happen (or block ones that should).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import Recommendation
from app.modules.trading.services.trade_execution_service import TradeExecutionService


class TestTradeValidation:
    """Tests for trade validation logic.

    The trade execution service validates:
    - Broker connection before trading
    - Sufficient currency balance for BUY orders
    - Sufficient position quantity for SELL orders

    Bug this catches: Invalid trades getting through could cause
    real financial losses or broker errors.
    """

    @pytest.fixture
    def mock_trade_repo(self):
        """Create mock trade repository."""
        repo = AsyncMock()
        repo.create = AsyncMock()
        repo.has_recent_sell_order = AsyncMock(return_value=False)
        repo.exists = AsyncMock(return_value=False)
        repo.get_recently_bought_symbols = AsyncMock(return_value=set())
        # Mock database for pending order check
        repo._db = AsyncMock()
        repo._db.fetchone = AsyncMock(return_value=None)  # No recent orders
        return repo

    @pytest.fixture
    def mock_position_repo(self):
        """Create mock position repository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_stock_repo(self):
        """Create mock stock repository."""
        repo = AsyncMock()
        repo.get_by_symbol = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def mock_client(self):
        """Create mock Tradernet client."""
        client = MagicMock()
        client.is_connected = True
        client.connect.return_value = True
        client.has_pending_order_for_symbol = MagicMock(return_value=False)

        # Simulate successful order
        order_result = MagicMock()
        order_result.order_id = "12345"
        order_result.price = 100.0
        client.place_order.return_value = order_result

        return client

    @pytest.fixture
    def mock_currency_exchange_service(self):
        """Create mock currency exchange service."""
        from app.shared.services import CurrencyExchangeService

        service = MagicMock(spec=CurrencyExchangeService)
        return service

    @pytest.fixture
    def mock_exchange_rate_service(self):
        """Create mock exchange rate service."""
        from app.domain.services.exchange_rate_service import ExchangeRateService

        service = MagicMock(spec=ExchangeRateService)
        service.get_rate = AsyncMock(return_value=1.0)
        return service

    def _make_trade(
        self,
        symbol: str = "TEST",
        side: str = "BUY",
        quantity: float = 10,
        price: float = 100,
        currency: str = "EUR",
    ) -> Recommendation:
        """Helper to create test trades."""
        from app.domain.value_objects.trade_side import TradeSide
        from app.shared.domain.value_objects.currency import Currency

        return Recommendation(
            symbol=symbol,
            name="Test Stock",
            side=TradeSide(side),
            quantity=quantity,
            estimated_price=price,
            estimated_value=quantity * price,
            reason="Test",
            country="United States",
            currency=Currency(currency),
        )

    @pytest.mark.asyncio
    async def test_buy_blocked_when_insufficient_balance(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_client,
        mock_currency_exchange_service,
        mock_exchange_rate_service,
    ):
        """BUY order should be skipped if insufficient currency balance.

        Bug caught: Attempting trades without enough money.
        """
        service = TradeExecutionService(
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            tradernet_client=mock_client,
            currency_exchange_service=mock_currency_exchange_service,
            exchange_rate_service=mock_exchange_rate_service,
        )

        trade = self._make_trade(side="BUY", quantity=10, price=100, currency="EUR")

        # Only 500 EUR available, need 1000
        currency_balances = {"EUR": 500}

        results = await service.execute_trades(
            [trade], currency_balances=currency_balances
        )

        assert len(results) == 1
        assert results[0]["status"] == "skipped"
        assert "Insufficient EUR balance" in results[0]["error"]

        # Should NOT have placed order
        mock_client.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_blocked_when_negative_balance(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_client,
        mock_currency_exchange_service,
        mock_exchange_rate_service,
    ):
        """BUY order should be blocked if currency balance is negative.

        Bug caught: Attempting trades when balance is already negative.
        """
        service = TradeExecutionService(
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            tradernet_client=mock_client,
            currency_exchange_service=mock_currency_exchange_service,
            exchange_rate_service=mock_exchange_rate_service,
        )

        trade = self._make_trade(side="BUY", quantity=10, price=100, currency="USD")

        # Negative USD balance
        currency_balances = {"USD": -556.21}

        results = await service.execute_trades(
            [trade], currency_balances=currency_balances
        )

        assert len(results) == 1
        assert results[0]["status"] == "blocked"
        assert "Negative USD balance" in results[0]["error"]

        # Should NOT have placed order
        mock_client.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_allowed_when_sufficient_balance(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_client,
        mock_currency_exchange_service,
        mock_exchange_rate_service,
    ):
        """BUY order should proceed if sufficient currency balance.

        Bug caught: Valid trades being blocked.
        """
        service = TradeExecutionService(
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            tradernet_client=mock_client,
            currency_exchange_service=mock_currency_exchange_service,
            exchange_rate_service=mock_exchange_rate_service,
        )

        trade = self._make_trade(side="BUY", quantity=10, price=100, currency="EUR")

        # 1500 EUR available, need 1000
        currency_balances = {"EUR": 1500}

        results = await service.execute_trades(
            [trade], currency_balances=currency_balances
        )

        assert len(results) == 1
        assert results[0]["status"] == "success"

        # Should have placed order
        mock_client.place_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_sell_blocked_when_no_position(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_client,
        mock_currency_exchange_service,
        mock_exchange_rate_service,
    ):
        """SELL order should be skipped if no position exists.

        Bug caught: Trying to sell shares we don't own.
        """
        # No position exists
        mock_position_repo.get_by_symbol.return_value = None

        service = TradeExecutionService(
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            tradernet_client=mock_client,
            currency_exchange_service=mock_currency_exchange_service,
            exchange_rate_service=mock_exchange_rate_service,
        )

        trade = self._make_trade(side="SELL", quantity=10)

        results = await service.execute_trades([trade])

        assert len(results) == 1
        assert results[0]["status"] == "skipped"
        assert "No position found" in results[0]["error"]

        mock_client.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_sell_blocked_when_quantity_exceeds_position(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_client,
        mock_currency_exchange_service,
        mock_exchange_rate_service,
    ):
        """SELL order should be skipped if quantity > position.

        Bug caught: Trying to sell more shares than we own.
        """
        # Position has only 5 shares
        position = MagicMock()
        position.quantity = 5
        mock_position_repo.get_by_symbol.return_value = position

        service = TradeExecutionService(
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            tradernet_client=mock_client,
            currency_exchange_service=mock_currency_exchange_service,
            exchange_rate_service=mock_exchange_rate_service,
        )

        # Trying to sell 10 shares
        trade = self._make_trade(side="SELL", quantity=10)

        results = await service.execute_trades([trade])

        assert len(results) == 1
        assert results[0]["status"] == "skipped"
        assert "exceeds position" in results[0]["error"]

        mock_client.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_sell_allowed_when_quantity_within_position(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_client,
        mock_currency_exchange_service,
        mock_exchange_rate_service,
    ):
        """SELL order should proceed if quantity <= position.

        Bug caught: Valid sells being blocked.
        """
        # Position has 20 shares
        position = MagicMock()
        position.quantity = 20
        mock_position_repo.get_by_symbol.return_value = position

        service = TradeExecutionService(
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            tradernet_client=mock_client,
            currency_exchange_service=mock_currency_exchange_service,
            exchange_rate_service=mock_exchange_rate_service,
        )

        # Selling 10 of 20 shares
        trade = self._make_trade(side="SELL", quantity=10)

        results = await service.execute_trades([trade])

        assert len(results) == 1
        assert results[0]["status"] == "success"

        mock_client.place_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_broker_connection_failure_raises_error(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_currency_exchange_service,
        mock_exchange_rate_service,
    ):
        """Should raise error if broker connection fails.

        Bug caught: Trading without broker connection.
        """
        mock_client = MagicMock()
        mock_client.is_connected = False
        mock_client.connect.return_value = False

        service = TradeExecutionService(
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            tradernet_client=mock_client,
            currency_exchange_service=mock_currency_exchange_service,
            exchange_rate_service=mock_exchange_rate_service,
        )

        trade = self._make_trade()

        with pytest.raises(ConnectionError):
            await service.execute_trades([trade])

    @pytest.mark.asyncio
    async def test_multi_currency_validation(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_client,
        mock_currency_exchange_service,
        mock_exchange_rate_service,
    ):
        """Should validate each trade against correct currency balance.

        Bug caught: Using wrong currency for validation.
        """
        service = TradeExecutionService(
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            tradernet_client=mock_client,
            currency_exchange_service=mock_currency_exchange_service,
            exchange_rate_service=mock_exchange_rate_service,
        )

        trades = [
            self._make_trade(
                symbol="EUR_STOCK", quantity=10, price=100, currency="EUR"
            ),
            self._make_trade(
                symbol="USD_STOCK", quantity=10, price=100, currency="USD"
            ),
        ]

        # Enough EUR but not enough USD
        currency_balances = {"EUR": 2000, "USD": 500}

        results = await service.execute_trades(
            trades, currency_balances=currency_balances
        )

        # EUR trade should succeed
        assert results[0]["status"] == "success"
        # USD trade should be skipped
        assert results[1]["status"] == "skipped"
        assert "USD" in results[1]["error"]

    @pytest.mark.asyncio
    async def test_order_failure_recorded(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_client,
        mock_currency_exchange_service,
        mock_exchange_rate_service,
    ):
        """Failed order should be recorded in results.

        Bug caught: Silent failures not being reported.
        """
        mock_client.place_order.return_value = None  # Simulate failure

        service = TradeExecutionService(
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            tradernet_client=mock_client,
            currency_exchange_service=mock_currency_exchange_service,
            exchange_rate_service=mock_exchange_rate_service,
        )

        trade = self._make_trade()

        results = await service.execute_trades([trade])

        assert len(results) == 1
        assert results[0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_no_validation_without_currency_balances(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_client,
        mock_currency_exchange_service,
        mock_exchange_rate_service,
    ):
        """BUY should proceed without validation if no balances provided.

        This allows for cases where balance checking is done elsewhere.

        Bug caught: Blocking all trades when balance info unavailable.
        """
        service = TradeExecutionService(
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            tradernet_client=mock_client,
            currency_exchange_service=mock_currency_exchange_service,
            exchange_rate_service=mock_exchange_rate_service,
        )

        trade = self._make_trade(side="BUY")

        # No currency_balances provided
        results = await service.execute_trades([trade], currency_balances=None)

        assert results[0]["status"] == "success"
        mock_client.place_order.assert_called_once()

        # Verify order was stored immediately
        mock_trade_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_sell_blocked_when_recent_order_in_database(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_client,
        mock_currency_exchange_service,
        mock_exchange_rate_service,
    ):
        """SELL order should be blocked if recent sell order exists in database.

        Bug caught: Duplicate sell orders being submitted.
        """
        # Position exists
        position = MagicMock()
        position.quantity = 20
        mock_position_repo.get_by_symbol.return_value = position

        # Recent sell order exists in database (mocked via _db.fetchone)
        # The _check_pending_orders function checks the database for recent orders
        mock_trade_repo._db.fetchone = AsyncMock(
            return_value={"1": 1}
        )  # Return a row to indicate recent order

        service = TradeExecutionService(
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            tradernet_client=mock_client,
            currency_exchange_service=mock_currency_exchange_service,
            exchange_rate_service=mock_exchange_rate_service,
        )

        trade = self._make_trade(side="SELL", quantity=10)

        results = await service.execute_trades([trade])

        assert len(results) == 1
        assert results[0]["status"] == "blocked"
        assert "Pending order already exists" in results[0]["error"]

        # Should NOT have placed order
        mock_client.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_order_stored_immediately_after_placement(
        self,
        mock_trade_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_client,
        mock_currency_exchange_service,
        mock_exchange_rate_service,
    ):
        """Order should be stored in database immediately after successful placement.

        Bug caught: Orders not being tracked locally, causing duplicates.
        """
        service = TradeExecutionService(
            trade_repo=mock_trade_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            tradernet_client=mock_client,
            currency_exchange_service=mock_currency_exchange_service,
            exchange_rate_service=mock_exchange_rate_service,
        )

        trade = self._make_trade(side="BUY")

        results = await service.execute_trades([trade], currency_balances={"EUR": 2000})

        assert len(results) == 1
        assert results[0]["status"] == "success"

        # Verify order was stored immediately
        mock_trade_repo.create.assert_called_once()

        # Verify the stored trade has correct order_id
        call_args = mock_trade_repo.create.call_args[0][0]
        assert call_args.order_id == "12345"
        assert call_args.symbol == "TEST"
        assert call_args.side == "BUY"
