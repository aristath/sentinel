"""Tests for symbol resolver service.

These tests validate symbol resolution between Tradernet, ISIN, and Yahoo formats,
including identifier type detection, conversion, and caching.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models import Stock
from app.modules.universe.domain.symbol_resolver import (
    IdentifierType,
    SymbolInfo,
    SymbolResolver,
    detect_identifier_type,
    is_isin,
    is_tradernet_format,
    tradernet_to_yahoo,
)


class TestIsIsin:
    """Test is_isin function."""

    def test_returns_true_for_valid_isin(self):
        """Test that valid ISINs are recognized."""
        assert is_isin("US0378331005") is True
        assert is_isin("DE0007164600") is True
        assert is_isin("ES0113900J37") is True

    def test_returns_false_for_invalid_isin(self):
        """Test that invalid ISINs are rejected."""
        assert is_isin("AAPL") is False
        assert is_isin("AAPL.US") is False
        assert is_isin("US037833100") is False  # Too short
        assert is_isin("US03783310055") is False  # Too long
        assert is_isin("") is False

    def test_is_case_insensitive(self):
        """Test that ISIN check is case insensitive."""
        assert is_isin("us0378331005") is True
        assert is_isin("US0378331005") is True


class TestIsTradernetFormat:
    """Test is_tradernet_format function."""

    def test_returns_true_for_tradernet_symbols(self):
        """Test that Tradernet format symbols are recognized."""
        assert is_tradernet_format("AAPL.US") is True
        assert is_tradernet_format("SAP.DE") is True
        assert is_tradernet_format("SAN.EU") is True

    def test_returns_false_for_non_tradernet_symbols(self):
        """Test that non-Tradernet symbols are rejected."""
        assert is_tradernet_format("AAPL") is False
        assert is_tradernet_format("US0378331005") is False
        assert is_tradernet_format("") is False

    def test_is_case_insensitive(self):
        """Test that Tradernet format check is case insensitive."""
        assert is_tradernet_format("aapl.us") is True
        assert is_tradernet_format("AAPL.US") is True


class TestDetectIdentifierType:
    """Test detect_identifier_type function."""

    def test_detects_isin(self):
        """Test that ISINs are detected correctly."""
        assert detect_identifier_type("US0378331005") == IdentifierType.ISIN

    def test_detects_tradernet_format(self):
        """Test that Tradernet format is detected correctly."""
        assert detect_identifier_type("AAPL.US") == IdentifierType.TRADERNET

    def test_detects_yahoo_format(self):
        """Test that Yahoo format is detected correctly."""
        assert detect_identifier_type("AAPL") == IdentifierType.YAHOO


class TestTradernetToYahoo:
    """Test tradernet_to_yahoo function."""

    def test_strips_us_suffix(self):
        """Test that .US suffix is stripped."""
        result = tradernet_to_yahoo("AAPL.US")
        assert result == "AAPL"

    def test_converts_greek_to_athens(self):
        """Test that .GR suffix is converted to .AT."""
        result = tradernet_to_yahoo("OPAP.GR")
        assert result == "OPAP.AT"

    def test_passes_through_other_suffixes(self):
        """Test that other suffixes pass through unchanged."""
        result = tradernet_to_yahoo("SAP.DE")
        assert result == "SAP.DE"

        result = tradernet_to_yahoo("SAN.EU")
        assert result == "SAN.EU"

    def test_is_case_insensitive(self):
        """Test that conversion is case insensitive."""
        result = tradernet_to_yahoo("aapl.us")
        assert result == "AAPL"


class TestSymbolResolver:
    """Test SymbolResolver class."""

    @pytest.fixture
    def mock_tradernet_client(self):
        """Mock TradernetClient."""
        client = MagicMock()
        client.is_connected = True
        client.get_quotes_raw.return_value = {
            "result": {"q": [{"issue_nb": "US0378331005"}]}
        }
        return client

    @pytest.fixture
    def mock_stock_repo(self):
        """Mock StockRepository."""
        repo = AsyncMock()
        return repo

    def test_detect_type_delegates_to_function(self, mock_tradernet_client):
        """Test that detect_type delegates to detect_identifier_type."""
        resolver = SymbolResolver(mock_tradernet_client)

        assert resolver.detect_type("AAPL.US") == IdentifierType.TRADERNET
        assert resolver.detect_type("US0378331005") == IdentifierType.ISIN
        assert resolver.detect_type("AAPL") == IdentifierType.YAHOO

    @pytest.mark.asyncio
    async def test_resolve_isin_returns_directly(self, mock_tradernet_client):
        """Test that ISIN identifiers are resolved directly."""
        resolver = SymbolResolver(mock_tradernet_client)

        result = await resolver.resolve("US0378331005")

        assert result.isin == "US0378331005"
        assert result.yahoo_symbol == "US0378331005"
        assert result.tradernet_symbol is None

    @pytest.mark.asyncio
    async def test_resolve_yahoo_returns_as_is(self, mock_tradernet_client):
        """Test that Yahoo format identifiers are returned as-is."""
        resolver = SymbolResolver(mock_tradernet_client)

        result = await resolver.resolve("AAPL")

        assert result.yahoo_symbol == "AAPL"
        assert result.isin is None
        assert result.tradernet_symbol is None

    @pytest.mark.asyncio
    async def test_resolve_tradernet_with_cached_isin(
        self, mock_tradernet_client, mock_stock_repo
    ):
        """Test resolving Tradernet symbol when ISIN is cached."""
        from app.domain.models import Stock

        mock_stock = Stock(
            symbol="AAPL.US",
            name="Apple",
            isin="US0378331005",
            country="US",
        )
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        resolver = SymbolResolver(mock_tradernet_client, mock_stock_repo)

        result = await resolver.resolve("AAPL.US")

        assert result.tradernet_symbol == "AAPL.US"
        assert result.isin == "US0378331005"
        assert result.yahoo_symbol == "US0378331005"  # Uses ISIN for Yahoo
        mock_stock_repo.get_by_symbol.assert_called_once_with("AAPL.US")

    @pytest.mark.asyncio
    async def test_resolve_tradernet_without_cached_isin_fetches_from_api(
        self, mock_tradernet_client
    ):
        """Test resolving Tradernet symbol when ISIN is not cached."""
        resolver = SymbolResolver(mock_tradernet_client)

        result = await resolver.resolve("AAPL.US")

        assert result.tradernet_symbol == "AAPL.US"
        assert result.isin == "US0378331005"
        assert result.yahoo_symbol == "US0378331005"
        mock_tradernet_client.get_quotes_raw.assert_called_once_with(["AAPL.US"])

    @pytest.mark.asyncio
    async def test_resolve_tradernet_falls_back_to_yahoo_conversion(
        self, mock_tradernet_client
    ):
        """Test that Tradernet symbol falls back to Yahoo conversion when ISIN not available."""
        mock_tradernet_client.get_quotes_raw.return_value = {
            "result": {"q": [{"issue_nb": None}]}  # No ISIN in response
        }

        resolver = SymbolResolver(mock_tradernet_client)

        result = await resolver.resolve("AAPL.US")

        assert result.tradernet_symbol == "AAPL.US"
        assert result.isin is None
        assert result.yahoo_symbol == "AAPL"  # Falls back to converted symbol

    @pytest.mark.asyncio
    async def test_resolve_and_cache_caches_isin(
        self, mock_tradernet_client, mock_stock_repo
    ):
        """Test that resolve_and_cache caches ISIN when found."""
        mock_stock = Stock(symbol="AAPL.US", name="Apple", isin=None, country="US")
        mock_stock_repo.get_by_symbol.return_value = mock_stock
        mock_tradernet_client.get_quotes_raw.return_value = {
            "result": {"q": [{"issue_nb": "US0378331005"}]}
        }

        resolver = SymbolResolver(mock_tradernet_client, mock_stock_repo)

        result = await resolver.resolve_and_cache("AAPL.US")

        assert result.isin == "US0378331005"
        mock_stock_repo.update.assert_called_once_with("AAPL.US", isin="US0378331005")

    @pytest.mark.asyncio
    async def test_resolve_to_isin_returns_isin_directly(self, mock_tradernet_client):
        """Test that resolve_to_isin returns ISIN when provided directly."""
        resolver = SymbolResolver(mock_tradernet_client)

        result = await resolver.resolve_to_isin("US0378331005")

        assert result == "US0378331005"

    @pytest.mark.asyncio
    async def test_resolve_to_isin_resolves_tradernet_symbol(
        self, mock_tradernet_client
    ):
        """Test that resolve_to_isin resolves Tradernet symbol to ISIN."""
        resolver = SymbolResolver(mock_tradernet_client)

        result = await resolver.resolve_to_isin("AAPL.US")

        assert result == "US0378331005"

    @pytest.mark.asyncio
    async def test_get_symbol_for_display_returns_symbol_for_isin(
        self, mock_tradernet_client, mock_stock_repo
    ):
        """Test that get_symbol_for_display returns symbol for ISIN."""
        from app.domain.models import Stock

        mock_stock = Stock(
            symbol="AAPL.US", name="Apple", isin="US0378331005", country="US"
        )
        mock_stock_repo.get_by_isin.return_value = mock_stock

        resolver = SymbolResolver(mock_tradernet_client, mock_stock_repo)

        result = await resolver.get_symbol_for_display("US0378331005")

        assert result == "AAPL.US"
        mock_stock_repo.get_by_isin.assert_called_once_with("US0378331005")

    @pytest.mark.asyncio
    async def test_get_symbol_for_display_returns_input_if_not_found(
        self, mock_tradernet_client, mock_stock_repo
    ):
        """Test that get_symbol_for_display returns input if symbol not found."""
        mock_stock_repo.get_by_isin.return_value = None

        resolver = SymbolResolver(mock_tradernet_client, mock_stock_repo)

        result = await resolver.get_symbol_for_display("US0378331005")

        assert result == "US0378331005"

    @pytest.mark.asyncio
    async def test_get_symbol_for_display_returns_symbol_as_is(
        self, mock_tradernet_client
    ):
        """Test that get_symbol_for_display returns symbol as-is if not ISIN."""
        resolver = SymbolResolver(mock_tradernet_client)

        result = await resolver.get_symbol_for_display("AAPL.US")

        assert result == "AAPL.US"

    @pytest.mark.asyncio
    async def test_get_isin_for_symbol_returns_isin_from_repo(
        self, mock_tradernet_client, mock_stock_repo
    ):
        """Test that get_isin_for_symbol returns ISIN from repository."""
        from app.domain.models import Stock

        mock_stock = Stock(
            symbol="AAPL.US", name="Apple", isin="US0378331005", country="US"
        )
        mock_stock_repo.get_by_symbol.return_value = mock_stock

        resolver = SymbolResolver(mock_tradernet_client, mock_stock_repo)

        result = await resolver.get_isin_for_symbol("AAPL.US")

        assert result == "US0378331005"

    @pytest.mark.asyncio
    async def test_get_isin_for_symbol_returns_none_if_not_found(
        self, mock_tradernet_client, mock_stock_repo
    ):
        """Test that get_isin_for_symbol returns None if symbol not found."""
        mock_stock_repo.get_by_symbol.return_value = None

        resolver = SymbolResolver(mock_tradernet_client, mock_stock_repo)

        result = await resolver.get_isin_for_symbol("UNKNOWN.US")

        assert result is None

    @pytest.mark.asyncio
    async def test_handles_tradernet_not_connected(self, mock_tradernet_client):
        """Test handling when Tradernet client is not connected."""
        mock_tradernet_client.is_connected = False

        resolver = SymbolResolver(mock_tradernet_client)

        result = await resolver.resolve("AAPL.US")

        # Should fall back to Yahoo conversion when not connected
        assert result.tradernet_symbol == "AAPL.US"
        assert result.isin is None
        assert result.yahoo_symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_handles_tradernet_api_error(self, mock_tradernet_client):
        """Test handling when Tradernet API returns error."""
        mock_tradernet_client.get_quotes_raw.side_effect = Exception("API Error")

        resolver = SymbolResolver(mock_tradernet_client)

        result = await resolver.resolve("AAPL.US")

        # Should fall back to Yahoo conversion on error
        assert result.tradernet_symbol == "AAPL.US"
        assert result.isin is None
        assert result.yahoo_symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_handles_invalid_tradernet_response(self, mock_tradernet_client):
        """Test handling when Tradernet returns invalid response format."""
        mock_tradernet_client.get_quotes_raw.return_value = None

        resolver = SymbolResolver(mock_tradernet_client)

        result = await resolver.resolve("AAPL.US")

        # Should fall back to Yahoo conversion on invalid response
        assert result.tradernet_symbol == "AAPL.US"
        assert result.isin is None
        assert result.yahoo_symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_strips_and_uppercases_identifier(self, mock_tradernet_client):
        """Test that identifier is stripped and uppercased."""
        resolver = SymbolResolver(mock_tradernet_client)

        result = await resolver.resolve("  aapl.us  ")

        assert result.tradernet_symbol == "AAPL.US"

    def test_symbol_info_has_isin_property(self):
        """Test that SymbolInfo.has_isin property works correctly."""
        info_with_isin = SymbolInfo(
            tradernet_symbol="AAPL.US", isin="US0378331005", yahoo_symbol="US0378331005"
        )
        assert info_with_isin.has_isin is True

        info_without_isin = SymbolInfo(
            tradernet_symbol="AAPL.US", isin=None, yahoo_symbol="AAPL"
        )
        assert info_without_isin.has_isin is False
