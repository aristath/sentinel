"""Tests for ticker content service.

These tests validate ticker content generation for the LED display,
including portfolio value, cash balance, and trading recommendations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTickerContentService:
    """Test TickerContentService class."""

    @pytest.fixture
    def mock_portfolio_repo(self):
        """Mock PortfolioRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_position_repo(self):
        """Mock PositionRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_stock_repo(self):
        """Mock StockRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def mock_settings_repo(self):
        """Mock SettingsRepository."""
        repo = AsyncMock()
        repo.get_float = AsyncMock(return_value=1.0)  # Default to showing all
        return repo

    @pytest.fixture
    def mock_allocation_repo(self):
        """Mock AllocationRepository."""
        repo = AsyncMock()
        repo.get_all = AsyncMock(return_value={})
        return repo

    @pytest.fixture
    def mock_tradernet_client(self):
        """Mock TradernetClient."""
        client = MagicMock()
        client.is_connected = True
        client.get_cash_balances.return_value = []
        client.get_pending_orders.return_value = []
        return client

    @pytest.fixture
    def ticker_service(
        self,
        mock_portfolio_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_settings_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Create TickerContentService instance."""
        from app.modules.universe.domain.ticker_content_service import (
            TickerContentService,
        )

        return TickerContentService(
            portfolio_repo=mock_portfolio_repo,
            position_repo=mock_position_repo,
            stock_repo=mock_stock_repo,
            settings_repo=mock_settings_repo,
            allocation_repo=mock_allocation_repo,
            tradernet_client=mock_tradernet_client,
        )

    @pytest.mark.asyncio
    async def test_generate_ticker_text_includes_portfolio_value(
        self, ticker_service, mock_portfolio_repo, mock_settings_repo
    ):
        """Test that portfolio value is included when show_value > 0."""
        from app.domain.models import PortfolioSnapshot

        mock_snapshot = PortfolioSnapshot(
            date="2024-01-01",
            total_value=100000.0,
            cash_balance=10000.0,
        )
        mock_portfolio_repo.get_latest.return_value = mock_snapshot
        mock_settings_repo.get_float.return_value = 1.0  # Show value

        with patch(
            "app.domain.services.ticker_content_service.format_market_status_for_display",
            new_callable=AsyncMock,
        ) as mock_format_status:
            mock_format_status.return_value = "MARKET OPEN"
            with patch(
                "app.domain.services.ticker_content_service.cache"
            ) as mock_cache:
                mock_cache.get.return_value = None  # No recommendations

                result = await ticker_service.generate_ticker_text()

                assert "PORTFOLIO" in result
                assert "100,000" in result or "100000" in result

    @pytest.mark.asyncio
    async def test_generate_ticker_text_includes_cash_balance(
        self, ticker_service, mock_portfolio_repo, mock_settings_repo
    ):
        """Test that cash balance is included when show_cash > 0."""
        from app.domain.models import PortfolioSnapshot

        mock_snapshot = PortfolioSnapshot(
            date="2024-01-01",
            total_value=100000.0,
            cash_balance=10000.0,
        )
        mock_portfolio_repo.get_latest.return_value = mock_snapshot
        mock_settings_repo.get_float.return_value = 1.0  # Show cash

        with patch(
            "app.domain.services.ticker_content_service.format_market_status_for_display",
            new_callable=AsyncMock,
        ) as mock_format_status:
            mock_format_status.return_value = "MARKET OPEN"
            with patch(
                "app.domain.services.ticker_content_service.cache"
            ) as mock_cache:
                mock_cache.get.return_value = None

                result = await ticker_service.generate_ticker_text()

                assert "CASH" in result
                assert "10,000" in result or "10000" in result

    @pytest.mark.asyncio
    async def test_generate_ticker_text_respects_show_value_setting(
        self, ticker_service, mock_portfolio_repo, mock_settings_repo
    ):
        """Test that portfolio value is excluded when show_value is 0."""
        from app.domain.models import PortfolioSnapshot

        mock_snapshot = PortfolioSnapshot(
            date="2024-01-01",
            total_value=100000.0,
            cash_balance=10000.0,
        )
        mock_portfolio_repo.get_latest.return_value = mock_snapshot

        # show_value = 0, show_cash = 1.0
        async def get_float_side_effect(key, default):
            if key == "ticker_show_value":
                return 0.0
            return default

        mock_settings_repo.get_float.side_effect = get_float_side_effect

        with patch(
            "app.domain.services.ticker_content_service.format_market_status_for_display",
            new_callable=AsyncMock,
        ) as mock_format_status:
            mock_format_status.return_value = "MARKET OPEN"
            with patch(
                "app.domain.services.ticker_content_service.cache"
            ) as mock_cache:
                mock_cache.get.return_value = None

                result = await ticker_service.generate_ticker_text()

                assert "PORTFOLIO" not in result

    @pytest.mark.asyncio
    async def test_generate_ticker_text_includes_recommendations(
        self,
        ticker_service,
        mock_portfolio_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_settings_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that recommendations are included when show_actions > 0."""
        from app.domain.models import PortfolioSnapshot

        mock_snapshot = PortfolioSnapshot(
            date="2024-01-01",
            total_value=100000.0,
            cash_balance=10000.0,
        )
        mock_portfolio_repo.get_latest.return_value = mock_snapshot
        mock_position_repo.get_all.return_value = []
        mock_stock_repo.get_all_active.return_value = []

        # Mock settings service
        with patch.object(
            ticker_service._settings_service, "get_settings", new_callable=AsyncMock
        ) as mock_get_settings:
            mock_get_settings.return_value = MagicMock(to_dict=lambda: {})

            with patch(
                "app.domain.services.ticker_content_service.format_market_status_for_display",
                new_callable=AsyncMock,
            ) as mock_format_status:
                mock_format_status.return_value = "MARKET OPEN"

                with patch(
                    "app.domain.services.ticker_content_service.cache"
                ) as mock_cache:
                    # Mock recommendations
                    mock_cache.get.return_value = {
                        "steps": [
                            {
                                "side": "BUY",
                                "symbol": "AAPL.US",
                                "estimated_value": 1000,
                            }
                        ]
                    }

                    result = await ticker_service.generate_ticker_text()

                    assert "BUY" in result
                    assert "AAPL" in result

    @pytest.mark.asyncio
    async def test_generate_ticker_text_respects_show_amounts_setting(
        self,
        ticker_service,
        mock_settings_repo,
        mock_portfolio_repo,
        mock_position_repo,
        mock_stock_repo,
        mock_allocation_repo,
        mock_tradernet_client,
    ):
        """Test that amounts are excluded when show_amounts is 0."""
        from app.domain.models import PortfolioSnapshot

        mock_snapshot = PortfolioSnapshot(
            date="2024-01-01",
            total_value=100000.0,
            cash_balance=10000.0,
        )
        mock_portfolio_repo.get_latest.return_value = mock_snapshot
        mock_position_repo.get_all.return_value = []
        mock_stock_repo.get_all_active.return_value = []

        # show_amounts = 0
        async def get_float_side_effect(key, default):
            if key == "ticker_show_amounts":
                return 0.0
            return 1.0

        mock_settings_repo.get_float.side_effect = get_float_side_effect

        with patch.object(
            ticker_service._settings_service, "get_settings", new_callable=AsyncMock
        ) as mock_get_settings:
            mock_get_settings.return_value = MagicMock(to_dict=lambda: {})

            with patch(
                "app.domain.services.ticker_content_service.format_market_status_for_display",
                new_callable=AsyncMock,
            ) as mock_format_status:
                mock_format_status.return_value = "MARKET OPEN"

                with patch(
                    "app.domain.services.ticker_content_service.cache"
                ) as mock_cache:
                    mock_cache.get.return_value = {
                        "steps": [
                            {
                                "side": "BUY",
                                "symbol": "AAPL.US",
                                "estimated_value": 1000,
                            }
                        ]
                    }

                    result = await ticker_service.generate_ticker_text()

                    # Should have BUY AAPL but not the €1000 amount
                    assert "BUY" in result
                    assert "AAPL" in result
                    assert "1000" not in result

    @pytest.mark.asyncio
    async def test_generate_ticker_text_returns_system_online_when_no_content(
        self, ticker_service, mock_settings_repo, mock_tradernet_client
    ):
        """Test that SYSTEM ONLINE is returned when no content and Tradernet connected."""
        mock_settings_repo.get_float.return_value = 0.0  # Hide everything
        mock_tradernet_client.is_connected = True

        with patch(
            "app.domain.services.ticker_content_service.format_market_status_for_display",
            new_callable=AsyncMock,
        ) as mock_format_status:
            mock_format_status.return_value = ""

            result = await ticker_service.generate_ticker_text()

            assert result == "SYSTEM ONLINE"

    @pytest.mark.asyncio
    async def test_generate_ticker_text_returns_ready_when_not_connected(
        self, ticker_service, mock_settings_repo, mock_tradernet_client
    ):
        """Test that READY is returned when not connected and no content."""
        mock_settings_repo.get_float.return_value = 0.0
        mock_tradernet_client.is_connected = False

        with patch(
            "app.domain.services.ticker_content_service.format_market_status_for_display",
            new_callable=AsyncMock,
        ) as mock_format_status:
            mock_format_status.return_value = ""

            result = await ticker_service.generate_ticker_text()

            assert result == "READY"

    @pytest.mark.asyncio
    async def test_generate_ticker_text_handles_exceptions_gracefully(
        self, ticker_service, mock_settings_repo, mock_tradernet_client
    ):
        """Test that exceptions are handled and system status is returned."""
        mock_settings_repo.get_float.side_effect = Exception("DB Error")
        mock_tradernet_client.is_connected = True

        result = await ticker_service.generate_ticker_text()

        # Should return system status even on error
        assert result == "SYSTEM ONLINE" or result == "READY"

    @pytest.mark.asyncio
    async def test_generate_ticker_text_handles_none_snapshot(
        self, ticker_service, mock_portfolio_repo, mock_settings_repo
    ):
        """Test handling when portfolio snapshot is None."""
        mock_portfolio_repo.get_latest.return_value = None
        mock_settings_repo.get_float.return_value = 1.0

        with patch(
            "app.domain.services.ticker_content_service.format_market_status_for_display",
            new_callable=AsyncMock,
        ) as mock_format_status:
            mock_format_status.return_value = ""
            with patch(
                "app.domain.services.ticker_content_service.cache"
            ) as mock_cache:
                mock_cache.get.return_value = None

                result = await ticker_service.generate_ticker_text()

                # Should handle None gracefully and return system status or empty
                assert isinstance(result, str)
