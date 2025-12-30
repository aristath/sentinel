"""Tests for currency exchange service.

These tests validate the currency exchange service logic including
rate lookups, conversion paths, and exchange operations.
"""

from unittest.mock import MagicMock

import pytest


class TestFindRateSymbol:
    """Test finding exchange rate symbols."""

    def test_finds_direct_symbol(self):
        """Test finding a direct rate symbol."""
        from app.application.services.currency_exchange_service import _find_rate_symbol

        mock_service = MagicMock()
        mock_service.RATE_SYMBOLS = {
            ("EUR", "USD"): "EURUSD_T0.ITS",
        }

        symbol, is_inverse = _find_rate_symbol("EUR", "USD", mock_service)

        assert symbol == "EURUSD_T0.ITS"
        assert is_inverse is False

    def test_finds_inverse_symbol(self):
        """Test finding an inverse rate symbol."""
        from app.application.services.currency_exchange_service import _find_rate_symbol

        mock_service = MagicMock()
        mock_service.RATE_SYMBOLS = {
            ("EUR", "USD"): "EURUSD_T0.ITS",
        }

        symbol, is_inverse = _find_rate_symbol("USD", "EUR", mock_service)

        assert symbol == "EURUSD_T0.ITS"
        assert is_inverse is True

    def test_returns_none_for_unknown_pair(self):
        """Test returns None for unknown currency pair."""
        from app.application.services.currency_exchange_service import _find_rate_symbol

        mock_service = MagicMock()
        mock_service.RATE_SYMBOLS = {}

        symbol, is_inverse = _find_rate_symbol("EUR", "JPY", mock_service)

        assert symbol is None
        assert is_inverse is False


class TestGetRateViaPath:
    """Test getting exchange rates via conversion path."""

    def test_single_step_path(self):
        """Test getting rate with a single step path."""
        from app.application.services.currency_exchange_service import (
            ConversionStep,
            _get_rate_via_path,
        )

        mock_service = MagicMock()
        mock_step = ConversionStep(
            from_currency="EUR",
            to_currency="USD",
            symbol="EURUSD_T0.ITS",
            action="BUY",
        )
        mock_service.get_conversion_path.return_value = [mock_step]

        mock_quote = MagicMock()
        mock_quote.price = 1.08
        mock_service.client.get_quote.return_value = mock_quote

        rate = _get_rate_via_path("EUR", "USD", mock_service)

        assert rate == 1.08

    def test_single_step_path_zero_price(self):
        """Test returns None when quote price is zero."""
        from app.application.services.currency_exchange_service import (
            ConversionStep,
            _get_rate_via_path,
        )

        mock_service = MagicMock()
        mock_step = ConversionStep(
            from_currency="EUR",
            to_currency="USD",
            symbol="EURUSD_T0.ITS",
            action="BUY",
        )
        mock_service.get_conversion_path.return_value = [mock_step]

        mock_quote = MagicMock()
        mock_quote.price = 0
        mock_service.client.get_quote.return_value = mock_quote

        rate = _get_rate_via_path("EUR", "USD", mock_service)

        assert rate is None

    def test_two_step_path(self):
        """Test getting rate with a two step path."""
        from app.application.services.currency_exchange_service import (
            ConversionStep,
            _get_rate_via_path,
        )

        mock_service = MagicMock()
        mock_step1 = ConversionStep(
            from_currency="GBP",
            to_currency="EUR",
            symbol="EURGBP_T0.ITS",
            action="SELL",
        )
        mock_step2 = ConversionStep(
            from_currency="EUR",
            to_currency="HKD",
            symbol="HKD/EUR",
            action="BUY",
        )
        mock_service.get_conversion_path.return_value = [mock_step1, mock_step2]

        # Mock get_rate for each step
        mock_service.get_rate.side_effect = [0.85, 9.0]

        rate = _get_rate_via_path("GBP", "HKD", mock_service)

        assert rate == pytest.approx(0.85 * 9.0, rel=0.01)

    def test_returns_none_for_empty_path(self):
        """Test returns None for empty conversion path."""
        from app.application.services.currency_exchange_service import (
            _get_rate_via_path,
        )

        mock_service = MagicMock()
        mock_service.get_conversion_path.return_value = []

        rate = _get_rate_via_path("EUR", "USD", mock_service)

        assert rate is None


