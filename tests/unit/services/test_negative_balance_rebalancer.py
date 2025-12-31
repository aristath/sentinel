"""Tests for negative_balance_rebalancer module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import Stock
from app.modules.rebalancing.services.negative_balance_rebalancer import (
    NegativeBalanceRebalancer,
)
from app.shared.domain.value_objects.currency import Currency


class TestNegativeBalanceRebalancer:
    """Tests for negative balance rebalancer service."""

    @pytest.fixture
    def mock_client(self):
        """Create mock Tradernet client."""
        client = MagicMock()
        client.is_connected = True
        client.connect = MagicMock(return_value=True)
        client.get_cash_balances = MagicMock(return_value=[])
        return client

    @pytest.fixture
    def mock_currency_service(self):
        """Create mock currency exchange service."""
        service = MagicMock()
        service.exchange = MagicMock(return_value=None)
        return service

    @pytest.fixture
    def mock_trade_execution_service(self):
        """Create mock trade execution service."""
        service = MagicMock()
        service.execute_trades = AsyncMock(return_value=[])
        return service

    @pytest.fixture
    def mock_stock_repo(self):
        """Create mock stock repository."""
        repo = AsyncMock()
        repo.get_all_active = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def mock_position_repo(self):
        """Create mock position repository."""
        repo = AsyncMock()
        repo.get_with_stock_info = AsyncMock(return_value=[])
        return repo

    @pytest.fixture
    def mock_exchange_rate_service(self):
        """Create mock exchange rate service."""
        service = AsyncMock()
        service.get_rate = AsyncMock(return_value=1.0)
        return service

    @pytest.fixture
    def mock_recommendation_repo(self):
        """Create mock recommendation repository."""
        repo = AsyncMock()
        repo.create = AsyncMock()
        repo.dismiss_all_by_portfolio_hash = AsyncMock(return_value=0)
        return repo

    @pytest.fixture
    def rebalancer(
        self,
        mock_client,
        mock_currency_service,
        mock_trade_execution_service,
        mock_stock_repo,
        mock_position_repo,
        mock_exchange_rate_service,
        mock_recommendation_repo,
    ):
        """Create rebalancer instance with mocked dependencies."""
        return NegativeBalanceRebalancer(
            mock_client,
            mock_currency_service,
            mock_trade_execution_service,
            mock_stock_repo,
            mock_position_repo,
            mock_exchange_rate_service,
            recommendation_repo=mock_recommendation_repo,
        )

    @pytest.mark.asyncio
    async def test_get_trading_currencies(self, rebalancer, mock_stock_repo):
        """Test getting currencies from active stocks."""
        stocks = [
            Stock(
                symbol="AAPL.US",
                name="Apple Inc",
                currency=Currency.USD,
                active=True,
            ),
            Stock(
                symbol="SAP.DE",
                name="SAP SE",
                currency=Currency.EUR,
                active=True,
            ),
            Stock(
                symbol="700.HK",
                name="Tencent",
                currency=Currency.HKD,
                active=True,
            ),
        ]
        mock_stock_repo.get_all_active.return_value = stocks

        currencies = await rebalancer.get_trading_currencies()

        assert "USD" in currencies
        assert "EUR" in currencies
        assert "HKD" in currencies
        assert len(currencies) == 3

    @pytest.mark.asyncio
    async def test_check_currency_minimums_all_above_minimum(
        self, rebalancer, mock_stock_repo
    ):
        """Test check_currency_minimums when all currencies meet minimum."""
        stocks = [
            Stock(
                symbol="AAPL.US",
                name="Apple Inc",
                currency=Currency.USD,
                active=True,
            ),
        ]
        mock_stock_repo.get_all_active.return_value = stocks

        cash_balances = {"USD": 100.0, "EUR": 50.0}

        shortfalls = await rebalancer.check_currency_minimums(cash_balances)

        assert len(shortfalls) == 0

    @pytest.mark.asyncio
    async def test_check_currency_minimums_below_minimum(
        self, rebalancer, mock_stock_repo
    ):
        """Test check_currency_minimums when currency is below minimum."""
        stocks = [
            Stock(
                symbol="AAPL.US",
                name="Apple Inc",
                currency=Currency.USD,
                active=True,
            ),
        ]
        mock_stock_repo.get_all_active.return_value = stocks

        cash_balances = {"USD": 2.0}  # Below minimum of 5.0

        shortfalls = await rebalancer.check_currency_minimums(cash_balances)

        assert "USD" in shortfalls
        assert shortfalls["USD"] == 3.0  # 5.0 - 2.0

    @pytest.mark.asyncio
    async def test_check_currency_minimums_negative_balance(
        self, rebalancer, mock_stock_repo
    ):
        """Test check_currency_minimums when balance is negative."""
        stocks = [
            Stock(
                symbol="AAPL.US",
                name="Apple Inc",
                currency=Currency.USD,
                active=True,
            ),
        ]
        mock_stock_repo.get_all_active.return_value = stocks

        cash_balances = {"USD": -556.21}

        shortfalls = await rebalancer.check_currency_minimums(cash_balances)

        assert "USD" in shortfalls
        assert shortfalls["USD"] == 561.21  # 5.0 - (-556.21)

    @pytest.mark.asyncio
    async def test_rebalance_negative_balances_no_shortfalls(
        self, rebalancer, mock_client
    ):
        """Test rebalance when all currencies meet minimum."""
        from app.infrastructure.external.tradernet.models import CashBalance

        mock_client.get_cash_balances.return_value = [
            CashBalance(currency="USD", amount=100.0),
            CashBalance(currency="EUR", amount=50.0),
        ]

        result = await rebalancer.rebalance_negative_balances()

        assert result is True
        mock_currency_service = rebalancer._currency_service
        mock_currency_service.exchange.assert_not_called()
