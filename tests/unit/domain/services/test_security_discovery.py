"""Tests for stock discovery service.

These tests validate the stock discovery logic for finding new investment opportunities.
CRITICAL: Tests catch real bugs that would cause poor stock selection or API abuse.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


def create_mock_security(
    symbol: str, exchange: str = "usa", volume: float = 5000000.0
) -> dict:
    """Helper to create mock security data from Tradernet API."""
    return {
        "symbol": symbol,
        "exchange": exchange,
        "volume": volume,
        "name": f"{symbol} Inc.",
        "country": "US" if exchange == "usa" else "EU",
    }


class TestFilteringLogic:
    """Test filtering logic for stock discovery."""

    @pytest.mark.asyncio
    async def test_filters_by_geography_correctly(self):
        """Test that geography filtering works correctly.

        Bug caught: Wrong geography stocks included, violating user preferences.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = [
            create_mock_security("AAPL", "usa", 10000000.0),
            create_mock_security("ASML", "europe", 8000000.0),
            create_mock_security("9988", "asia", 6000000.0),
        ]

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "EU",
                "stock_discovery_exchanges": "europe",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        candidates = await service.discover_candidates(existing_symbols=[])

        # Should only include European stocks
        assert len(candidates) == 1
        assert candidates[0]["symbol"] == "ASML"

    @pytest.mark.asyncio
    async def test_filters_by_exchange_correctly(self):
        """Test that exchange filtering works correctly.

        Bug caught: Wrong exchange stocks included.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = [
            create_mock_security("AAPL", "usa", 10000000.0),
            create_mock_security("MSFT", "usa", 9000000.0),
            create_mock_security("ASML", "europe", 8000000.0),
        ]

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US,EU",
                "stock_discovery_exchanges": "usa",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        candidates = await service.discover_candidates(existing_symbols=[])

        # Should only include USA exchange stocks
        assert len(candidates) == 2
        assert all(c["exchange"] == "usa" for c in candidates)

    @pytest.mark.asyncio
    async def test_filters_by_min_volume(self):
        """Test that minimum volume filtering works.

        Bug caught: Low-liquidity stocks included, hard to trade.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = [
            create_mock_security("AAPL", "usa", 10000000.0),
            create_mock_security("LOWVOL", "usa", 500000.0),  # Below threshold
            create_mock_security("MSFT", "usa", 8000000.0),
        ]

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,  # 1M threshold
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US",
                "stock_discovery_exchanges": "usa",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        candidates = await service.discover_candidates(existing_symbols=[])

        # Should exclude LOWVOL (below threshold)
        assert len(candidates) == 2
        assert all(c["volume"] >= 1000000.0 for c in candidates)

    @pytest.mark.asyncio
    async def test_excludes_stocks_already_in_universe(self):
        """Test that existing stocks are excluded.

        Bug caught: Duplicate stocks added to universe.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = [
            create_mock_security("AAPL", "usa", 10000000.0),
            create_mock_security("MSFT", "usa", 9000000.0),
            create_mock_security("GOOGL", "usa", 8000000.0),
        ]

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US",
                "stock_discovery_exchanges": "usa",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        existing_symbols = ["AAPL", "MSFT"]
        candidates = await service.discover_candidates(
            existing_symbols=existing_symbols
        )

        # Should exclude AAPL and MSFT
        assert len(candidates) == 1
        assert candidates[0]["symbol"] == "GOOGL"

    @pytest.mark.asyncio
    async def test_respects_fetch_limit(self):
        """Test that fetch limit is respected.

        Bug caught: Too many candidates fetched, API rate limits.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        # Generate many mock securities
        many_securities = [
            create_mock_security(f"STOCK{i}", "usa", 10000000.0) for i in range(100)
        ]

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = many_securities

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 10.0,  # Limit to 10
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US",
                "stock_discovery_exchanges": "usa",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        candidates = await service.discover_candidates(existing_symbols=[])

        # Should respect fetch limit
        assert len(candidates) <= 10


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_exactly_at_min_volume_includes_stock(self):
        """Test that stocks exactly at min_volume threshold are included.

        Bug caught: Off-by-one at threshold.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = [
            create_mock_security("EXACT", "usa", 1000000.0),  # Exactly at threshold
        ]

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US",
                "stock_discovery_exchanges": "usa",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        candidates = await service.discover_candidates(existing_symbols=[])

        # Should include stock at exact threshold (>=)
        assert len(candidates) == 1
        assert candidates[0]["symbol"] == "EXACT"

    @pytest.mark.asyncio
    async def test_empty_universe_returns_all_candidates(self):
        """Test that empty universe returns all valid candidates.

        Bug caught: No candidates when universe empty.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = [
            create_mock_security("AAPL", "usa", 10000000.0),
            create_mock_security("MSFT", "usa", 9000000.0),
        ]

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US",
                "stock_discovery_exchanges": "usa",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        candidates = await service.discover_candidates(existing_symbols=[])

        # Should return all valid candidates
        assert len(candidates) == 2

    @pytest.mark.asyncio
    async def test_very_large_fetch_limit_handles_gracefully(self):
        """Test that very large fetch limit is handled gracefully.

        Bug caught: Memory issues or API errors.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = [
            create_mock_security("AAPL", "usa", 10000000.0),
        ]

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 1000000.0,  # Very large limit
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US",
                "stock_discovery_exchanges": "usa",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        # Should not crash with very large limit
        candidates = await service.discover_candidates(existing_symbols=[])
        assert isinstance(candidates, list)

    @pytest.mark.asyncio
    async def test_all_stocks_in_universe_returns_empty(self):
        """Test that all candidates in universe returns empty list.

        Bug caught: Returns duplicates.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = [
            create_mock_security("AAPL", "usa", 10000000.0),
            create_mock_security("MSFT", "usa", 9000000.0),
        ]

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US",
                "stock_discovery_exchanges": "usa",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        existing_symbols = ["AAPL", "MSFT"]
        candidates = await service.discover_candidates(
            existing_symbols=existing_symbols
        )

        # Should return empty (all candidates already in universe)
        assert len(candidates) == 0