class TestCurrencyExchangeService:
    """Test the CurrencyExchangeService class."""

    def test_init_sets_client(self):
        """Test that client is set on init."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()

        service = CurrencyExchangeService(mock_client)

        assert service.client == mock_client

    def test_get_conversion_path_direct(self):
        """Test getting a direct conversion path."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()
        service = CurrencyExchangeService(mock_client)

        path = service.get_conversion_path("EUR", "USD")

        assert len(path) == 1
        assert path[0].from_currency == "EUR"
        assert path[0].to_currency == "USD"
        assert path[0].symbol == "EURUSD_T0.ITS"
        assert path[0].action == "SELL"

    def test_get_conversion_path_same_currency(self):
        """Test getting path for same currency returns empty."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()
        service = CurrencyExchangeService(mock_client)

        path = service.get_conversion_path("EUR", "EUR")

        assert len(path) == 0

    def test_get_conversion_path_via_eur(self):
        """Test getting a two-step conversion path via EUR."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()
        service = CurrencyExchangeService(mock_client)

        # GBP to HKD requires going via EUR
        path = service.get_conversion_path("GBP", "HKD")

        assert len(path) == 2
        assert path[0].from_currency == "GBP"
        assert path[0].to_currency == "EUR"
        assert path[1].from_currency == "EUR"
        assert path[1].to_currency == "HKD"

    def test_get_rate_direct_pair(self):
        """Test getting rate for a direct pair."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()
        mock_quote = MagicMock()
        mock_quote.price = 1.085
        mock_client.get_quote.return_value = mock_quote

        service = CurrencyExchangeService(mock_client)
        rate = service.get_rate("EUR", "USD")

        assert rate == 1.085

    def test_get_rate_inverse_pair(self):
        """Test getting rate for an inverse pair."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()
        mock_quote = MagicMock()
        mock_quote.price = 1.085  # EUR/USD rate
        mock_client.get_quote.return_value = mock_quote

        service = CurrencyExchangeService(mock_client)
        rate = service.get_rate("USD", "EUR")

        # Inverse of 1.085
        assert rate == pytest.approx(1 / 1.085, rel=0.001)

    def test_get_rate_same_currency(self):
        """Test getting rate for same currency returns 1.0."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()
        service = CurrencyExchangeService(mock_client)

        rate = service.get_rate("EUR", "EUR")

        assert rate == 1.0

    def test_get_available_currencies(self):
        """Test getting list of available currencies."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()
        service = CurrencyExchangeService(mock_client)

        currencies = service.get_available_currencies()

        assert "EUR" in currencies
        assert "USD" in currencies
        assert "GBP" in currencies
        assert "HKD" in currencies


class TestExchangeDataClasses:
    """Test the data classes used by the service."""

    def test_exchange_rate_dataclass(self):
        """Test ExchangeRate dataclass."""
        from app.application.services.currency_exchange_service import ExchangeRate

        rate = ExchangeRate(
            from_currency="EUR",
            to_currency="USD",
            rate=1.085,
            bid=1.084,
            ask=1.086,
            symbol="EURUSD_T0.ITS",
        )

        assert rate.from_currency == "EUR"
        assert rate.to_currency == "USD"
        assert rate.rate == 1.085
        assert rate.bid == 1.084
        assert rate.ask == 1.086

    def test_conversion_step_dataclass(self):
        """Test ConversionStep dataclass."""
        from app.application.services.currency_exchange_service import ConversionStep

        step = ConversionStep(
            from_currency="EUR",
            to_currency="USD",
            symbol="EURUSD_T0.ITS",
            action="BUY",
        )

        assert step.from_currency == "EUR"
        assert step.to_currency == "USD"
        assert step.symbol == "EURUSD_T0.ITS"
        assert step.action == "BUY"


