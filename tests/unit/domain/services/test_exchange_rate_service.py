"""Tests for ExchangeRateService.

These tests verify the currency conversion logic which is CRITICAL
for accurate portfolio valuation and trade execution in multi-currency environments.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.services.exchange_rate_service import (
    EXCHANGE_RATE_TTL_SECONDS,
    FALLBACK_RATES,
    ExchangeRateService,
)


class TestExchangeRateServiceBasic:
    """Test basic exchange rate functionality."""

    @pytest.mark.asyncio
    async def test_same_currency_returns_one(self):
        """Test that same currency conversion returns 1.0."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        rate = await service.get_rate("EUR", "EUR")
        assert rate == 1.0

        rate = await service.get_rate("USD", "USD")
        assert rate == 1.0

    @pytest.mark.asyncio
    async def test_normalizes_currency_codes(self):
        """Test that currency codes are normalized to uppercase."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        rate1 = await service.get_rate("eur", "eur")
        rate2 = await service.get_rate("EUR", "EUR")
        rate3 = await service.get_rate("Eur", "Eur")

        assert rate1 == rate2 == rate3 == 1.0


class TestExchangeRateServiceCaching:
    """Test caching behavior."""

    @pytest.mark.asyncio
    async def test_uses_memory_cache(self):
        """Test that memory cache is checked first."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        # Pre-populate memory cache
        service._memory_cache["USD_EUR"] = (1.05, datetime.now())

        rate = await service.get_rate("USD", "EUR")

        assert rate == 1.05
        # DB should not be called
        mock_db.cache.fetchone.assert_not_called()

    @pytest.mark.asyncio
    async def test_memory_cache_expires(self):
        """Test that expired memory cache is not used."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()
        mock_db.cache.fetchone.return_value = None

        service = ExchangeRateService(db_manager=mock_db, ttl_seconds=60)

        # Pre-populate memory cache with expired entry
        expired_time = datetime.now() - timedelta(seconds=120)
        service._memory_cache["USD_EUR"] = (1.05, expired_time)

        with patch.object(
            service, "_fetch_rate_from_api", return_value=1.08
        ) as mock_fetch:
            rate = await service.get_rate("USD", "EUR")

            # Should have fetched fresh rate
            mock_fetch.assert_called_once()
            assert rate == 1.08

    @pytest.mark.asyncio
    async def test_uses_db_cache_when_memory_empty(self):
        """Test that DB cache is checked when memory cache is empty."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()

        # Setup DB cache to return a valid rate
        future_expiry = (datetime.now() + timedelta(hours=1)).isoformat()
        mock_db.cache.fetchone.return_value = {
            "rate": 1.06,
            "expires_at": future_expiry,
        }

        service = ExchangeRateService(db_manager=mock_db)

        rate = await service.get_rate("USD", "EUR")

        assert rate == 1.06
        mock_db.cache.fetchone.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_cache_expires(self):
        """Test that expired DB cache is not used."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()

        # Setup DB cache with expired entry
        past_expiry = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_db.cache.fetchone.return_value = {"rate": 1.06, "expires_at": past_expiry}

        service = ExchangeRateService(db_manager=mock_db)

        with patch.object(
            service, "_fetch_rate_from_api", return_value=1.09
        ) as mock_fetch:
            rate = await service.get_rate("USD", "EUR")

            # Should have fetched fresh rate
            mock_fetch.assert_called_once()
            assert rate == 1.09


class TestExchangeRateServiceConversion:
    """Test currency conversion."""

    @pytest.mark.asyncio
    async def test_convert_zero_amount(self):
        """Test that converting zero returns zero."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        result = await service.convert(0, "USD", "EUR")
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_convert_uses_rate_correctly(self):
        """Test that conversion uses rate correctly."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        # Pre-populate cache with rate: 1 EUR = 1.05 USD
        service._memory_cache["USD_EUR"] = (1.05, datetime.now())

        # 100 USD / 1.05 = 95.24 EUR
        result = await service.convert(100, "USD", "EUR")
        assert result == pytest.approx(95.238, rel=0.01)

    @pytest.mark.asyncio
    async def test_convert_handles_invalid_rate(self):
        """Test that conversion handles invalid rates gracefully."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        # Pre-populate cache with invalid rate (zero)
        service._memory_cache["BAD_EUR"] = (0, datetime.now())

        # Should return original amount as fallback
        result = await service.convert(100, "BAD", "EUR")
        assert result == 100

    @pytest.mark.asyncio
    async def test_batch_convert_to_eur(self):
        """Test batch conversion to EUR."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        # Pre-populate cache
        service._memory_cache["USD_EUR"] = (1.05, datetime.now())
        service._memory_cache["GBP_EUR"] = (0.85, datetime.now())

        amounts = {"USD": 100, "GBP": 50}
        result = await service.batch_convert_to_eur(amounts)

        assert "USD" in result
        assert "GBP" in result
        assert result["USD"] == pytest.approx(95.238, rel=0.01)  # 100 / 1.05
        assert result["GBP"] == pytest.approx(58.824, rel=0.01)  # 50 / 0.85


class TestExchangeRateServiceFallback:
    """Test fallback rate behavior."""

    def test_fallback_rate_direct_lookup(self):
        """Test that fallback rates are found by direct lookup."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        rate = service._get_fallback_rate("USD", "EUR")
        assert rate == FALLBACK_RATES[("USD", "EUR")]

    def test_fallback_rate_reverse_lookup(self):
        """Test that fallback rates work in reverse."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        # If we have USD->EUR, we should be able to get EUR->USD
        usd_eur = FALLBACK_RATES.get(("USD", "EUR"), 1.05)
        expected_eur_usd = 1.0 / usd_eur

        # But EUR->USD has its own entry, so use that
        rate = service._get_fallback_rate("EUR", "USD")
        assert rate == FALLBACK_RATES[("EUR", "USD")]

    def test_fallback_rate_via_eur(self):
        """Test fallback rates via EUR intermediary."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        # For USD->GBP, should go via EUR
        # USD->EUR / GBP->EUR
        usd_eur = FALLBACK_RATES[("USD", "EUR")]
        gbp_eur = FALLBACK_RATES[("GBP", "EUR")]
        expected = usd_eur / gbp_eur

        rate = service._get_fallback_rate("USD", "GBP")
        assert rate == pytest.approx(expected, rel=0.01)

    def test_fallback_rate_unknown_currency(self):
        """Test that unknown currency pairs return 1.0."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        rate = service._get_fallback_rate("XYZ", "ABC")
        assert rate == 1.0

    @pytest.mark.asyncio
    async def test_uses_fallback_when_api_fails(self):
        """Test that fallback rate is used when API fails."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()
        mock_db.cache.fetchone.return_value = None

        service = ExchangeRateService(db_manager=mock_db)

        with patch.object(service, "_fetch_rate_from_api", return_value=None):
            rate = await service.get_rate("USD", "EUR")

            # Should use fallback rate
            assert rate == FALLBACK_RATES[("USD", "EUR")]


