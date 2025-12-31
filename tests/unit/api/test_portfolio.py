"""Tests for portfolio API endpoints.

These tests validate portfolio data retrieval, summary calculations,
and transaction history. Critical for accurate portfolio state display.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


@pytest.fixture
def mock_position_repo():
    """Mock position repository."""
    return AsyncMock()


@pytest.fixture
def mock_stock_repo():
    """Mock stock repository."""
    return AsyncMock()


@pytest.fixture
def mock_portfolio_repo():
    """Mock portfolio repository."""
    return AsyncMock()


@pytest.fixture
def mock_portfolio_service():
    """Mock portfolio service."""
    return AsyncMock()


class TestGetPortfolio:
    """Test the GET /portfolio endpoint."""

    @pytest.mark.asyncio
    async def test_returns_positions_with_stock_info(
        self, mock_position_repo, mock_stock_repo
    ):
        """Test that positions are returned with stock information."""
        from app.modules.portfolio.api.portfolio import get_portfolio

        # Setup mock position
        mock_position = MagicMock()
        mock_position.symbol = "AAPL"
        mock_position.quantity = 10
        mock_position.avg_price = 150.0
        mock_position.current_price = 160.0
        mock_position.currency = "USD"
        mock_position.currency_rate = 1.05
        mock_position.market_value_eur = 1523.81
        mock_position.last_updated = "2024-01-15T10:00:00"

        mock_position_repo.get_all.return_value = [mock_position]

        # Setup mock stock
        mock_stock = MagicMock()
        mock_stock.name = "Apple Inc."
        mock_stock.industry = "Consumer Electronics"
        mock_stock.country = "United States"

        mock_stock_repo.get_by_symbol.return_value = mock_stock

        result = await get_portfolio(mock_position_repo, mock_stock_repo)

        assert len(result) == 1
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["quantity"] == 10
        assert result[0]["stock_name"] == "Apple Inc."
        assert result[0]["industry"] == "Consumer Electronics"

    @pytest.mark.asyncio
    async def test_handles_position_without_stock(
        self, mock_position_repo, mock_stock_repo
    ):
        """Test handling of position without stock info."""
        from app.modules.portfolio.api.portfolio import get_portfolio

        mock_position = MagicMock()
        mock_position.symbol = "UNKNOWN"
        mock_position.quantity = 5
        mock_position.avg_price = 100.0
        mock_position.current_price = 110.0
        mock_position.currency = "USD"
        mock_position.currency_rate = 1.05
        mock_position.market_value_eur = 523.81
        mock_position.last_updated = "2024-01-15T10:00:00"

        mock_position_repo.get_all.return_value = [mock_position]
        mock_stock_repo.get_by_symbol.return_value = None

        result = await get_portfolio(mock_position_repo, mock_stock_repo)

        assert len(result) == 1
        assert result[0]["symbol"] == "UNKNOWN"
        assert "stock_name" not in result[0]

    @pytest.mark.asyncio
    async def test_sorts_by_market_value(self, mock_position_repo, mock_stock_repo):
        """Test that positions are sorted by market value descending."""
        from app.modules.portfolio.api.portfolio import get_portfolio

        # Create positions with different values
        pos1 = MagicMock()
        pos1.symbol = "SMALL"
        pos1.quantity = 10
        pos1.avg_price = 10.0
        pos1.current_price = 10.0
        pos1.currency = "EUR"
        pos1.currency_rate = 1.0
        pos1.market_value_eur = 100.0
        pos1.last_updated = "2024-01-15"

        pos2 = MagicMock()
        pos2.symbol = "LARGE"
        pos2.quantity = 100
        pos2.avg_price = 50.0
        pos2.current_price = 50.0
        pos2.currency = "EUR"
        pos2.currency_rate = 1.0
        pos2.market_value_eur = 5000.0
        pos2.last_updated = "2024-01-15"

        mock_position_repo.get_all.return_value = [pos1, pos2]
        mock_stock_repo.get_by_symbol.return_value = None

        result = await get_portfolio(mock_position_repo, mock_stock_repo)

        # LARGE should come first (higher value)
        assert result[0]["symbol"] == "LARGE"
        assert result[1]["symbol"] == "SMALL"

    @pytest.mark.asyncio
    async def test_handles_empty_portfolio(self, mock_position_repo, mock_stock_repo):
        """Test handling of empty portfolio."""
        from app.modules.portfolio.api.portfolio import get_portfolio

        mock_position_repo.get_all.return_value = []

        result = await get_portfolio(mock_position_repo, mock_stock_repo)

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_none_prices(self, mock_position_repo, mock_stock_repo):
        """Test handling of positions with None prices."""
        from app.modules.portfolio.api.portfolio import get_portfolio

        pos = MagicMock()
        pos.symbol = "TEST"
        pos.quantity = None  # No quantity
        pos.avg_price = None
        pos.current_price = None
        pos.currency = "EUR"
        pos.currency_rate = 1.0
        pos.market_value_eur = 0
        pos.last_updated = "2024-01-15"

        mock_position_repo.get_all.return_value = [pos]
        mock_stock_repo.get_by_symbol.return_value = None

        result = await get_portfolio(mock_position_repo, mock_stock_repo)

        # Should handle None values gracefully
        assert len(result) == 1


class TestGetPortfolioSummary:
    """Test the GET /portfolio/summary endpoint."""

    @pytest.mark.asyncio
    async def test_returns_summary(self, mock_portfolio_service):
        """Test that summary is returned correctly."""
        from app.modules.portfolio.api.portfolio import get_portfolio_summary

        mock_summary = MagicMock()
        mock_summary.total_value = 100000.0
        mock_summary.cash_balance = 5000.0

        # Mock geographic allocations
        mock_eu = MagicMock()
        mock_eu.name = "EU"
        mock_eu.current_pct = 0.30

        mock_asia = MagicMock()
        mock_asia.name = "ASIA"
        mock_asia.current_pct = 0.20

        mock_us = MagicMock()
        mock_us.name = "US"
        mock_us.current_pct = 0.50

        mock_summary.country_allocations = [mock_eu, mock_asia, mock_us]
        mock_portfolio_service.get_portfolio_summary.return_value = mock_summary

        result = await get_portfolio_summary(mock_portfolio_service)

        assert result["total_value"] == 100000.0
        assert result["cash_balance"] == 5000.0
        assert result["allocations"]["EU"] == 30.0  # Converted to percentage
        assert result["allocations"]["ASIA"] == 20.0
        assert result["allocations"]["US"] == 50.0

    @pytest.mark.asyncio
    async def test_handles_missing_geographies(self, mock_portfolio_service):
        """Test handling when some geographies are missing."""
        from app.modules.portfolio.api.portfolio import get_portfolio_summary

        mock_summary = MagicMock()
        mock_summary.total_value = 50000.0
        mock_summary.cash_balance = 2000.0

        # Only US stocks
        mock_us = MagicMock()
        mock_us.name = "US"
        mock_us.current_pct = 1.0

        mock_summary.country_allocations = [mock_us]
        mock_portfolio_service.get_portfolio_summary.return_value = mock_summary

        result = await get_portfolio_summary(mock_portfolio_service)

        assert result["allocations"]["US"] == 100.0
        assert result["allocations"]["EU"] == 0.0
        assert result["allocations"]["ASIA"] == 0.0


class TestGetPortfolioHistory:
    """Test the GET /portfolio/history endpoint."""

    @pytest.mark.asyncio
    async def test_returns_history(self, mock_portfolio_repo):
        """Test that history is returned correctly."""
        from app.modules.portfolio.api.portfolio import get_portfolio_history

        mock_snapshot = MagicMock()
        mock_snapshot.date = "2024-01-15"
        mock_snapshot.total_value = 100000.0
        mock_snapshot.cash_balance = 5000.0
        mock_snapshot.geo_eu_pct = 0.30
        mock_snapshot.geo_asia_pct = 0.20
        mock_snapshot.geo_us_pct = 0.50

        mock_portfolio_repo.get_history.return_value = [mock_snapshot]

        result = await get_portfolio_history(mock_portfolio_repo)

        assert len(result) == 1
        assert result[0]["date"] == "2024-01-15"
        assert result[0]["total_value"] == 100000.0
        assert result[0]["geo_us_pct"] == 0.50

    @pytest.mark.asyncio
    async def test_requests_90_days(self, mock_portfolio_repo):
        """Test that history is requested for 90 days."""
        from app.modules.portfolio.api.portfolio import get_portfolio_history

        mock_portfolio_repo.get_history.return_value = []

        await get_portfolio_history(mock_portfolio_repo)

        mock_portfolio_repo.get_history.assert_called_once_with(days=90)


class TestGetTransactionHistory:
    """Test the GET /portfolio/transactions endpoint."""

    @pytest.mark.asyncio
    async def test_returns_transaction_history(self):
        """Test that transaction history is returned."""
        from app.modules.portfolio.api.portfolio import get_transaction_history

        mock_client = MagicMock()
        mock_client.get_cash_movements.return_value = {
            "total_withdrawals": 5000.0,
            "withdrawals": [
                {"date": "2024-01-10", "amount": 2000.0},
                {"date": "2024-01-05", "amount": 3000.0},
            ],
        }

        with patch(
            "app.api.portfolio.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await get_transaction_history()

        assert result["total_withdrawals"] == 5000.0
        assert len(result["withdrawals"]) == 2
        assert "note" in result  # Note about deposits

    @pytest.mark.asyncio
    async def test_handles_api_error(self):
        """Test handling of API errors."""
        from app.modules.portfolio.api.portfolio import get_transaction_history

        mock_client = MagicMock()
        mock_client.get_cash_movements.side_effect = Exception("API error")

        with patch(
            "app.api.portfolio.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_transaction_history()

        assert exc_info.value.status_code == 500


class TestGetCashBreakdown:
    """Test the GET /portfolio/cash-breakdown endpoint."""

    @pytest.mark.asyncio
    async def test_returns_cash_breakdown(self):
        """Test that cash breakdown is returned."""
        from app.modules.portfolio.api.portfolio import get_cash_breakdown

        mock_client = MagicMock()
        mock_balance = MagicMock()
        mock_balance.currency = "EUR"
        mock_balance.amount = 5000.0
        mock_client.get_cash_balances.return_value = [mock_balance]

        mock_exchange_rate_service = AsyncMock()
        mock_exchange_rate_service.batch_convert_to_eur = AsyncMock(
            return_value={"EUR": 5000.0}
        )

        with patch(
            "app.api.portfolio.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            result = await get_cash_breakdown(mock_exchange_rate_service)

        assert len(result.balances) == 1
        assert result.balances[0].currency == "EUR"
        assert result.total_eur == 5000.0

    @pytest.mark.asyncio
    async def test_handles_no_connection(self):
        """Test handling when Tradernet is not connected."""
        from app.modules.portfolio.api.portfolio import get_cash_breakdown

        mock_exchange_rate_service = AsyncMock()

        with patch(
            "app.api.portfolio.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await get_cash_breakdown(mock_exchange_rate_service)

        assert result.balances == []
        assert result.total_eur == 0

    @pytest.mark.asyncio
    async def test_handles_api_error(self):
        """Test handling of API errors."""
        from app.modules.portfolio.api.portfolio import get_cash_breakdown

        mock_client = MagicMock()
        mock_client.get_cash_balances.side_effect = Exception("API error")

        mock_exchange_rate_service = AsyncMock()

        with patch(
            "app.api.portfolio.ensure_tradernet_connected",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_cash_breakdown(mock_exchange_rate_service)

        assert exc_info.value.status_code == 500


class TestGetPortfolioAnalytics:
    """Test the GET /portfolio/analytics endpoint."""

    @pytest.mark.asyncio
    async def test_returns_analytics(self):
        """Test that analytics are returned."""
        import pandas as pd

        from app.modules.portfolio.api.portfolio import get_portfolio_analytics

        mock_values = pd.Series([100, 101, 102])
        mock_returns = pd.Series(
            [0.01, 0.0099], index=pd.date_range("2024-01-01", periods=2)
        )

        mock_db_manager = MagicMock()
        mock_turnover_tracker = MagicMock()
        mock_turnover_tracker.calculate_annual_turnover = AsyncMock(return_value=0.5)
        mock_turnover_tracker.get_turnover_status = AsyncMock(
            return_value={
                "turnover": 0.5,
                "turnover_display": "50.00%",
                "status": "normal",
                "alert": None,
                "reason": "Normal turnover: 50.00%",
            }
        )

        with patch(
            "app.domain.analytics.reconstruct_portfolio_values",
            new_callable=AsyncMock,
            return_value=mock_values,
        ):
            with patch(
                "app.domain.analytics.calculate_portfolio_returns",
                return_value=mock_returns,
            ):
                with patch(
                    "app.domain.analytics.get_portfolio_metrics",
                    new_callable=AsyncMock,
                    return_value={
                        "annual_return": 0.15,
                        "sharpe_ratio": 1.5,
                        "volatility": 0.12,
                        "max_drawdown": -0.08,
                    },
                ):
                    with patch(
                        "app.domain.analytics.get_performance_attribution",
                        new_callable=AsyncMock,
                        return_value={"country": {}, "industry": {}},
                    ):
                        with patch(
                            "app.api.portfolio.get_db_manager",
                            return_value=mock_db_manager,
                        ):
                            with patch(
                                "app.modules.turnover_tracker.TurnoverTracker",
                                return_value=mock_turnover_tracker,
                            ):
                                result = await get_portfolio_analytics(days=365)

        # Result is a Pydantic model
        assert hasattr(result, "returns")
        assert hasattr(result, "risk_metrics")
        assert hasattr(result, "attribution")
        assert hasattr(result, "period")

    @pytest.mark.asyncio
    async def test_handles_insufficient_data(self):
        """Test handling of insufficient data."""
        import pandas as pd

        from app.modules.portfolio.api.portfolio import get_portfolio_analytics

        with patch(
            "app.domain.analytics.reconstruct_portfolio_values",
            new_callable=AsyncMock,
            return_value=pd.Series(dtype=float),  # Empty series
        ):
            result = await get_portfolio_analytics(days=365)

        # Result is a Pydantic model
        assert hasattr(result, "error")
        assert result.error == "Insufficient data"

    @pytest.mark.asyncio
    async def test_handles_analytics_error(self):
        """Test handling of analytics calculation error."""
        from app.modules.portfolio.api.portfolio import get_portfolio_analytics

        with patch(
            "app.domain.analytics.reconstruct_portfolio_values",
            new_callable=AsyncMock,
            side_effect=Exception("Calculation error"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_portfolio_analytics(days=365)

        assert exc_info.value.status_code == 500
