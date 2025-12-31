"""Tests for Yahoo Finance data fetchers.

These tests validate the Yahoo Finance API integration functions.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.infrastructure.external.yahoo.data_fetchers import (
    get_analyst_data,
    get_batch_quotes,
    get_current_price,
    get_fundamental_data,
    get_historical_prices,
    get_security_industry,
)


class TestGetAnalystData:
    """Test get_analyst_data function."""

    def test_returns_analyst_data(self):
        """Test returning analyst data when available."""
        mock_info = {
            "recommendationKey": "buy",
            "targetMeanPrice": 200.0,
            "currentPrice": 150.0,
            "numberOfAnalystOpinions": 25,
        }

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with (
            patch("yfinance.Ticker", return_value=mock_ticker),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_analyst_data("AAPL.US")

        assert result is not None
        assert result.symbol == "AAPL.US"
        assert result.recommendation == "buy"
        assert result.target_price == 200.0
        assert result.current_price == 150.0
        assert result.num_analysts == 25
        assert result.recommendation_score == 0.8

    def test_calculates_upside_percentage(self):
        """Test upside percentage calculation."""
        mock_info = {
            "recommendationKey": "strongBuy",
            "targetMeanPrice": 200.0,
            "currentPrice": 100.0,
            "numberOfAnalystOpinions": 10,
        }

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with (
            patch("yfinance.Ticker", return_value=mock_ticker),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_analyst_data("AAPL.US")

        assert result.upside_pct == pytest.approx(100.0)
        assert result.recommendation_score == 1.0

    def test_handles_missing_data(self):
        """Test handling missing data fields."""
        mock_info = {}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with (
            patch("yfinance.Ticker", return_value=mock_ticker),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_analyst_data("AAPL.US")

        assert result is not None
        assert result.recommendation == "hold"
        assert result.target_price == 0
        assert result.recommendation_score == 0.5

    def test_uses_yahoo_symbol_override(self):
        """Test using explicit Yahoo symbol override."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"recommendationKey": "hold"}

        with (
            patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf,
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            get_analyst_data("AAPL.US", yahoo_symbol="AAPL")

        mock_yf.assert_called_with("AAPL")

    def test_returns_none_on_exception(self):
        """Test returning None on exception."""
        with (
            patch("yfinance.Ticker", side_effect=Exception("API error")),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_analyst_data("INVALID")

        assert result is None

    def test_uses_regular_market_price_as_fallback(self):
        """Test using regularMarketPrice when currentPrice missing."""
        mock_info = {
            "recommendationKey": "hold",
            "targetMeanPrice": 100.0,
            "regularMarketPrice": 80.0,
        }

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with (
            patch("yfinance.Ticker", return_value=mock_ticker),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_analyst_data("AAPL.US")

        assert result.current_price == 80.0


class TestGetFundamentalData:
    """Test get_fundamental_data function."""

    def test_returns_fundamental_data(self):
        """Test returning fundamental data when available."""
        mock_info = {
            "trailingPE": 25.5,
            "forwardPE": 22.3,
            "pegRatio": 1.5,
            "priceToBook": 8.2,
            "revenueGrowth": 0.15,
            "earningsGrowth": 0.20,
            "profitMargins": 0.25,
            "operatingMargins": 0.30,
            "returnOnEquity": 0.45,
            "debtToEquity": 50.0,
            "currentRatio": 1.2,
            "marketCap": 3000000000000,
            "dividendYield": 0.005,
            "fiveYearAvgDividendYield": 0.006,
        }

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with (
            patch("yfinance.Ticker", return_value=mock_ticker),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_fundamental_data("AAPL.US")

        assert result is not None
        assert result.symbol == "AAPL.US"
        assert result.pe_ratio == 25.5
        assert result.forward_pe == 22.3
        assert result.profit_margin == 0.25
        assert result.roe == 0.45

    def test_returns_none_on_exception(self):
        """Test returning None on exception."""
        with (
            patch("yfinance.Ticker", side_effect=Exception("API error")),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_fundamental_data("INVALID")

        assert result is None

    def test_uses_yahoo_symbol_override(self):
        """Test using explicit Yahoo symbol override."""
        mock_ticker = MagicMock()
        mock_ticker.info = {}

        with (
            patch("yfinance.Ticker", return_value=mock_ticker) as mock_yf,
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            get_fundamental_data("MSFT.US", yahoo_symbol="MSFT")

        mock_yf.assert_called_with("MSFT")


class TestGetHistoricalPrices:
    """Test get_historical_prices function."""

    def test_returns_historical_prices(self):
        """Test returning historical price data."""
        # Create mock DataFrame
        dates = pd.date_range(start="2024-01-01", periods=3)
        mock_data = pd.DataFrame(
            {
                "Open": [100.0, 101.0, 102.0],
                "High": [105.0, 106.0, 107.0],
                "Low": [99.0, 100.0, 101.0],
                "Close": [104.0, 105.0, 106.0],
                "Volume": [1000000, 1100000, 1200000],
                "Adj Close": [104.0, 105.0, 106.0],
            },
            index=dates,
        )

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_data

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_historical_prices("AAPL.US")

        assert len(result) == 3
        assert result[0].open == 100.0
        assert result[0].close == 104.0
        assert result[0].volume == 1000000

    def test_returns_empty_list_on_exception(self):
        """Test returning empty list on exception."""
        with patch("yfinance.Ticker", side_effect=Exception("API error")):
            result = get_historical_prices("INVALID")

        assert result == []

    def test_uses_custom_period(self):
        """Test using custom period parameter."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch("yfinance.Ticker", return_value=mock_ticker):
            get_historical_prices("AAPL.US", period="5y")

        mock_ticker.history.assert_called_with(period="5y")


class TestGetCurrentPrice:
    """Test get_current_price function."""

    def test_returns_current_price(self):
        """Test returning current price."""
        mock_info = {"currentPrice": 150.0}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with (
            patch("yfinance.Ticker", return_value=mock_ticker),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_current_price("AAPL.US", max_retries=1)

        assert result == 150.0

    def test_uses_regular_market_price_fallback(self):
        """Test using regularMarketPrice when currentPrice missing."""
        mock_info = {"regularMarketPrice": 150.0}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with (
            patch("yfinance.Ticker", return_value=mock_ticker),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_current_price("AAPL.US", max_retries=1)

        assert result == 150.0

    def test_retries_on_invalid_price(self):
        """Test retry logic on invalid price."""
        mock_info_invalid = {"currentPrice": 0}
        mock_info_valid = {"currentPrice": 100.0}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info_invalid

        call_count = 0

        def get_info_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_info_invalid
            return mock_info_valid

        mock_ticker_multi = MagicMock()
        type(mock_ticker_multi).info = property(lambda self: get_info_side_effect())

        with (
            patch("yfinance.Ticker", return_value=mock_ticker_multi),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
            patch("time.sleep"),
        ):
            result = get_current_price("AAPL.US", max_retries=3)

        assert result == 100.0

    def test_returns_none_after_max_retries(self):
        """Test returning None after max retries exhausted."""
        mock_info = {"currentPrice": 0}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with (
            patch("yfinance.Ticker", return_value=mock_ticker),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
            patch("time.sleep"),
        ):
            result = get_current_price("AAPL.US", max_retries=2)

        assert result is None

    def test_retries_on_exception(self):
        """Test retry logic on exception."""
        call_count = 0

        def ticker_side_effect(symbol):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary error")
            mock = MagicMock()
            mock.info = {"currentPrice": 100.0}
            return mock

        with (
            patch("yfinance.Ticker", side_effect=ticker_side_effect),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
            patch("time.sleep"),
        ):
            result = get_current_price("AAPL.US", max_retries=3)

        assert result == 100.0


class TestGetStockIndustry:
    """Test get_security_industry function."""

    def test_returns_technology_industry(self):
        """Test returning actual industry name from Yahoo Finance."""
        mock_info = {"industry": "Consumer Electronics"}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_security_industry("AAPL.US")

        assert result == "Consumer Electronics"

    def test_returns_healthcare_industry(self):
        """Test returning actual industry name from Yahoo Finance."""
        mock_info = {"industry": "Drug Manufacturers"}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_security_industry("PFE.US")

        assert result == "Drug Manufacturers"

    def test_returns_finance_industry(self):
        """Test returning actual industry name from Yahoo Finance."""
        mock_info = {"industry": "Banks - Diversified"}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_security_industry("JPM.US")

        assert result == "Banks - Diversified"

    def test_returns_consumer_industry(self):
        """Test returning actual industry name from Yahoo Finance."""
        mock_info = {"industry": "Retail - Apparel"}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_security_industry("NKE.US")

        assert result == "Retail - Apparel"

    def test_returns_industrial_industry(self):
        """Test returning actual industry name from Yahoo Finance."""
        mock_info = {"industry": "Aerospace & Defense"}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_security_industry("BA.US")

        assert result == "Aerospace & Defense"

    def test_returns_energy_industry(self):
        """Test returning actual industry name from Yahoo Finance."""
        mock_info = {"industry": "Oil & Gas Integrated"}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_security_industry("XOM.US")

        assert result == "Oil & Gas Integrated"

    def test_falls_back_to_sector(self):
        """Test falling back to sector when industry missing."""
        mock_info = {"sector": "Consumer Electronics"}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_security_industry("AAPL.US")

        assert result == "Consumer Electronics"

    def test_returns_original_if_no_match(self):
        """Test returning original industry if no category match."""
        mock_info = {"industry": "Unknown Sector XYZ"}

        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = get_security_industry("UNKNOWN.US")

        assert result == "Unknown Sector XYZ"

    def test_returns_none_on_exception(self):
        """Test returning None on exception."""
        with patch("yfinance.Ticker", side_effect=Exception("API error")):
            result = get_security_industry("INVALID")

        assert result is None


class TestGetBatchQuotes:
    """Test get_batch_quotes function."""

    def test_returns_batch_quotes_single_symbol(self):
        """Test returning batch quotes for single symbol."""
        dates = pd.date_range(start="2024-01-01", periods=3)
        mock_data = pd.DataFrame(
            {"Close": [100.0, 101.0, 102.0]},
            index=dates,
        )

        with (
            patch("yfinance.download", return_value=mock_data),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_batch_quotes({"AAPL.US": None})

        assert "AAPL.US" in result
        assert result["AAPL.US"] == 102.0

    def test_returns_batch_quotes_multiple_symbols(self):
        """Test returning batch quotes for multiple symbols."""
        dates = pd.date_range(start="2024-01-01", periods=3)
        mock_data = pd.DataFrame(
            {
                ("Close", "AAPL"): [100.0, 101.0, 102.0],
                ("Close", "MSFT"): [200.0, 201.0, 202.0],
            },
            index=dates,
        )
        mock_data.columns = pd.MultiIndex.from_tuples(
            [("Close", "AAPL"), ("Close", "MSFT")]
        )

        with (
            patch("yfinance.download", return_value=mock_data),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_batch_quotes({"AAPL.US": None, "MSFT.US": None})

        assert "AAPL.US" in result
        assert "MSFT.US" in result
        assert result["AAPL.US"] == 102.0
        assert result["MSFT.US"] == 202.0

    def test_handles_empty_data(self):
        """Test handling empty data response."""
        mock_data = pd.DataFrame()

        with (
            patch("yfinance.download", return_value=mock_data),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_batch_quotes({"AAPL.US": None})

        assert result == {}

    def test_handles_exception(self):
        """Test handling exception."""
        with (
            patch("yfinance.download", side_effect=Exception("API error")),
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            result = get_batch_quotes({"AAPL.US": None})

        assert result == {}

    def test_uses_yahoo_symbol_override(self):
        """Test using Yahoo symbol override in batch."""
        mock_data = pd.DataFrame()

        with (
            patch("yfinance.download", return_value=mock_data) as mock_download,
            patch("app.infrastructure.external.yahoo.data_fetchers.emit"),
        ):
            get_batch_quotes({"AAPL.US": "AAPL"})

        # Should use the override symbol
        call_args = mock_download.call_args
        assert "AAPL" in call_args.kwargs.get("tickers", "")


class TestLedApiCall:
    """Test the _led_api_call context manager."""

    def test_emits_events(self):
        """Test that API call emits start and end events."""
        from app.infrastructure.external.yahoo.data_fetchers import _led_api_call

        with patch("app.infrastructure.external.yahoo.data_fetchers.emit") as mock_emit:
            with _led_api_call():
                pass

        assert mock_emit.call_count == 2

    def test_emits_end_event_on_exception(self):
        """Test that end event is emitted even on exception."""
        from app.infrastructure.external.yahoo.data_fetchers import _led_api_call

        with patch("app.infrastructure.external.yahoo.data_fetchers.emit") as mock_emit:
            try:
                with _led_api_call():
                    raise ValueError("test error")
            except ValueError:
                pass

        assert mock_emit.call_count == 2
