"""Tests for ticker text generator job.

These tests validate the LED ticker text generation from portfolio
data and recommendations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGetPortfolioValuePart:
    """Test portfolio value text generation."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_disabled(self):
        """Test that empty string returned when show_value is 0."""
        from app.jobs.ticker_text_generator import _get_portfolio_value_part

        mock_repo = AsyncMock()

        result = await _get_portfolio_value_part(mock_repo, 0)

        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_snapshot(self):
        """Test that empty string returned when no portfolio snapshot."""
        from app.jobs.ticker_text_generator import _get_portfolio_value_part

        mock_repo = AsyncMock()
        mock_repo.get_latest.return_value = None

        result = await _get_portfolio_value_part(mock_repo, 1.0)

        assert result == ""

    @pytest.mark.asyncio
    async def test_formats_portfolio_value(self):
        """Test portfolio value formatting with comma separator."""
        from app.jobs.ticker_text_generator import _get_portfolio_value_part

        mock_repo = AsyncMock()
        mock_snapshot = MagicMock()
        mock_snapshot.total_value = 12345.67
        mock_repo.get_latest.return_value = mock_snapshot

        result = await _get_portfolio_value_part(mock_repo, 1.0)

        assert result == "Portfolio EUR12,345"


class TestGetCashBalancePart:
    """Test cash balance text generation."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_disabled(self):
        """Test that empty string returned when show_cash is 0."""
        from app.jobs.ticker_text_generator import _get_cash_balance_part

        mock_repo = AsyncMock()

        result = await _get_cash_balance_part(mock_repo, 0)

        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_snapshot(self):
        """Test that empty string returned when no portfolio snapshot."""
        from app.jobs.ticker_text_generator import _get_cash_balance_part

        mock_repo = AsyncMock()
        mock_repo.get_latest.return_value = None

        result = await _get_cash_balance_part(mock_repo, 1.0)

        assert result == ""

    @pytest.mark.asyncio
    async def test_formats_cash_balance(self):
        """Test cash balance formatting."""
        from app.jobs.ticker_text_generator import _get_cash_balance_part

        mock_repo = AsyncMock()
        mock_snapshot = MagicMock()
        mock_snapshot.cash_balance = 675.50
        mock_repo.get_latest.return_value = mock_snapshot

        result = await _get_cash_balance_part(mock_repo, 1.0)

        assert result == "CASH EUR675"


class TestGetMultiStepRecommendations:
    """Test multi-step recommendation text generation."""

    def test_returns_empty_when_no_cache(self):
        """Test empty list when no cached recommendations."""
        from app.jobs.ticker_text_generator import _get_multi_step_recommendations

        with patch("app.jobs.ticker_text_generator.cache") as mock_cache:
            mock_cache.get.return_value = None

            result = _get_multi_step_recommendations(3, 1.0)

        assert result == []

    def test_returns_empty_when_no_steps(self):
        """Test empty list when cached data has no steps."""
        from app.jobs.ticker_text_generator import _get_multi_step_recommendations

        with patch("app.jobs.ticker_text_generator.cache") as mock_cache:
            mock_cache.get.return_value = {"steps": []}

            result = _get_multi_step_recommendations(3, 1.0)

        assert result == []

    def test_formats_steps_with_amounts(self):
        """Test step formatting with amounts shown."""
        from app.jobs.ticker_text_generator import _get_multi_step_recommendations

        with patch("app.jobs.ticker_text_generator.cache") as mock_cache:
            mock_cache.get.return_value = {
                "steps": [
                    {"side": "buy", "symbol": "AAPL.US", "estimated_value": 855},
                    {"side": "sell", "symbol": "MSFT.US", "estimated_value": 200},
                ]
            }

            result = _get_multi_step_recommendations(3, 1.0)

        assert result == ["BUY AAPL EUR855", "SELL MSFT EUR200"]

    def test_formats_steps_without_amounts(self):
        """Test step formatting without amounts."""
        from app.jobs.ticker_text_generator import _get_multi_step_recommendations

        with patch("app.jobs.ticker_text_generator.cache") as mock_cache:
            mock_cache.get.return_value = {
                "steps": [
                    {"side": "buy", "symbol": "AAPL.US", "estimated_value": 855},
                ]
            }

            result = _get_multi_step_recommendations(3, 0)  # show_amounts=0

        assert result == ["BUY AAPL"]

    def test_respects_max_actions(self):
        """Test that max_actions limits output."""
        from app.jobs.ticker_text_generator import _get_multi_step_recommendations

        with patch("app.jobs.ticker_text_generator.cache") as mock_cache:
            mock_cache.get.return_value = {
                "steps": [
                    {"side": "buy", "symbol": "A.US", "estimated_value": 100},
                    {"side": "buy", "symbol": "B.US", "estimated_value": 200},
                    {"side": "buy", "symbol": "C.US", "estimated_value": 300},
                    {"side": "buy", "symbol": "D.US", "estimated_value": 400},
                ]
            }

            result = _get_multi_step_recommendations(2, 1.0)

        assert len(result) == 2

    def test_tries_different_cache_depths(self):
        """Test that different cache depths are tried."""
        from app.jobs.ticker_text_generator import _get_multi_step_recommendations

        with patch("app.jobs.ticker_text_generator.cache") as mock_cache:
            # Return None for depth 5,4,3 but data for depth 2
            def mock_get(key):
                if ":2:" in key:
                    return {
                        "steps": [
                            {"side": "buy", "symbol": "TEST.US", "estimated_value": 100}
                        ]
                    }
                return None

            mock_cache.get.side_effect = mock_get

            result = _get_multi_step_recommendations(3, 1.0)

        assert result == ["BUY TEST EUR100"]


class TestGetSingleRecommendations:
    """Test single recommendation text generation."""

    def test_returns_empty_when_no_cache(self):
        """Test empty list when no cached recommendations."""
        from app.jobs.ticker_text_generator import _get_single_recommendations

        with patch("app.jobs.ticker_text_generator.cache") as mock_cache:
            mock_cache.get.return_value = None

            result = _get_single_recommendations(3, 1.0)

        assert result == []

    def test_formats_buy_recommendations(self):
        """Test buy recommendation formatting."""
        from app.jobs.ticker_text_generator import _get_single_recommendations

        with patch("app.jobs.ticker_text_generator.cache") as mock_cache:

            def mock_get(key):
                if key == "recommendations:3":
                    return {
                        "recommendations": [
                            {"symbol": "AAPL.US", "amount": 1000},
                        ]
                    }
                return None

            mock_cache.get.side_effect = mock_get

            result = _get_single_recommendations(3, 1.0)

        assert result == ["BUY AAPL EUR1000"]

    def test_formats_sell_recommendations(self):
        """Test sell recommendation formatting."""
        from app.jobs.ticker_text_generator import _get_single_recommendations

        with patch("app.jobs.ticker_text_generator.cache") as mock_cache:

            def mock_get(key):
                if key == "sell_recommendations:3":
                    return {
                        "recommendations": [
                            {"symbol": "MSFT.US", "estimated_value": 500},
                        ]
                    }
                return None

            mock_cache.get.side_effect = mock_get

            result = _get_single_recommendations(3, 1.0)

        assert result == ["SELL MSFT EUR500"]

    def test_respects_max_actions_across_buy_and_sell(self):
        """Test max_actions limits total across buy and sell."""
        from app.jobs.ticker_text_generator import _get_single_recommendations

        with patch("app.jobs.ticker_text_generator.cache") as mock_cache:

            def mock_get(key):
                if key == "recommendations:3":
                    return {
                        "recommendations": [
                            {"symbol": "A.US", "amount": 100},
                            {"symbol": "B.US", "amount": 200},
                        ]
                    }
                if key == "sell_recommendations:3":
                    return {
                        "recommendations": [
                            {"symbol": "C.US", "estimated_value": 300},
                            {"symbol": "D.US", "estimated_value": 400},
                        ]
                    }
                return None

            mock_cache.get.side_effect = mock_get

            result = _get_single_recommendations(2, 1.0)

        assert len(result) == 2

    def test_formats_without_amounts(self):
        """Test formatting without amounts."""
        from app.jobs.ticker_text_generator import _get_single_recommendations

        with patch("app.jobs.ticker_text_generator.cache") as mock_cache:

            def mock_get(key):
                if key == "recommendations:3":
                    return {
                        "recommendations": [
                            {"symbol": "AAPL.US", "amount": 1000},
                        ]
                    }
                return None

            mock_cache.get.side_effect = mock_get

            result = _get_single_recommendations(3, 0)  # show_amounts=0

        assert result == ["BUY AAPL"]


class TestGenerateTickerText:
    """Test full ticker text generation."""

    @pytest.mark.asyncio
    async def test_generates_full_ticker_text(self):
        """Test complete ticker text with all parts."""
        from app.jobs.ticker_text_generator import generate_ticker_text

        mock_settings_repo = AsyncMock()
        mock_settings_repo.get_float.side_effect = [1.0, 1.0, 1.0, 1.0, 3.0]

        mock_portfolio_repo = AsyncMock()
        mock_snapshot = MagicMock()
        mock_snapshot.total_value = 10000
        mock_snapshot.cash_balance = 500
        mock_portfolio_repo.get_latest.return_value = mock_snapshot

        with patch(
            "app.jobs.ticker_text_generator.SettingsRepository",
            return_value=mock_settings_repo,
        ):
            with patch(
                "app.jobs.ticker_text_generator.PortfolioRepository",
                return_value=mock_portfolio_repo,
            ):
                with patch(
                    "app.jobs.ticker_text_generator._get_multi_step_recommendations",
                    return_value=["BUY AAPL EUR500"],
                ):
                    result = await generate_ticker_text()

        assert "Portfolio EUR10,000" in result
        assert "CASH EUR500" in result
        assert "BUY AAPL EUR500" in result
        assert "|" in result  # Parts separated by |

    @pytest.mark.asyncio
    async def test_falls_back_to_single_recommendations(self):
        """Test fallback to single recommendations when multi-step is empty."""
        from app.jobs.ticker_text_generator import generate_ticker_text

        mock_settings_repo = AsyncMock()
        mock_settings_repo.get_float.side_effect = [
            0,
            0,
            1.0,
            1.0,
            3.0,
        ]  # No value/cash

        mock_portfolio_repo = AsyncMock()

        with patch(
            "app.jobs.ticker_text_generator.SettingsRepository",
            return_value=mock_settings_repo,
        ):
            with patch(
                "app.jobs.ticker_text_generator.PortfolioRepository",
                return_value=mock_portfolio_repo,
            ):
                with patch(
                    "app.jobs.ticker_text_generator._get_multi_step_recommendations",
                    return_value=[],
                ):
                    with patch(
                        "app.jobs.ticker_text_generator._get_single_recommendations",
                        return_value=["BUY MSFT EUR300"],
                    ):
                        result = await generate_ticker_text()

        assert "BUY MSFT EUR300" in result

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        """Test empty string returned on error."""
        from app.jobs.ticker_text_generator import generate_ticker_text

        with patch(
            "app.jobs.ticker_text_generator.SettingsRepository",
            side_effect=Exception("Test error"),
        ):
            result = await generate_ticker_text()

        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_data(self):
        """Test empty string when no portfolio data available."""
        from app.jobs.ticker_text_generator import generate_ticker_text

        mock_settings_repo = AsyncMock()
        mock_settings_repo.get_float.side_effect = [1.0, 1.0, 1.0, 1.0, 3.0]

        mock_portfolio_repo = AsyncMock()
        mock_portfolio_repo.get_latest.return_value = None

        with patch(
            "app.jobs.ticker_text_generator.SettingsRepository",
            return_value=mock_settings_repo,
        ):
            with patch(
                "app.jobs.ticker_text_generator.PortfolioRepository",
                return_value=mock_portfolio_repo,
            ):
                with patch(
                    "app.jobs.ticker_text_generator._get_multi_step_recommendations",
                    return_value=[],
                ):
                    with patch(
                        "app.jobs.ticker_text_generator._get_single_recommendations",
                        return_value=[],
                    ):
                        result = await generate_ticker_text()

        assert result == ""


class TestUpdateTickerText:
    """Test ticker text update function."""

    @pytest.mark.asyncio
    async def test_sets_ticker_text(self):
        """Test that ticker text is set via display service."""
        from app.jobs.ticker_text_generator import update_ticker_text

        with patch(
            "app.jobs.ticker_text_generator.generate_ticker_text",
            new_callable=AsyncMock,
            return_value="Test ticker text",
        ):
            with patch("app.jobs.ticker_text_generator.set_next_actions") as mock_set:
                await update_ticker_text()

        mock_set.assert_called_once_with("Test ticker text")

    @pytest.mark.asyncio
    async def test_handles_errors_gracefully(self):
        """Test that errors don't crash the update."""
        from app.jobs.ticker_text_generator import update_ticker_text

        with patch(
            "app.jobs.ticker_text_generator.generate_ticker_text",
            new_callable=AsyncMock,
            side_effect=Exception("Test error"),
        ):
            # Should not raise
            await update_ticker_text()
