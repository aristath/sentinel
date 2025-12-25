"""Tests for trade_execution_service module - validates trade safety checks.

These tests ensure trades are validated correctly before execution.
Wrong validation could cause trades that shouldn't happen (or block ones that should).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.application.services.trade_execution_service import TradeExecutionService
from app.domain.models import Recommendation


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
        return repo

    @pytest.fixture
    def mock_position_repo(self):
        """Create mock position repository."""
        repo = AsyncMock()
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

    def _make_trade(
        self,
        symbol: str = "TEST",
        side: str = "BUY",
        quantity: float = 10,
        price: float = 100,
        currency: str = "EUR",
    ) -> Recommendation:
        """Helper to create test trades."""
        return Recommendation(
            symbol=symbol,
            name="Test Stock",
            side=side,
            quantity=quantity,
            estimated_price=price,
            estimated_value=quantity * price,
            reason="Test",
            geography="US",
            currency=currency,
        )

    @pytest.mark.asyncio
    async def test_buy_blocked_when_insufficient_balance(
        self, mock_trade_repo, mock_position_repo, mock_client
    ):
        """BUY order should be skipped if insufficient currency balance.

        Bug caught: Attempting trades without enough money.
        """
        with patch(
            "app.application.services.trade_execution_service.get_tradernet_client",
            return_value=mock_client
        ):
            service = TradeExecutionService(
                mock_trade_repo,
                position_repo=mock_position_repo
            )

            trade = self._make_trade(
                side="BUY",
                quantity=10,
                price=100,
                currency="EUR"
            )

            # Only 500 EUR available, need 1000
            currency_balances = {"EUR": 500}

            results = await service.execute_trades(
                [trade],
                currency_balances=currency_balances
            )

            assert len(results) == 1
            assert results[0]["status"] == "skipped"
            assert "Insufficient EUR balance" in results[0]["error"]

            # Should NOT have placed order
            mock_client.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_buy_allowed_when_sufficient_balance(
        self, mock_trade_repo, mock_position_repo, mock_client
    ):
        """BUY order should proceed if sufficient currency balance.

        Bug caught: Valid trades being blocked.
        """
        with patch(
            "app.application.services.trade_execution_service.get_tradernet_client",
            return_value=mock_client
        ):
            service = TradeExecutionService(
                mock_trade_repo,
                position_repo=mock_position_repo
            )

            trade = self._make_trade(
                side="BUY",
                quantity=10,
                price=100,
                currency="EUR"
            )

            # 1500 EUR available, need 1000
            currency_balances = {"EUR": 1500}

            results = await service.execute_trades(
                [trade],
                currency_balances=currency_balances
            )

            assert len(results) == 1
            assert results[0]["status"] == "success"

            # Should have placed order
            mock_client.place_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_sell_blocked_when_no_position(
        self, mock_trade_repo, mock_position_repo, mock_client
    ):
        """SELL order should be skipped if no position exists.

        Bug caught: Trying to sell shares we don't own.
        """
        with patch(
            "app.application.services.trade_execution_service.get_tradernet_client",
            return_value=mock_client
        ):
            # No position exists
            mock_position_repo.get_by_symbol.return_value = None

            service = TradeExecutionService(
                mock_trade_repo,
                position_repo=mock_position_repo
            )

            trade = self._make_trade(side="SELL", quantity=10)

            results = await service.execute_trades([trade])

            assert len(results) == 1
            assert results[0]["status"] == "skipped"
            assert "No position found" in results[0]["error"]

            mock_client.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_sell_blocked_when_quantity_exceeds_position(
        self, mock_trade_repo, mock_position_repo, mock_client
    ):
        """SELL order should be skipped if quantity > position.

        Bug caught: Trying to sell more shares than we own.
        """
        with patch(
            "app.application.services.trade_execution_service.get_tradernet_client",
            return_value=mock_client
        ):
            # Position has only 5 shares
            position = MagicMock()
            position.quantity = 5
            mock_position_repo.get_by_symbol.return_value = position

            service = TradeExecutionService(
                mock_trade_repo,
                position_repo=mock_position_repo
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
        self, mock_trade_repo, mock_position_repo, mock_client
    ):
        """SELL order should proceed if quantity <= position.

        Bug caught: Valid sells being blocked.
        """
        with patch(
            "app.application.services.trade_execution_service.get_tradernet_client",
            return_value=mock_client
        ):
            # Position has 20 shares
            position = MagicMock()
            position.quantity = 20
            mock_position_repo.get_by_symbol.return_value = position

            service = TradeExecutionService(
                mock_trade_repo,
                position_repo=mock_position_repo
            )

            # Selling 10 of 20 shares
            trade = self._make_trade(side="SELL", quantity=10)

            results = await service.execute_trades([trade])

            assert len(results) == 1
            assert results[0]["status"] == "success"

            mock_client.place_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_broker_connection_failure_raises_error(
        self, mock_trade_repo, mock_position_repo
    ):
        """Should raise error if broker connection fails.

        Bug caught: Trading without broker connection.
        """
        mock_client = MagicMock()
        mock_client.is_connected = False
        mock_client.connect.return_value = False

        with patch(
            "app.application.services.trade_execution_service.get_tradernet_client",
            return_value=mock_client
        ):
            service = TradeExecutionService(
                mock_trade_repo,
                position_repo=mock_position_repo
            )

            trade = self._make_trade()

            with pytest.raises(ConnectionError):
                await service.execute_trades([trade])

    @pytest.mark.asyncio
    async def test_multi_currency_validation(
        self, mock_trade_repo, mock_position_repo, mock_client
    ):
        """Should validate each trade against correct currency balance.

        Bug caught: Using wrong currency for validation.
        """
        with patch(
            "app.application.services.trade_execution_service.get_tradernet_client",
            return_value=mock_client
        ):
            service = TradeExecutionService(
                mock_trade_repo,
                position_repo=mock_position_repo
            )

            trades = [
                self._make_trade(symbol="EUR_STOCK", quantity=10, price=100, currency="EUR"),
                self._make_trade(symbol="USD_STOCK", quantity=10, price=100, currency="USD"),
            ]

            # Enough EUR but not enough USD
            currency_balances = {"EUR": 2000, "USD": 500}

            results = await service.execute_trades(
                trades,
                currency_balances=currency_balances
            )

            # EUR trade should succeed
            assert results[0]["status"] == "success"
            # USD trade should be skipped
            assert results[1]["status"] == "skipped"
            assert "USD" in results[1]["error"]

    @pytest.mark.asyncio
    async def test_order_failure_recorded(
        self, mock_trade_repo, mock_position_repo, mock_client
    ):
        """Failed order should be recorded in results.

        Bug caught: Silent failures not being reported.
        """
        mock_client.place_order.return_value = None  # Simulate failure

        with patch(
            "app.application.services.trade_execution_service.get_tradernet_client",
            return_value=mock_client
        ):
            service = TradeExecutionService(
                mock_trade_repo,
                position_repo=mock_position_repo
            )

            trade = self._make_trade()

            results = await service.execute_trades([trade])

            assert len(results) == 1
            assert results[0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_no_validation_without_currency_balances(
        self, mock_trade_repo, mock_position_repo, mock_client
    ):
        """BUY should proceed without validation if no balances provided.

        This allows for cases where balance checking is done elsewhere.

        Bug caught: Blocking all trades when balance info unavailable.
        """
        with patch(
            "app.application.services.trade_execution_service.get_tradernet_client",
            return_value=mock_client
        ):
            service = TradeExecutionService(
                mock_trade_repo,
                position_repo=mock_position_repo
            )

            trade = self._make_trade(side="BUY")

            # No currency_balances provided
            results = await service.execute_trades(
                [trade],
                currency_balances=None
            )

            assert results[0]["status"] == "success"
            mock_client.place_order.assert_called_once()
            
            # Verify order was stored immediately
            mock_trade_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_sell_blocked_when_recent_order_in_database(
        self, mock_trade_repo, mock_position_repo, mock_client
    ):
        """SELL order should be blocked if recent sell order exists in database.
        
        Bug caught: Duplicate sell orders being submitted.
        """
        with patch(
            "app.application.services.trade_execution_service.get_tradernet_client",
            return_value=mock_client
        ):
            # Position exists
            position = MagicMock()
            position.quantity = 20
            mock_position_repo.get_by_symbol.return_value = position
            
            # Recent sell order exists in database
            mock_trade_repo.has_recent_sell_order.return_value = True

            service = TradeExecutionService(
                mock_trade_repo,
                position_repo=mock_position_repo
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
        self, mock_trade_repo, mock_position_repo, mock_client
    ):
        """Order should be stored in database immediately after successful placement.
        
        Bug caught: Orders not being tracked locally, causing duplicates.
        """
        with patch(
            "app.application.services.trade_execution_service.get_tradernet_client",
            return_value=mock_client
        ):
            service = TradeExecutionService(
                mock_trade_repo,
                position_repo=mock_position_repo
            )

            trade = self._make_trade(side="BUY")

            results = await service.execute_trades(
                [trade],
                currency_balances={"EUR": 2000}
            )

            assert len(results) == 1
            assert results[0]["status"] == "success"
            
            # Verify order was stored immediately
            mock_trade_repo.create.assert_called_once()
            
            # Verify the stored trade has correct order_id
            call_args = mock_trade_repo.create.call_args[0][0]
            assert call_args.order_id == "12345"
            assert call_args.symbol == "TEST"
            assert call_args.side == "BUY"