class TestSettingsIntegration:
    """Test settings integration."""

    @pytest.mark.asyncio
    async def test_uses_custom_geography_list(self):
        """Test that custom geography list is used.

        Bug caught: Ignores user geography settings.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = [
            create_mock_security("AAPL", "usa", 10000000.0),
            create_mock_security("ASML", "europe", 8000000.0),
        ]

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "ASIA",  # Custom: only ASIA
                "stock_discovery_exchanges": "asia",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        candidates = await service.discover_candidates(existing_symbols=[])

        # Should only include ASIA stocks (none in this case)
        assert len(candidates) == 0  # No ASIA stocks in mock data

    @pytest.mark.asyncio
    async def test_parses_comma_separated_settings(self):
        """Test that comma-separated settings are parsed correctly.

        Bug caught: Settings not parsed correctly.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()

        # Return exchange-specific results to avoid duplicates
        def get_most_traded_by_exchange(**kwargs):
            exchange = kwargs.get("exchange", "")
            if exchange == "usa":
                return [
                    create_mock_security("AAPL", "usa", 10000000.0),
                ]
            elif exchange == "europe":
                return [
                    create_mock_security("ASML", "europe", 8000000.0),
                ]
            return []

        mock_client.get_most_traded.side_effect = get_most_traded_by_exchange

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US,EU",  # Comma-separated
                "stock_discovery_exchanges": "usa,europe",  # Comma-separated
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        candidates = await service.discover_candidates(existing_symbols=[])

        # Should include US and EU stocks (not ASIA)
        assert len(candidates) == 2
        assert all(c["symbol"] in ["AAPL", "ASML"] for c in candidates)


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_api_failure_returns_empty_list(self):
        """Test that API failure returns empty list.

        Bug caught: Crashes on API failure.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.side_effect = Exception("API error")

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US",
                "stock_discovery_exchanges": "usa",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        # Should not raise exception, return empty list
        candidates = await service.discover_candidates(existing_symbols=[])
        assert candidates == []
        assert candidates == []

    @pytest.mark.asyncio
    async def test_uses_custom_exchange_list(self):
        """Test that custom exchange list is used.

        Bug caught: Ignores user exchange settings.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = [
            create_mock_security("AAPL", "usa", 10000000.0),
            create_mock_security("ASML", "europe", 8000000.0),
        ]

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US,EU",
                "stock_discovery_exchanges": "europe",  # Custom: only europe
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        candidates = await service.discover_candidates(existing_symbols=[])

        # Should only include europe exchange stocks
        assert len(candidates) == 1
        assert candidates[0]["symbol"] == "ASML"

    @pytest.mark.asyncio
    async def test_uses_custom_min_volume(self):
        """Test that custom min_volume is used.

        Bug caught: Wrong liquidity threshold.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = [
            create_mock_security("AAPL", "usa", 10000000.0),
            create_mock_security("LOWVOL", "usa", 2000000.0),  # Above custom threshold
        ]

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 5000000.0,  # Custom: 5M threshold
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US",
                "stock_discovery_exchanges": "usa",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        candidates = await service.discover_candidates(existing_symbols=[])

        # Should only include stocks above custom 5M threshold
        assert len(candidates) == 1
        assert candidates[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_invalid_api_response_handles_gracefully(self):
        """Test that invalid API response is handled gracefully.

        Bug caught: Crashes on malformed data.
        """
        from app.domain.services.security_discovery import SecurityDiscoveryService

        mock_client = MagicMock()
        mock_client.get_most_traded.return_value = None  # Invalid response

        mock_settings_repo = AsyncMock()

        async def get_float(key, default):
            return {
                "stock_discovery_enabled": 1.0,
                "stock_discovery_min_volume": 1000000.0,
                "stock_discovery_fetch_limit": 50.0,
            }.get(key, default)

        async def get(key):
            return {
                "stock_discovery_geographies": "US",
                "stock_discovery_exchanges": "usa",
            }.get(key)

        mock_settings_repo.get_float = AsyncMock(side_effect=get_float)
        mock_settings_repo.get = AsyncMock(side_effect=get)

        service = SecurityDiscoveryService(
            tradernet_client=mock_client,
            settings_repo=mock_settings_repo,
        )

        # Should not raise exception, return empty list
        candidates = await service.discover_candidates(existing_symbols=[])
        assert candidates == []
