"""Tests for stocks API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.stocks import (
    StockCreate,
    StockUpdate,
    _apply_boolean_update,
    _apply_numeric_update,
    _apply_string_update,
    _build_update_dict,
    _format_stock_response,
    _validate_symbol_change,
    create_stock,
    delete_stock,
    get_stock,
    get_stocks,
    refresh_all_scores,
    refresh_stock_score,
    update_stock,
)


class TestGetStocks:
    """Tests for GET /stocks endpoint."""

    @pytest.mark.asyncio
    async def test_get_stocks_returns_cached_data(self):
        """Test that cached data is returned when available."""
        cached_data = [{"symbol": "AAPL", "name": "Apple", "position_value": 100}]

        with patch("app.api.stocks.cache") as mock_cache:
            mock_cache.get.return_value = cached_data

            mock_stock_repo = AsyncMock()
            mock_portfolio_service = AsyncMock()
            mock_position_repo = AsyncMock()
            mock_position_repo.get_count.return_value = 1  # Match cached position count

            result = await get_stocks(
                mock_stock_repo, mock_portfolio_service, mock_position_repo
            )

            assert result == cached_data
            mock_stock_repo.get_with_scores.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_stocks_fetches_when_no_cache(self):
        """Test that stocks are fetched when cache is empty."""
        mock_stock = {
            "symbol": "AAPL",
            "name": "Apple",
            "total_score": 0.8,
            "volatility": 0.2,
            "priority_multiplier": 1.0,
            "country": "United States",
            "industry": "Consumer Electronics",
            "quality_score": 0.7,
            "opportunity_score": 0.6,
            "allocation_fit_score": 0.8,
        }
        mock_summary = MagicMock()
        mock_summary.country_allocations = []
        mock_summary.industry_allocations = []

        with patch("app.api.stocks.cache") as mock_cache:
            mock_cache.get.return_value = None

            mock_stock_repo = AsyncMock()
            mock_stock_repo.get_with_scores.return_value = [mock_stock]

            mock_portfolio_service = AsyncMock()
            mock_portfolio_service.get_portfolio_summary.return_value = mock_summary

            mock_position_repo = AsyncMock()

            result = await get_stocks(
                mock_stock_repo, mock_portfolio_service, mock_position_repo
            )

            assert len(result) == 1
            assert result[0]["symbol"] == "AAPL"
            mock_cache.set.assert_called_once()


class TestGetStock:
    """Tests for GET /stocks/{isin} endpoint."""

    @pytest.mark.asyncio
    async def test_get_stock_found(self):
        """Test getting a stock that exists."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple Inc."
        mock_stock.industry = "Consumer Electronics"
        mock_stock.country = "United States"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = True

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock

        mock_position_repo = AsyncMock()
        mock_position_repo.get_by_symbol.return_value = None

        mock_score_repo = AsyncMock()
        mock_score_repo.get_by_symbol.return_value = None

        with patch("app.api.stocks.is_isin", return_value=True):
            result = await get_stock(
                "US0378331005", mock_stock_repo, mock_position_repo, mock_score_repo
            )

            assert result["symbol"] == "AAPL.US"
            assert result["isin"] == "US0378331005"
            assert result["name"] == "Apple Inc."
            assert result["position"] is None

    @pytest.mark.asyncio
    async def test_get_stock_not_found(self):
        """Test getting a stock that doesn't exist."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = None

        mock_position_repo = AsyncMock()
        mock_score_repo = AsyncMock()

        with patch("app.api.stocks.is_isin", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await get_stock(
                    "US9999999999", mock_stock_repo, mock_position_repo, mock_score_repo
                )

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_stock_with_score(self):
        """Test getting a stock with score data."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple"
        mock_stock.industry = "Consumer Electronics"
        mock_stock.country = "United States"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = False

        mock_score = MagicMock()
        mock_score.quality_score = 0.8
        mock_score.opportunity_score = 0.7
        mock_score.analyst_score = 0.6
        mock_score.allocation_fit_score = 0.9
        mock_score.total_score = 0.75
        mock_score.cagr_score = 0.85
        mock_score.consistency_score = 0.7
        mock_score.history_years = 5
        mock_score.volatility = 0.2
        mock_score.calculated_at = None
        mock_score.technical_score = 0.6
        mock_score.fundamental_score = 0.8

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock

        mock_position_repo = AsyncMock()
        mock_position_repo.get_by_symbol.return_value = None

        mock_score_repo = AsyncMock()
        mock_score_repo.get_by_symbol.return_value = mock_score

        with patch("app.api.stocks.is_isin", return_value=True):
            result = await get_stock(
                "US0378331005", mock_stock_repo, mock_position_repo, mock_score_repo
            )

            assert result["total_score"] == 0.75
            assert result["quality_score"] == 0.8

    @pytest.mark.asyncio
    async def test_get_stock_with_position(self):
        """Test getting a stock with position data."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple"
        mock_stock.industry = "Consumer Electronics"
        mock_stock.country = "United States"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = False

        mock_position = MagicMock()
        mock_position.symbol = "AAPL.US"
        mock_position.quantity = 10
        mock_position.avg_price = 150.0
        mock_position.current_price = 175.0
        mock_position.currency = "USD"
        mock_position.market_value_eur = 1500.0

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock

        mock_position_repo = AsyncMock()
        mock_position_repo.get_by_symbol.return_value = mock_position

        mock_score_repo = AsyncMock()
        mock_score_repo.get_by_symbol.return_value = None

        with patch("app.api.stocks.is_isin", return_value=True):
            result = await get_stock(
                "US0378331005", mock_stock_repo, mock_position_repo, mock_score_repo
            )

            assert result["position"] is not None
            assert result["position"]["quantity"] == 10
            assert result["position"]["avg_price"] == 150.0


class TestCreateStock:
    """Tests for POST /stocks endpoint."""

    @pytest.mark.asyncio
    async def test_create_stock_already_exists(self):
        """Test creating a stock that already exists."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = MagicMock()  # Stock exists

        mock_score_repo = AsyncMock()
        mock_scoring_service = AsyncMock()

        stock_data = StockCreate(
            symbol="AAPL",
            name="Apple",
            country="United States",
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_stock(
                stock_data, mock_stock_repo, mock_score_repo, mock_scoring_service
            )

        assert exc_info.value.status_code == 400
        assert "already exists" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_stock_with_industry(self):
        """Test creating a stock with industry provided."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = None  # Stock doesn't exist

        mock_score_repo = AsyncMock()

        mock_score = MagicMock()
        mock_score.total_score = 0.75
        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score.return_value = mock_score

        stock_data = StockCreate(
            symbol="AAPL",
            name="Apple",
            country="United States",
            industry="Consumer Electronics",
        )

        with (
            patch("app.api.stocks.cache"),
            patch("app.api.stocks.get_event_bus") as mock_event_bus,
            patch("app.api.stocks.StockFactory") as mock_factory,
        ):
            mock_stock = MagicMock()
            mock_stock.min_lot = 1
            mock_factory.create_from_api_request.return_value = mock_stock
            mock_event_bus.return_value = MagicMock()

            result = await create_stock(
                stock_data, mock_stock_repo, mock_score_repo, mock_scoring_service
            )

            assert result["symbol"] == "AAPL"
            assert result["total_score"] == 0.75
            mock_factory.create_from_api_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_stock_detects_industry(self):
        """Test creating a stock without industry triggers detection."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = None

        mock_score_repo = AsyncMock()

        mock_score = MagicMock()
        mock_score.total_score = 0.75
        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score.return_value = mock_score

        stock_data = StockCreate(
            symbol="AAPL",
            name="Apple",
            country="United States",
            # No industry provided
        )

        with (
            patch("app.api.stocks.cache"),
            patch("app.api.stocks.get_event_bus") as mock_event_bus,
            patch("app.api.stocks.StockFactory") as mock_factory,
            patch(
                "app.infrastructure.external.yahoo_finance.get_stock_industry"
            ) as mock_yahoo_industry,
            patch(
                "app.infrastructure.external.yahoo_finance.get_stock_country_and_exchange"
            ) as mock_yahoo_country,
        ):
            mock_stock = MagicMock()
            mock_stock.min_lot = 1
            mock_stock.country = "United States"
            mock_stock.fullExchangeName = "NASDAQ"
            mock_factory.create_from_api_request.return_value = mock_stock
            mock_event_bus.return_value = MagicMock()
            mock_yahoo_industry.return_value = "Consumer Electronics"
            mock_yahoo_country.return_value = ("United States", "NASDAQ")

            result = await create_stock(
                stock_data, mock_stock_repo, mock_score_repo, mock_scoring_service
            )

            assert result["symbol"] == "AAPL"
            mock_yahoo_industry.assert_called_once()
            mock_factory.create_from_api_request.assert_called_once()


class TestRefreshAllScores:
    """Tests for POST /stocks/refresh-all endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_all_scores_success(self):
        """Test refreshing all scores successfully."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.industry = "Consumer Electronics"

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active.return_value = [mock_stock]

        mock_score = MagicMock()
        mock_score.symbol = "AAPL"
        mock_score.total_score = 0.8
        mock_scoring_service = AsyncMock()
        mock_scoring_service.score_all_stocks.return_value = [mock_score]

        with patch("app.api.stocks.get_recommendation_cache") as mock_cache:
            mock_cache.return_value = AsyncMock()
            with patch("app.api.stocks.cache"):
                result = await refresh_all_scores(mock_stock_repo, mock_scoring_service)

                assert "Refreshed scores" in result["message"]
                assert len(result["scores"]) == 1

    @pytest.mark.asyncio
    async def test_refresh_all_scores_detects_missing_industry(self):
        """Test that refresh detects missing industries."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.industry = None  # No industry

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active.return_value = [mock_stock]

        mock_scoring_service = AsyncMock()
        mock_scoring_service.score_all_stocks.return_value = []

        with (
            patch("app.api.stocks.get_recommendation_cache") as mock_cache,
            patch("app.api.stocks.cache"),
            patch(
                "app.infrastructure.external.yahoo_finance.get_stock_industry"
            ) as mock_yahoo,
        ):
            mock_cache.return_value = AsyncMock()
            mock_yahoo.return_value = "Consumer Electronics"

            await refresh_all_scores(mock_stock_repo, mock_scoring_service)

            # Production code calls update with symbol and industry kwargs
            mock_stock_repo.update.assert_called_once_with(
                mock_stock.symbol, industry="Consumer Electronics"
            )

    @pytest.mark.asyncio
    async def test_refresh_all_scores_error(self):
        """Test error handling during refresh."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_all_active.side_effect = Exception("Database error")

        mock_scoring_service = AsyncMock()

        with (
            patch("app.api.stocks.get_recommendation_cache") as mock_cache,
            patch("app.api.stocks.cache"),
        ):
            mock_cache.return_value = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await refresh_all_scores(mock_stock_repo, mock_scoring_service)

            assert exc_info.value.status_code == 500


class TestRefreshStockScore:
    """Tests for POST /stocks/{isin}/refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_stock_score_success(self):
        """Test refreshing a single stock score."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.country = "United States"
        mock_stock.industry = "Consumer Electronics"

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock

        mock_score = MagicMock()
        mock_score.total_score = 0.8
        mock_score.group_scores = {
            "long_term": 0.7,
            "fundamentals": 0.8,
            "opportunity": 0.6,
            "opinion": 0.5,
            "diversification": 0.9,
        }
        mock_score.sub_scores = {
            "long_term": {"cagr": 0.75},
            "fundamentals": {"consistency": 0.8},
            "dividends": {"yield": 0.03},
        }
        mock_score.volatility = 0.2

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score.return_value = mock_score

        with patch("app.api.stocks.get_recommendation_cache") as mock_cache:
            mock_cache.return_value = AsyncMock()
            with patch("app.api.stocks.is_isin", return_value=True):
                result = await refresh_stock_score(
                    "US0378331005", mock_stock_repo, mock_scoring_service
                )

                assert result["symbol"] == "AAPL.US"
                assert result["isin"] == "US0378331005"
                assert result["total_score"] == 0.8

    @pytest.mark.asyncio
    async def test_refresh_stock_score_not_found(self):
        """Test refreshing score for non-existent stock."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = None

        mock_scoring_service = AsyncMock()

        with patch("app.api.stocks.get_recommendation_cache") as mock_cache:
            mock_cache.return_value = AsyncMock()
            with patch("app.api.stocks.is_isin", return_value=True):
                with pytest.raises(HTTPException) as exc_info:
                    await refresh_stock_score(
                        "US9999999999", mock_stock_repo, mock_scoring_service
                    )

                assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_refresh_stock_score_failed(self):
        """Test when score calculation fails."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.country = "United States"
        mock_stock.industry = "Consumer Electronics"

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score.return_value = None  # Failed

        with patch("app.api.stocks.get_recommendation_cache") as mock_cache:
            mock_cache.return_value = AsyncMock()
            with patch("app.api.stocks.is_isin", return_value=True):
                with pytest.raises(HTTPException) as exc_info:
                    await refresh_stock_score(
                        "US0378331005", mock_stock_repo, mock_scoring_service
                    )

                assert exc_info.value.status_code == 500


class TestUpdateStock:
    """Tests for PUT /stocks/{isin} endpoint."""

    @pytest.mark.asyncio
    async def test_update_stock_success(self):
        """Test updating a stock successfully."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple"
        mock_stock.industry = "Consumer Electronics"
        mock_stock.country = "United States"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = False

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        mock_score = MagicMock()
        mock_score.total_score = 0.8
        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score.return_value = mock_score

        update = StockUpdate(name="Apple Inc.")

        with patch("app.api.stocks.cache"):
            with patch("app.api.stocks.is_isin", return_value=True):
                result = await update_stock(
                    "US0378331005", update, mock_stock_repo, mock_scoring_service
                )

                assert result["symbol"] == "AAPL.US"
                assert result["isin"] == "US0378331005"
                mock_stock_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_stock_not_found(self):
        """Test updating a stock that doesn't exist."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = None

        mock_scoring_service = AsyncMock()

        update = StockUpdate(name="New Name")

        with patch("app.api.stocks.is_isin", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await update_stock(
                    "US9999999999", update, mock_stock_repo, mock_scoring_service
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_stock_no_updates(self):
        """Test updating with no changes."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock

        mock_scoring_service = AsyncMock()

        update = StockUpdate()  # Empty update

        with patch("app.api.stocks.is_isin", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await update_stock(
                    "US0378331005", update, mock_stock_repo, mock_scoring_service
                )

            assert exc_info.value.status_code == 400
            assert "No updates" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_stock_symbol_change(self):
        """Test changing a stock's symbol."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple"
        mock_stock.industry = "Consumer Electronics"
        mock_stock.country = "United States"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = False

        mock_stock_repo = AsyncMock()
        # First call finds stock by ISIN, second check for new symbol returns None (doesn't exist)
        mock_stock_repo.get_by_isin.return_value = mock_stock
        mock_stock_repo.get_by_symbol.return_value = None  # New symbol doesn't exist
        mock_stock_repo.get_by_symbol.side_effect = [
            None,
            mock_stock,
        ]  # After update, get by new symbol

        mock_score = MagicMock()
        mock_score.total_score = 0.8
        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score.return_value = mock_score

        update = StockUpdate(new_symbol="AAPL2.US")

        with patch("app.api.stocks.cache"):
            with patch("app.api.stocks.is_isin", return_value=True):
                result = await update_stock(
                    "US0378331005", update, mock_stock_repo, mock_scoring_service
                )

                assert "symbol" in result

    @pytest.mark.asyncio
    async def test_update_stock_with_portfolio_targets(self):
        """Test updating stock with min/max portfolio targets."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple"
        mock_stock.industry = "Consumer Electronics"
        mock_stock.country = "United States"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = False

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        mock_score = MagicMock()
        mock_score.total_score = 0.8
        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score.return_value = mock_score

        update = StockUpdate(min_portfolio_target=5.0, max_portfolio_target=15.0)

        with patch("app.api.stocks.cache"):
            with patch("app.api.stocks.is_isin", return_value=True):
                result = await update_stock(
                    "US0378331005", update, mock_stock_repo, mock_scoring_service
                )

                assert result["symbol"] == "AAPL.US"
                assert result["isin"] == "US0378331005"
                mock_stock_repo.update.assert_called_once()
                # Check that portfolio targets are in the update call
                call_kwargs = mock_stock_repo.update.call_args[1]
                assert call_kwargs["min_portfolio_target"] == 5.0
                assert call_kwargs["max_portfolio_target"] == 15.0

    @pytest.mark.asyncio
    async def test_update_stock_portfolio_target_validation_min_clamped(self):
        """Test that min_portfolio_target is clamped to 0-20 range."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock
        mock_stock_repo.get_by_symbol.return_value = mock_stock
        mock_scoring_service = AsyncMock()

        update = StockUpdate(min_portfolio_target=25.0)  # Over limit

        with patch("app.api.stocks.cache"):
            with patch("app.api.stocks.is_isin", return_value=True):
                await update_stock(
                    "US0378331005", update, mock_stock_repo, mock_scoring_service
                )

                # Should be clamped to 20
                call_kwargs = mock_stock_repo.update.call_args[1]
                assert call_kwargs["min_portfolio_target"] == 20.0

    @pytest.mark.asyncio
    async def test_update_stock_portfolio_target_validation_max_clamped(self):
        """Test that max_portfolio_target is clamped to 0-30 range."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock
        mock_stock_repo.get_by_symbol.return_value = mock_stock
        mock_scoring_service = AsyncMock()

        update = StockUpdate(max_portfolio_target=35.0)  # Over limit

        with patch("app.api.stocks.cache"):
            with patch("app.api.stocks.is_isin", return_value=True):
                await update_stock(
                    "US0378331005", update, mock_stock_repo, mock_scoring_service
                )

                # Should be clamped to 30
                call_kwargs = mock_stock_repo.update.call_args[1]
                assert call_kwargs["max_portfolio_target"] == 30.0

    @pytest.mark.asyncio
    async def test_update_stock_portfolio_target_max_less_than_min(self):
        """Test that max < min is rejected."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock
        mock_scoring_service = AsyncMock()

        update = StockUpdate(min_portfolio_target=15.0, max_portfolio_target=5.0)

        with patch("app.api.stocks.cache"):
            with patch("app.api.stocks.is_isin", return_value=True):
                with pytest.raises(HTTPException) as exc_info:
                    await update_stock(
                        "US0378331005", update, mock_stock_repo, mock_scoring_service
                    )

                assert exc_info.value.status_code == 400
                assert (
                    "max" in exc_info.value.detail.lower()
                    or "min" in exc_info.value.detail.lower()
                )


class TestGetStockResponse:
    """Tests for GET /stocks/{isin} response format."""

    @pytest.mark.asyncio
    async def test_get_stock_includes_portfolio_targets(self):
        """Test that get_stock response includes portfolio targets."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple Inc."
        mock_stock.industry = "Consumer Electronics"
        mock_stock.country = "United States"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = False
        mock_stock.min_portfolio_target = 5.0
        mock_stock.max_portfolio_target = 15.0

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock

        mock_position_repo = AsyncMock()
        mock_position_repo.get_by_symbol.return_value = None

        mock_score_repo = AsyncMock()
        mock_score_repo.get_by_symbol.return_value = None

        with patch("app.api.stocks.is_isin", return_value=True):
            result = await get_stock(
                "US0378331005", mock_stock_repo, mock_position_repo, mock_score_repo
            )

            assert result["min_portfolio_target"] == 5.0
            assert result["max_portfolio_target"] == 15.0


class TestGetStocksResponse:
    """Tests for GET /stocks response format."""

    @pytest.mark.asyncio
    async def test_get_stocks_includes_portfolio_targets(self):
        """Test that get_stocks response includes portfolio targets."""
        mock_stock = {
            "symbol": "AAPL",
            "name": "Apple",
            "total_score": 0.8,
            "volatility": 0.2,
            "priority_multiplier": 1.0,
            "country": "United States",
            "industry": "Consumer Electronics",
            "quality_score": 0.7,
            "opportunity_score": 0.6,
            "allocation_fit_score": 0.8,
            "min_portfolio_target": 5.0,
            "max_portfolio_target": 15.0,
        }
        mock_summary = MagicMock()
        mock_summary.country_allocations = []
        mock_summary.industry_allocations = []

        with patch("app.api.stocks.cache") as mock_cache:
            mock_cache.get.return_value = None

            mock_stock_repo = AsyncMock()
            mock_stock_repo.get_with_scores.return_value = [mock_stock]

            mock_portfolio_service = AsyncMock()
            mock_portfolio_service.get_portfolio_summary.return_value = mock_summary

            mock_position_repo = AsyncMock()

            result = await get_stocks(
                mock_stock_repo, mock_portfolio_service, mock_position_repo
            )

            assert len(result) == 1
            assert result[0]["min_portfolio_target"] == 5.0
            assert result[0]["max_portfolio_target"] == 15.0


class TestDeleteStock:
    """Tests for DELETE /stocks/{isin} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_stock_success(self):
        """Test deleting a stock successfully."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL.US"
        mock_stock.isin = "US0378331005"

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = mock_stock

        with patch("app.api.stocks.cache"):
            with patch("app.api.stocks.is_isin", return_value=True):
                result = await delete_stock("US0378331005", mock_stock_repo)

                assert "removed" in result["message"].lower()
                mock_stock_repo.delete.assert_called_once_with("AAPL.US")

    @pytest.mark.asyncio
    async def test_delete_stock_not_found(self):
        """Test deleting a stock that doesn't exist."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_isin.return_value = None

        with patch("app.api.stocks.is_isin", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await delete_stock("US9999999999", mock_stock_repo)

            assert exc_info.value.status_code == 404


class TestValidateSymbolChange:
    """Tests for symbol change validation."""

    @pytest.mark.asyncio
    async def test_validate_same_symbol(self):
        """Test that same symbol is allowed."""
        mock_stock_repo = AsyncMock()

        # Should not raise
        await _validate_symbol_change("AAPL.US", "AAPL.US", mock_stock_repo)
        mock_stock_repo.get_by_symbol.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_new_symbol_available(self):
        """Test that new symbol is available."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = None

        await _validate_symbol_change("AAPL.US", "AAPL2.US", mock_stock_repo)
        mock_stock_repo.get_by_symbol.assert_called_once_with("AAPL2.US")

    @pytest.mark.asyncio
    async def test_validate_new_symbol_taken(self):
        """Test that taken symbol raises error."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = MagicMock()  # Symbol exists

        with pytest.raises(HTTPException) as exc_info:
            await _validate_symbol_change("AAPL.US", "GOOGL.US", mock_stock_repo)

        assert exc_info.value.status_code == 400


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_apply_string_update_with_value(self):
        """Test applying string update with value."""
        updates = {}
        _apply_string_update(updates, "name", "Apple")
        assert updates["name"] == "Apple"

    def test_apply_string_update_with_transform(self):
        """Test applying string update with transformation."""
        updates = {}
        _apply_string_update(updates, "country", "united states", str.title)
        assert updates["country"] == "United States"

    def test_apply_string_update_with_none(self):
        """Test applying string update with None."""
        updates = {}
        _apply_string_update(updates, "name", None)
        assert "name" not in updates

    def test_apply_numeric_update_with_value(self):
        """Test applying numeric update with value."""
        updates = {}
        _apply_numeric_update(updates, "min_lot", 5)
        assert updates["min_lot"] == 5

    def test_apply_numeric_update_with_clamp(self):
        """Test applying numeric update with clamping."""
        updates = {}
        _apply_numeric_update(updates, "priority", 5.0, lambda v: max(0.1, min(3.0, v)))
        assert updates["priority"] == 3.0

    def test_apply_numeric_update_with_none(self):
        """Test applying numeric update with None."""
        updates = {}
        _apply_numeric_update(updates, "min_lot", None)
        assert "min_lot" not in updates

    def test_apply_boolean_update_with_value(self):
        """Test applying boolean update with value."""
        updates = {}
        _apply_boolean_update(updates, "active", True)
        assert updates["active"] is True

    def test_apply_boolean_update_with_false(self):
        """Test applying boolean update with False."""
        updates = {}
        _apply_boolean_update(updates, "active", False)
        assert updates["active"] is False

    def test_apply_boolean_update_with_none(self):
        """Test applying boolean update with None."""
        updates = {}
        _apply_boolean_update(updates, "active", None)
        assert "active" not in updates

    def test_build_update_dict(self):
        """Test building update dictionary."""
        update = StockUpdate(
            name="Apple Inc.",
            country="United States",  # Country is auto-detected, not in update dict
            active=True,
            min_lot=5,
        )
        result = _build_update_dict(update, None)

        assert result["name"] == "Apple Inc."
        assert "country" not in result  # Country is auto-detected from Yahoo Finance
        assert result["active"] is True
        assert result["min_lot"] == 5

    def test_build_update_dict_with_new_symbol(self):
        """Test building update dictionary with new symbol."""
        update = StockUpdate(name="Apple")
        result = _build_update_dict(update, "AAPL2")

        assert result["symbol"] == "AAPL2"
        assert result["name"] == "Apple"

    def test_format_stock_response_without_score(self):
        """Test formatting stock response without score."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple"
        mock_stock.industry = "Consumer Electronics"
        mock_stock.country = "United States"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = False

        result = _format_stock_response(mock_stock, None)

        assert result["symbol"] == "AAPL"
        assert "total_score" not in result

    def test_format_stock_response_with_score(self):
        """Test formatting stock response with score."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple"
        mock_stock.industry = "Consumer Electronics"
        mock_stock.country = "United States"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = False

        mock_score = MagicMock()
        mock_score.total_score = 0.8

        result = _format_stock_response(mock_stock, mock_score)

        assert result["symbol"] == "AAPL"
        assert result["total_score"] == 0.8
