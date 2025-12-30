"""Tests for stock setup service.

These tests validate stock setup functionality, including identifier resolution,
data fetching from Tradernet and Yahoo Finance, and stock creation.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.services.stock_setup_service import StockSetupService
from app.domain.models import Stock
from app.domain.services.symbol_resolver import IdentifierType, SymbolInfo
from app.domain.value_objects.currency import Currency


class TestStockSetupService:
    """Test StockSetupService class."""

    @pytest.fixture
    def mock_stock_repo(self):
        """Mock StockRepository."""
        repo = AsyncMock()
        repo.get_by_identifier = AsyncMock(return_value=None)  # Stock doesn't exist
        repo.create = AsyncMock()
        return repo

    @pytest.fixture
    def mock_scoring_service(self):
        """Mock ScoringService."""
        service = AsyncMock()
        service.calculate_and_save_score = AsyncMock(return_value=None)
        return service

    @pytest.fixture
    def mock_tradernet_client(self):
        """Mock TradernetClient."""
        client = MagicMock()
        client.is_connected = True
        return client

    @pytest.fixture
    def mock_db_manager(self):
        """Mock DatabaseManager."""
        manager = MagicMock()
        return manager

    @pytest.fixture
    def mock_symbol_resolver(self):
        """Mock SymbolResolver."""
        resolver = MagicMock()
        resolver.detect_type = MagicMock(return_value=IdentifierType.TRADERNET)
        resolver.resolve = AsyncMock(
            return_value=SymbolInfo(
                tradernet_symbol="AAPL.US",
                isin="US0378331005",
                yahoo_symbol="AAPL",
            )
        )
        return resolver

    @pytest.fixture
    def service(
        self,
        mock_stock_repo,
        mock_scoring_service,
        mock_tradernet_client,
        mock_db_manager,
        mock_symbol_resolver,
    ):
        """Create StockSetupService with mocked dependencies."""
        return StockSetupService(
            stock_repo=mock_stock_repo,
            scoring_service=mock_scoring_service,
            tradernet_client=mock_tradernet_client,
            db_manager=mock_db_manager,
            symbol_resolver=mock_symbol_resolver,
        )

    @pytest.mark.asyncio
    async def test_adds_stock_by_tradernet_symbol(
        self, service, mock_stock_repo, mock_symbol_resolver, mock_tradernet_client
    ):
        """Test adding stock by Tradernet symbol."""
        # Mock Tradernet data
        mock_tradernet_client.get_quotes_raw.return_value = {
            "result": {
                "q": [
                    {
                        "x_curr": "USD",
                        "issue_nb": "US0378331005",
                    }
                ]
            }
        }

        # Mock Yahoo Finance data
        with patch("app.application.services.stock_setup_service.yahoo") as mock_yahoo:
            mock_yahoo.get_stock_country_and_exchange.return_value = ("US", "NASDAQ")
            mock_yahoo.get_stock_industry.return_value = "Technology"

            with patch(
                "app.application.services.stock_setup_service._sync_historical_for_symbol",
                new_callable=AsyncMock,
            ) as mock_sync:
                result = await service.add_stock_by_identifier("AAPL.US")

                assert isinstance(result, Stock)
                assert result.symbol == "AAPL.US"
                assert result.country == "US"
                assert result.industry == "Technology"
                mock_stock_repo.create.assert_called_once()
                mock_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_adds_stock_by_isin(
        self, service, mock_stock_repo, mock_symbol_resolver, mock_tradernet_client
    ):
        """Test adding stock by ISIN."""
        mock_symbol_resolver.detect_type.return_value = IdentifierType.ISIN
        mock_symbol_resolver.resolve.return_value = SymbolInfo(
            tradernet_symbol=None,
            isin="US0378331005",
            yahoo_symbol="US0378331005",
        )

        # Mock Tradernet find_symbol
        mock_tradernet_client.find_symbol.return_value = {
            "found": [
                {
                    "t": "AAPL.US",
                    "nm": "Apple Inc.",
                    "x_curr": "USD",
                    "isin": "US0378331005",
                }
            ]
        }

        # Mock Yahoo Finance data
        with patch("app.application.services.stock_setup_service.yahoo") as mock_yahoo:
            mock_yahoo.get_stock_country_and_exchange.return_value = ("US", "NASDAQ")
            mock_yahoo.get_stock_industry.return_value = "Technology"

            with patch(
                "app.application.services.stock_setup_service._sync_historical_for_symbol",
                new_callable=AsyncMock,
            ):
                result = await service.add_stock_by_identifier("US0378331005")

                assert isinstance(result, Stock)
                assert result.symbol == "AAPL.US"
                assert result.isin == "US0378331005"
                mock_stock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_error_if_stock_already_exists(self, service, mock_stock_repo):
        """Test that ValueError is raised if stock already exists."""
        existing_stock = Stock(
            symbol="AAPL.US",
            name="Apple Inc.",
            country="US",
            fullExchangeName="NASDAQ",
            yahoo_symbol="AAPL",
            isin="US0378331005",
            industry="Technology",
            priority_multiplier=1.0,
            min_lot=1,
            active=True,
            allow_buy=True,
            allow_sell=True,
            currency=Currency.USD,
        )
        mock_stock_repo.get_by_identifier.return_value = existing_stock

        with pytest.raises(ValueError, match="Stock already exists"):
            await service.add_stock_by_identifier("AAPL.US")

    @pytest.mark.asyncio
    async def test_raises_error_if_identifier_empty(self, service):
        """Test that ValueError is raised for empty identifier."""
        with pytest.raises(ValueError, match="Identifier cannot be empty"):
            await service.add_stock_by_identifier("")

        with pytest.raises(ValueError, match="Identifier cannot be empty"):
            await service.add_stock_by_identifier("   ")

    @pytest.mark.asyncio
    async def test_raises_error_if_yahoo_format_provided(
        self, service, mock_symbol_resolver
    ):
        """Test that ValueError is raised for Yahoo format identifiers."""
        mock_symbol_resolver.detect_type.return_value = IdentifierType.YAHOO

        with pytest.raises(ValueError, match="Cannot add stock with identifier"):
            await service.add_stock_by_identifier("AAPL")

    @pytest.mark.asyncio
    async def test_normalizes_identifier_to_uppercase(
        self, service, mock_stock_repo, mock_symbol_resolver, mock_tradernet_client
    ):
        """Test that identifier is normalized to uppercase."""
        mock_tradernet_client.get_quotes_raw.return_value = {
            "result": {
                "q": [
                    {
                        "x_curr": "USD",
                        "issue_nb": "US0378331005",
                    }
                ]
            }
        }

        with patch("app.application.services.stock_setup_service.yahoo") as mock_yahoo:
            mock_yahoo.get_stock_country_and_exchange.return_value = ("US", "NASDAQ")
            mock_yahoo.get_stock_industry.return_value = "Technology"

            with patch(
                "app.application.services.stock_setup_service._sync_historical_for_symbol",
                new_callable=AsyncMock,
            ):
                # Identifier should be normalized
                mock_symbol_resolver.detect_type.assert_not_called()

                result = await service.add_stock_by_identifier("aapl.us")

                # Should have been called with uppercase
                mock_symbol_resolver.detect_type.assert_called_with("AAPL.US")
                assert result.symbol == "AAPL.US"

    @pytest.mark.asyncio
    async def test_handles_historical_data_fetch_failure(
        self, service, mock_stock_repo, mock_tradernet_client
    ):
        """Test that stock creation continues even if historical data fetch fails."""
        mock_tradernet_client.get_quotes_raw.return_value = {
            "result": {
                "q": [
                    {
                        "x_curr": "USD",
                        "issue_nb": "US0378331005",
                    }
                ]
            }
        }

        with patch("app.application.services.stock_setup_service.yahoo") as mock_yahoo:
            mock_yahoo.get_stock_country_and_exchange.return_value = ("US", "NASDAQ")
            mock_yahoo.get_stock_industry.return_value = "Technology"

            with patch(
                "app.application.services.stock_setup_service._sync_historical_for_symbol",
                new_callable=AsyncMock,
            ) as mock_sync:
                mock_sync.side_effect = Exception("Historical data fetch failed")

                # Should still create stock
                result = await service.add_stock_by_identifier("AAPL.US")

                assert isinstance(result, Stock)
                mock_stock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_score_calculation_failure(
        self, service, mock_stock_repo, mock_scoring_service, mock_tradernet_client
    ):
        """Test that stock creation continues even if score calculation fails."""
        mock_tradernet_client.get_quotes_raw.return_value = {
            "result": {
                "q": [
                    {
                        "x_curr": "USD",
                        "issue_nb": "US0378331005",
                    }
                ]
            }
        }
        mock_scoring_service.calculate_and_save_score.side_effect = Exception(
            "Score calculation failed"
        )

        with patch("app.application.services.stock_setup_service.yahoo") as mock_yahoo:
            mock_yahoo.get_stock_country_and_exchange.return_value = ("US", "NASDAQ")
            mock_yahoo.get_stock_industry.return_value = "Technology"

            with patch(
                "app.application.services.stock_setup_service._sync_historical_for_symbol",
                new_callable=AsyncMock,
            ):
                # Should still create stock
                result = await service.add_stock_by_identifier("AAPL.US")

                assert isinstance(result, Stock)
                mock_stock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_publishes_stock_added_event(
        self, service, mock_stock_repo, mock_tradernet_client
    ):
        """Test that StockAddedEvent is published when stock is added."""
        mock_tradernet_client.get_quotes_raw.return_value = {
            "result": {
                "q": [
                    {
                        "x_curr": "USD",
                        "issue_nb": "US0378331005",
                    }
                ]
            }
        }

        with (
            patch("app.application.services.stock_setup_service.yahoo") as mock_yahoo,
            patch(
                "app.application.services.stock_setup_service.get_event_bus"
            ) as mock_event_bus,
            patch(
                "app.application.services.stock_setup_service.StockAddedEvent"
            ) as mock_event_class,
            patch(
                "app.application.services.stock_setup_service._sync_historical_for_symbol",
                new_callable=AsyncMock,
            ),
        ):
            mock_yahoo.get_stock_country_and_exchange.return_value = ("US", "NASDAQ")
            mock_yahoo.get_stock_industry.return_value = "Technology"

            mock_bus = MagicMock()
            mock_event_bus.return_value = mock_bus

            mock_event = MagicMock()
            mock_event_class.return_value = mock_event

            await service.add_stock_by_identifier("AAPL.US")

            # Should publish event
            mock_bus.publish.assert_called_once()
            mock_event_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_custom_min_lot(
        self, service, mock_stock_repo, mock_tradernet_client
    ):
        """Test that custom min_lot is used."""
        mock_tradernet_client.get_quotes_raw.return_value = {
            "result": {
                "q": [
                    {
                        "x_curr": "USD",
                        "issue_nb": "US0378331005",
                    }
                ]
            }
        }

        with (
            patch("app.application.services.stock_setup_service.yahoo") as mock_yahoo,
            patch(
                "app.application.services.stock_setup_service._sync_historical_for_symbol",
                new_callable=AsyncMock,
            ),
        ):
            mock_yahoo.get_stock_country_and_exchange.return_value = ("US", "NASDAQ")
            mock_yahoo.get_stock_industry.return_value = "Technology"

            result = await service.add_stock_by_identifier("AAPL.US", min_lot=10)

            assert result.min_lot == 10

    @pytest.mark.asyncio
    async def test_uses_custom_allow_buy_sell(
        self, service, mock_stock_repo, mock_tradernet_client
    ):
        """Test that custom allow_buy and allow_sell flags are used."""
        mock_tradernet_client.get_quotes_raw.return_value = {
            "result": {
                "q": [
                    {
                        "x_curr": "USD",
                        "issue_nb": "US0378331005",
                    }
                ]
            }
        }

        with (
            patch("app.application.services.stock_setup_service.yahoo") as mock_yahoo,
            patch(
                "app.application.services.stock_setup_service._sync_historical_for_symbol",
                new_callable=AsyncMock,
            ),
        ):
            mock_yahoo.get_stock_country_and_exchange.return_value = ("US", "NASDAQ")
            mock_yahoo.get_stock_industry.return_value = "Technology"

            result = await service.add_stock_by_identifier(
                "AAPL.US", allow_buy=False, allow_sell=False
            )

            assert result.allow_buy is False
            assert result.allow_sell is False
