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
        cached_data = [{"symbol": "AAPL", "name": "Apple"}]

        with patch("app.api.stocks.cache") as mock_cache:
            mock_cache.get.return_value = cached_data

            mock_stock_repo = AsyncMock()
            mock_portfolio_service = AsyncMock()

            result = await get_stocks(mock_stock_repo, mock_portfolio_service)

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
            "geography": "US",
            "industry": "Technology",
            "quality_score": 0.7,
            "opportunity_score": 0.6,
            "allocation_fit_score": 0.8,
        }
        mock_summary = MagicMock()
        mock_summary.geographic_allocations = []
        mock_summary.industry_allocations = []

        with patch("app.api.stocks.cache") as mock_cache:
            mock_cache.get.return_value = None

            mock_stock_repo = AsyncMock()
            mock_stock_repo.get_with_scores.return_value = [mock_stock]

            mock_portfolio_service = AsyncMock()
            mock_portfolio_service.get_portfolio_summary.return_value = mock_summary

            result = await get_stocks(mock_stock_repo, mock_portfolio_service)

            assert len(result) == 1
            assert result[0]["symbol"] == "AAPL"
            mock_cache.set.assert_called_once()


class TestGetStock:
    """Tests for GET /stocks/{symbol} endpoint."""

    @pytest.mark.asyncio
    async def test_get_stock_found(self):
        """Test getting a stock that exists."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple Inc."
        mock_stock.industry = "Technology"
        mock_stock.geography = "US"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = True

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        mock_position_repo = AsyncMock()
        mock_position_repo.get_by_symbol.return_value = None

        mock_score_repo = AsyncMock()
        mock_score_repo.get_by_symbol.return_value = None

        result = await get_stock(
            "AAPL", mock_stock_repo, mock_position_repo, mock_score_repo
        )

        assert result["symbol"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["position"] is None

    @pytest.mark.asyncio
    async def test_get_stock_not_found(self):
        """Test getting a stock that doesn't exist."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = None

        mock_position_repo = AsyncMock()
        mock_score_repo = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_stock(
                "INVALID", mock_stock_repo, mock_position_repo, mock_score_repo
            )

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_stock_with_score(self):
        """Test getting a stock with score data."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple"
        mock_stock.industry = "Tech"
        mock_stock.geography = "US"
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
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        mock_position_repo = AsyncMock()
        mock_position_repo.get_by_symbol.return_value = None

        mock_score_repo = AsyncMock()
        mock_score_repo.get_by_symbol.return_value = mock_score

        result = await get_stock(
            "AAPL", mock_stock_repo, mock_position_repo, mock_score_repo
        )

        assert result["total_score"] == 0.75
        assert result["quality_score"] == 0.8

    @pytest.mark.asyncio
    async def test_get_stock_with_position(self):
        """Test getting a stock with position data."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple"
        mock_stock.industry = "Tech"
        mock_stock.geography = "US"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = False

        mock_position = MagicMock()
        mock_position.symbol = "AAPL"
        mock_position.quantity = 10
        mock_position.avg_price = 150.0
        mock_position.current_price = 175.0
        mock_position.currency = "USD"
        mock_position.market_value_eur = 1500.0

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        mock_position_repo = AsyncMock()
        mock_position_repo.get_by_symbol.return_value = mock_position

        mock_score_repo = AsyncMock()
        mock_score_repo.get_by_symbol.return_value = None

        result = await get_stock(
            "AAPL", mock_stock_repo, mock_position_repo, mock_score_repo
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
            geography="US",
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
            geography="US",
            industry="Technology",
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
            geography="US",
            # No industry provided
        )

        with (
            patch("app.api.stocks.cache"),
            patch("app.api.stocks.get_event_bus") as mock_event_bus,
            patch("app.api.stocks.StockFactory") as mock_factory,
            patch(
                "app.infrastructure.external.yahoo_finance.get_stock_industry"
            ) as mock_yahoo,
        ):
            mock_stock = MagicMock()
            mock_stock.min_lot = 1
            mock_factory.create_with_industry_detection.return_value = mock_stock
            mock_event_bus.return_value = MagicMock()
            mock_yahoo.return_value = "Consumer Electronics"

            result = await create_stock(
                stock_data, mock_stock_repo, mock_score_repo, mock_scoring_service
            )

            assert result["symbol"] == "AAPL"
            mock_factory.create_with_industry_detection.assert_called_once()