class TestExchangeRateServiceAPI:
    """Test API fetching."""

    @pytest.mark.asyncio
    async def test_fetch_rate_from_api_success(self):
        """Test successful API rate fetch."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()
        service = ExchangeRateService(db_manager=mock_db)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rates": {"USD": 1.05, "GBP": 0.85}}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            rate = await service._fetch_rate_from_api("USD", "EUR")

            assert rate == 1.05

    @pytest.mark.asyncio
    async def test_fetch_rate_from_api_timeout(self):
        """Test API timeout handling."""
        import httpx

        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.side_effect = httpx.TimeoutException("Timeout")

            rate = await service._fetch_rate_from_api("USD", "EUR")

            assert rate is None

    @pytest.mark.asyncio
    async def test_fetch_rate_from_api_error_status(self):
        """Test API error status handling."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            rate = await service._fetch_rate_from_api("USD", "EUR")

            assert rate is None

    @pytest.mark.asyncio
    async def test_fetch_rate_caches_all_rates(self):
        """Test that API response caches all supported rates."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()
        service = ExchangeRateService(db_manager=mock_db)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {"USD": 1.05, "GBP": 0.85, "HKD": 8.33, "JPY": 160.0}
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            await service._fetch_rate_from_api("USD", "EUR")

            # Should have cached supported currencies
            assert "USD_EUR" in service._memory_cache
            assert "GBP_EUR" in service._memory_cache
            assert "HKD_EUR" in service._memory_cache
            # JPY is not in supported list, should not be cached
            assert "JPY_EUR" not in service._memory_cache


class TestExchangeRateServiceRefresh:
    """Test rate refresh functionality."""

    @pytest.mark.asyncio
    async def test_refresh_rates_updates_cache(self):
        """Test that refresh_rates updates the cache."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()
        service = ExchangeRateService(db_manager=mock_db)

        with patch.object(service, "_fetch_rate_from_api", return_value=1.10):
            await service.refresh_rates(["USD"])

            # Should have updated memory cache
            assert "USD_EUR" in service._memory_cache
            rate, _ = service._memory_cache["USD_EUR"]
            assert rate == 1.10

    @pytest.mark.asyncio
    async def test_refresh_rates_default_currencies(self):
        """Test that refresh_rates uses default currencies when none specified."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()
        service = ExchangeRateService(db_manager=mock_db)

        call_count = 0

        async def mock_fetch(from_curr, to_curr):
            nonlocal call_count
            call_count += 1
            return 1.0

        with patch.object(service, "_fetch_rate_from_api", side_effect=mock_fetch):
            await service.refresh_rates()

            # Should have fetched USD, HKD, GBP
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_refresh_rates_skips_eur(self):
        """Test that refresh_rates skips EUR (base currency)."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()
        service = ExchangeRateService(db_manager=mock_db)

        with patch.object(
            service, "_fetch_rate_from_api", return_value=1.0
        ) as mock_fetch:
            await service.refresh_rates(["EUR", "USD"])

            # Should only call for USD, not EUR
            assert mock_fetch.call_count == 1
            mock_fetch.assert_called_with("USD", "EUR")