class TestValidateExchangeRequest:
    """Test exchange request validation.

    Note: _validate_exchange_request returns bool rather than raising exceptions.
    """

    def test_returns_false_for_same_currency(self):
        """Test that same currency returns False."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()
        service = CurrencyExchangeService(mock_client)

        result = service._validate_exchange_request("EUR", "EUR", 100.0)

        assert result is False

    def test_returns_false_for_negative_amount(self):
        """Test that negative amount returns False."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()
        service = CurrencyExchangeService(mock_client)

        result = service._validate_exchange_request("EUR", "USD", -100.0)

        assert result is False

    def test_returns_false_for_zero_amount(self):
        """Test that zero amount returns False."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()
        service = CurrencyExchangeService(mock_client)

        result = service._validate_exchange_request("EUR", "USD", 0.0)

        assert result is False

    def test_returns_false_when_disconnected(self):
        """Test that returns False when client is disconnected and can't reconnect."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()
        mock_client.is_connected = False
        mock_client.connect.return_value = False  # Can't reconnect

        service = CurrencyExchangeService(mock_client)

        result = service._validate_exchange_request("EUR", "USD", 100.0)

        assert result is False

    def test_returns_true_for_valid_request(self):
        """Test that valid request returns True."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()
        mock_client.is_connected = True

        service = CurrencyExchangeService(mock_client)

        result = service._validate_exchange_request("EUR", "USD", 100.0)

        assert result is True


class TestEnsureBalance:
    """Test ensure_balance functionality."""

    def test_returns_true_when_balance_sufficient(self):
        """Test returns True when target balance already met."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()

        # Mock balances: EUR has 1000, USD has 500
        mock_balance_eur = MagicMock()
        mock_balance_eur.currency = "EUR"
        mock_balance_eur.amount = 1000.0

        mock_balance_usd = MagicMock()
        mock_balance_usd.currency = "USD"
        mock_balance_usd.amount = 500.0

        mock_client.get_cash_balances.return_value = [
            mock_balance_eur,
            mock_balance_usd,
        ]

        service = CurrencyExchangeService(mock_client)

        # Need 300 USD, have 500 - should return True without conversion
        result = service.ensure_balance("USD", 300.0)

        assert result is True
        # Should not have called exchange (no conversion needed)
        mock_client.place_order.assert_not_called()

    def test_returns_false_when_insufficient_source(self):
        """Test returns False when source currency balance insufficient."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        mock_client = MagicMock()

        # Mock balances: EUR has 50, USD has 0
        mock_balance_eur = MagicMock()
        mock_balance_eur.currency = "EUR"
        mock_balance_eur.amount = 50.0

        mock_balance_usd = MagicMock()
        mock_balance_usd.currency = "USD"
        mock_balance_usd.amount = 0.0

        mock_client.get_cash_balances.return_value = [
            mock_balance_eur,
            mock_balance_usd,
        ]

        # Mock rate
        mock_quote = MagicMock()
        mock_quote.price = 1.08
        mock_client.get_quote.return_value = mock_quote

        service = CurrencyExchangeService(mock_client)

        # Need 500 USD, would need ~463 EUR, but only have 50 EUR
        result = service.ensure_balance("USD", 500.0, source_currency="EUR")

        assert result is False


class TestDirectPairs:
    """Test the DIRECT_PAIRS configuration."""

    def test_eur_usd_pair(self):
        """Test EUR/USD pair configuration."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        assert ("EUR", "USD") in CurrencyExchangeService.DIRECT_PAIRS
        assert ("USD", "EUR") in CurrencyExchangeService.DIRECT_PAIRS

        symbol, action = CurrencyExchangeService.DIRECT_PAIRS[("EUR", "USD")]
        assert symbol == "EURUSD_T0.ITS"
        assert action == "SELL"

    def test_eur_gbp_pair(self):
        """Test EUR/GBP pair configuration."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        assert ("EUR", "GBP") in CurrencyExchangeService.DIRECT_PAIRS
        assert ("GBP", "EUR") in CurrencyExchangeService.DIRECT_PAIRS

    def test_hkd_pairs(self):
        """Test HKD pair configurations."""
        from app.application.services.currency_exchange_service import (
            CurrencyExchangeService,
        )

        assert ("EUR", "HKD") in CurrencyExchangeService.DIRECT_PAIRS
        assert ("HKD", "EUR") in CurrencyExchangeService.DIRECT_PAIRS
        assert ("USD", "HKD") in CurrencyExchangeService.DIRECT_PAIRS
        assert ("HKD", "USD") in CurrencyExchangeService.DIRECT_PAIRS