class TestRefreshAllScores:
    """Tests for POST /stocks/refresh-all endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_all_scores_success(self):
        """Test refreshing all scores successfully."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.industry = "Technology"

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
            mock_yahoo.return_value = "Technology"

            await refresh_all_scores(mock_stock_repo, mock_scoring_service)

            # Production code calls update with symbol and industry kwargs
            mock_stock_repo.update.assert_called_once_with(
                mock_stock.symbol, industry="Technology"
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
    """Tests for POST /stocks/{symbol}/refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_stock_score_success(self):
        """Test refreshing a single stock score."""
        mock_stock = MagicMock()
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.geography = "US"
        mock_stock.industry = "Technology"

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = mock_stock

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

            result = await refresh_stock_score(
                "AAPL", mock_stock_repo, mock_scoring_service
            )

            assert result["symbol"] == "AAPL"
            assert result["total_score"] == 0.8

    @pytest.mark.asyncio
    async def test_refresh_stock_score_not_found(self):
        """Test refreshing score for non-existent stock."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = None

        mock_scoring_service = AsyncMock()

        with patch("app.api.stocks.get_recommendation_cache") as mock_cache:
            mock_cache.return_value = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await refresh_stock_score(
                    "INVALID", mock_stock_repo, mock_scoring_service
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_refresh_stock_score_failed(self):
        """Test when score calculation fails."""
        mock_stock = MagicMock()
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.geography = "US"
        mock_stock.industry = "Technology"

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score.return_value = None  # Failed

        with patch("app.api.stocks.get_recommendation_cache") as mock_cache:
            mock_cache.return_value = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await refresh_stock_score("AAPL", mock_stock_repo, mock_scoring_service)

            assert exc_info.value.status_code == 500


class TestUpdateStock:
    """Tests for PUT /stocks/{symbol} endpoint."""

    @pytest.mark.asyncio
    async def test_update_stock_success(self):
        """Test updating a stock successfully."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple"
        mock_stock.industry = "Technology"
        mock_stock.geography = "US"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = False

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        mock_score = MagicMock()
        mock_score.total_score = 0.8
        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score.return_value = mock_score

        update = StockUpdate(name="Apple Inc.")

        with patch("app.api.stocks.cache"):
            result = await update_stock(
                "AAPL", update, mock_stock_repo, mock_scoring_service
            )

            assert result["symbol"] == "AAPL"
            mock_stock_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_stock_not_found(self):
        """Test updating a stock that doesn't exist."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = None

        mock_scoring_service = AsyncMock()

        update = StockUpdate(name="New Name")

        with pytest.raises(HTTPException) as exc_info:
            await update_stock("INVALID", update, mock_stock_repo, mock_scoring_service)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_stock_no_updates(self):
        """Test updating with no changes."""
        mock_stock = MagicMock()

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        mock_scoring_service = AsyncMock()

        update = StockUpdate()  # Empty update

        with pytest.raises(HTTPException) as exc_info:
            await update_stock("AAPL", update, mock_stock_repo, mock_scoring_service)

        assert exc_info.value.status_code == 400
        assert "No updates" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_stock_symbol_change(self):
        """Test changing a stock's symbol."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"
        mock_stock.yahoo_symbol = "AAPL"
        mock_stock.name = "Apple"
        mock_stock.industry = "Tech"
        mock_stock.geography = "US"
        mock_stock.priority_multiplier = 1.0
        mock_stock.min_lot = 1
        mock_stock.active = True
        mock_stock.allow_buy = True
        mock_stock.allow_sell = False

        mock_stock_repo = AsyncMock()
        # First call finds AAPL, second check for new symbol returns None (doesn't exist)
        mock_stock_repo.get_by_symbol.side_effect = [mock_stock, None, mock_stock]

        mock_score = MagicMock()
        mock_score.total_score = 0.8
        mock_scoring_service = AsyncMock()
        mock_scoring_service.calculate_and_save_score.return_value = mock_score

        update = StockUpdate(new_symbol="AAPL2")

        with patch("app.api.stocks.cache"):
            result = await update_stock(
                "AAPL", update, mock_stock_repo, mock_scoring_service
            )

            assert "symbol" in result


class TestDeleteStock:
    """Tests for DELETE /stocks/{symbol} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_stock_success(self):
        """Test deleting a stock successfully."""
        mock_stock = MagicMock()
        mock_stock.symbol = "AAPL"

        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        with patch("app.api.stocks.cache"):
            result = await delete_stock("AAPL", mock_stock_repo)

            assert "removed" in result["message"].lower()
            mock_stock_repo.delete.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_delete_stock_not_found(self):
        """Test deleting a stock that doesn't exist."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await delete_stock("INVALID", mock_stock_repo)

        assert exc_info.value.status_code == 404


class TestValidateSymbolChange:
    """Tests for symbol change validation."""

    @pytest.mark.asyncio
    async def test_validate_same_symbol(self):
        """Test that same symbol is allowed."""
        mock_stock_repo = AsyncMock()

        # Should not raise
        await _validate_symbol_change("AAPL", "AAPL", mock_stock_repo)
        mock_stock_repo.get_by_symbol.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_new_symbol_available(self):
        """Test that new symbol is available."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = None

        await _validate_symbol_change("AAPL", "AAPL2", mock_stock_repo)
        mock_stock_repo.get_by_symbol.assert_called_once_with("AAPL2")

    @pytest.mark.asyncio
    async def test_validate_new_symbol_taken(self):
        """Test that taken symbol raises error."""
        mock_stock_repo = AsyncMock()
        mock_stock_repo.get_by_symbol.return_value = MagicMock()  # Symbol exists

        with pytest.raises(HTTPException) as exc_info:
            await _validate_symbol_change("AAPL", "GOOGL", mock_stock_repo)

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
        _apply_string_update(updates, "geography", "us", str.upper)
        assert updates["geography"] == "US"

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
            geography="us",
            active=True,
            min_lot=5,
        )
        result = _build_update_dict(update, None)

        assert result["name"] == "Apple Inc."
        assert result["geography"] == "US"
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
        mock_stock.industry = "Tech"
        mock_stock.geography = "US"
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
        mock_stock.industry = "Tech"
        mock_stock.geography = "US"
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