class TestExchangeRateServiceDBOperations:
    """Test database operations."""

    @pytest.mark.asyncio
    async def test_store_in_db_cache(self):
        """Test storing rate in DB cache."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()

        service = ExchangeRateService(db_manager=mock_db)

        await service._store_in_db_cache("USD", "EUR", 1.05)

        mock_db.cache.execute.assert_called_once()
        mock_db.cache.commit.assert_called_once()

        # Verify the SQL and parameters
        call_args = mock_db.cache.execute.call_args
        assert "INSERT OR REPLACE INTO exchange_rates" in call_args[0][0]
        params = call_args[0][1]
        assert params[0] == "USD"
        assert params[1] == "EUR"
        assert params[2] == 1.05

    @pytest.mark.asyncio
    async def test_store_in_db_cache_handles_error(self):
        """Test that DB cache errors are handled gracefully."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()
        mock_db.cache.execute.side_effect = Exception("DB error")

        service = ExchangeRateService(db_manager=mock_db)

        # Should not raise
        await service._store_in_db_cache("USD", "EUR", 1.05)

    @pytest.mark.asyncio
    async def test_get_from_db_cache_handles_error(self):
        """Test that DB cache lookup errors are handled gracefully."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()
        mock_db.cache.fetchone.side_effect = Exception("DB error")

        service = ExchangeRateService(db_manager=mock_db)

        result = await service._get_from_db_cache("USD", "EUR")

        assert result is None


class TestExchangeRateServiceTTL:
    """Test TTL configuration."""

    def test_default_ttl(self):
        """Test that default TTL is applied."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db)

        assert service._ttl_seconds == EXCHANGE_RATE_TTL_SECONDS

    def test_custom_ttl(self):
        """Test that custom TTL is applied."""
        mock_db = MagicMock()
        service = ExchangeRateService(db_manager=mock_db, ttl_seconds=120)

        assert service._ttl_seconds == 120

    @pytest.mark.asyncio
    async def test_ttl_affects_cache_expiry(self):
        """Test that TTL affects cache expiry time."""
        mock_db = MagicMock()
        mock_db.cache = AsyncMock()

        # Short TTL
        service = ExchangeRateService(db_manager=mock_db, ttl_seconds=1)

        # Pre-populate cache with recent entry
        service._memory_cache["USD_EUR"] = (1.05, datetime.now())

        rate = await service.get_rate("USD", "EUR")
        assert rate == 1.05  # Should use cache

        # Wait for TTL to expire
        import asyncio

        await asyncio.sleep(1.1)

        # Now cache should be expired
        with patch.object(
            service, "_fetch_rate_from_api", return_value=1.08
        ) as mock_fetch:
            mock_db.cache.fetchone.return_value = None
            rate = await service.get_rate("USD", "EUR")

            # Should have fetched fresh rate
            mock_fetch.assert_called_once()
