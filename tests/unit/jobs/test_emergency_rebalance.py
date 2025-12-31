"""Tests for emergency rebalance job.

These tests validate immediate rebalancing when negative balances
or currencies below minimum are detected.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.shared.domain.value_objects.currency import Currency


@pytest.fixture
def mock_tradernet_client():
    """Mock Tradernet client."""
    client = MagicMock()
    client.is_connected = True
    client.connect = MagicMock(return_value=True)
    mock_balance = MagicMock()
    mock_balance.currency = "EUR"
    mock_balance.amount = 1000.0
    client.get_cash_balances.return_value = [mock_balance]
    client.get_pending_orders.return_value = []
    return client


@pytest.fixture
def mock_stock_repo():
    """Mock stock repository."""
    repo = AsyncMock()
    from app.domain.models import Security

    mock_stock = Security(
        symbol="AAPL",
        name="Apple Inc.",
        country="United States",
        currency=Currency.USD,
    )
    repo.get_all_active.return_value = [mock_stock]
    return repo


class TestCheckAndRebalanceImmediately:
    """Test check_and_rebalance_immediately function."""

    @pytest.mark.asyncio
    async def test_returns_false_when_no_negative_balances(self, mock_tradernet_client):
        """Test that function returns False when no negative balances exist."""
        from app.jobs.emergency_rebalance import check_and_rebalance_immediately

        # Setup balances above minimum (EUR: 1000, USD: 100 from trading currencies)
        mock_balance_eur = MagicMock()
        mock_balance_eur.currency = "EUR"
        mock_balance_eur.amount = 1000.0
        mock_balance_usd = MagicMock()
        mock_balance_usd.currency = "USD"
        mock_balance_usd.amount = 100.0  # Above minimum of 5.0
        mock_tradernet_client.get_cash_balances.return_value = [
            mock_balance_eur,
            mock_balance_usd,
        ]

        with patch("app.jobs.emergency_rebalance.file_lock") as mock_lock:
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.jobs.emergency_rebalance.get_tradernet_client",
                return_value=mock_tradernet_client,
            ):
                with patch(
                    "app.jobs.emergency_rebalance.SecurityRepository"
                ) as mock_stock_repo_class:
                    mock_stock_repo = AsyncMock()
                    from app.domain.models import Security

                    mock_stock = Security(
                        symbol="AAPL",
                        name="Apple Inc.",
                        country="United States",
                        currency=Currency.USD,
                    )
                    mock_stock_repo.get_all_active.return_value = [mock_stock]
                    mock_stock_repo_class.return_value = mock_stock_repo

                    with patch(
                        "app.jobs.emergency_rebalance.RecommendationRepository"
                    ) as mock_rec_repo_class:
                        mock_rec_repo = AsyncMock()
                        mock_rec_repo.dismiss_all_by_portfolio_hash = AsyncMock(
                            return_value=0
                        )
                        mock_rec_repo_class.return_value = mock_rec_repo

                        result = await check_and_rebalance_immediately()

                        assert result is False

    @pytest.mark.asyncio
    async def test_triggers_rebalancing_with_negative_balance(
        self, mock_tradernet_client
    ):
        """Test that rebalancing is triggered when negative balance is detected."""
        from app.jobs.emergency_rebalance import check_and_rebalance_immediately

        # Setup negative balance
        mock_balance = MagicMock()
        mock_balance.currency = "EUR"
        mock_balance.amount = -100.0  # Negative!
        mock_tradernet_client.get_cash_balances.return_value = [mock_balance]

        with patch("app.jobs.emergency_rebalance.file_lock") as mock_lock:
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.jobs.emergency_rebalance.get_tradernet_client",
                return_value=mock_tradernet_client,
            ):
                with patch(
                    "app.jobs.emergency_rebalance.NegativeBalanceRebalancer"
                ) as mock_rebalancer_class:
                    mock_rebalancer = AsyncMock()
                    mock_rebalancer.rebalance_negative_balances = AsyncMock(
                        return_value=True
                    )
                    mock_rebalancer_class.return_value = mock_rebalancer

                    with patch("app.jobs.emergency_rebalance.get_db_manager"):
                        with patch(
                            "app.jobs.emergency_rebalance.get_exchange_rate_service"
                        ):
                            with patch(
                                "app.jobs.emergency_rebalance.get_currency_exchange_service_dep"
                            ):
                                with patch(
                                    "app.jobs.emergency_rebalance.PositionRepository"
                                ):
                                    with patch(
                                        "app.jobs.emergency_rebalance.SecurityRepository"
                                    ):
                                        with patch(
                                            "app.jobs.emergency_rebalance.TradeRepository"
                                        ):
                                            with patch(
                                                "app.jobs.emergency_rebalance.RecommendationRepository"
                                            ):
                                                with patch(
                                                    "app.jobs.emergency_rebalance.TradeExecutionService"
                                                ):
                                                    result = (
                                                        await check_and_rebalance_immediately()
                                                    )

                                                    assert result is True
                                                    mock_rebalancer.rebalance_negative_balances.assert_called_once()

    @pytest.mark.asyncio
    async def test_triggers_rebalancing_with_currency_below_minimum(
        self, mock_tradernet_client
    ):
        """Test that rebalancing is triggered when currency is below minimum."""
        from app.jobs.emergency_rebalance import check_and_rebalance_immediately

        # Setup currency below minimum (USD: 2.0 < 5.0 minimum)
        mock_balance_eur = MagicMock()
        mock_balance_eur.currency = "EUR"
        mock_balance_eur.amount = 1000.0
        mock_balance_usd = MagicMock()
        mock_balance_usd.currency = "USD"
        mock_balance_usd.amount = 2.0  # Below minimum of 5.0
        mock_tradernet_client.get_cash_balances.return_value = [
            mock_balance_eur,
            mock_balance_usd,
        ]

        with patch("app.jobs.emergency_rebalance.file_lock") as mock_lock:
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.jobs.emergency_rebalance.get_tradernet_client",
                return_value=mock_tradernet_client,
            ):
                with patch(
                    "app.jobs.emergency_rebalance.NegativeBalanceRebalancer"
                ) as mock_rebalancer_class:
                    mock_rebalancer = AsyncMock()
                    mock_rebalancer.rebalance_negative_balances = AsyncMock(
                        return_value=True
                    )
                    mock_rebalancer_class.return_value = mock_rebalancer

                    with patch("app.jobs.emergency_rebalance.get_db_manager"):
                        with patch(
                            "app.jobs.emergency_rebalance.get_exchange_rate_service"
                        ):
                            with patch(
                                "app.jobs.emergency_rebalance.get_currency_exchange_service_dep"
                            ):
                                with patch(
                                    "app.jobs.emergency_rebalance.PositionRepository"
                                ):
                                    with patch(
                                        "app.jobs.emergency_rebalance.SecurityRepository"
                                    ) as mock_stock_repo_class:
                                        mock_stock_repo = AsyncMock()
                                        from app.domain.models import Security

                                        mock_stock = Security(
                                            symbol="AAPL",
                                            name="Apple Inc.",
                                            country="United States",
                                            currency=Currency.USD,
                                        )
                                        mock_stock_repo.get_all_active.return_value = [
                                            mock_stock
                                        ]
                                        mock_stock_repo_class.return_value = (
                                            mock_stock_repo
                                        )

                                        with patch(
                                            "app.jobs.emergency_rebalance.TradeRepository"
                                        ):
                                            with patch(
                                                "app.jobs.emergency_rebalance.RecommendationRepository"
                                            ):
                                                with patch(
                                                    "app.jobs.emergency_rebalance.TradeExecutionService"
                                                ):
                                                    result = (
                                                        await check_and_rebalance_immediately()
                                                    )

                                                    assert result is True

    @pytest.mark.asyncio
    async def test_dismisses_stale_emergency_recommendations(
        self, mock_tradernet_client
    ):
        """Test that stale emergency recommendations are dismissed when no rebalancing needed."""
        from app.jobs.emergency_rebalance import check_and_rebalance_immediately

        # Setup balances above minimum
        mock_balance_eur = MagicMock()
        mock_balance_eur.currency = "EUR"
        mock_balance_eur.amount = 1000.0
        mock_balance_usd = MagicMock()
        mock_balance_usd.currency = "USD"
        mock_balance_usd.amount = 100.0
        mock_tradernet_client.get_cash_balances.return_value = [
            mock_balance_eur,
            mock_balance_usd,
        ]

        with patch("app.jobs.emergency_rebalance.file_lock") as mock_lock:
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.jobs.emergency_rebalance.get_tradernet_client",
                return_value=mock_tradernet_client,
            ):
                with patch(
                    "app.jobs.emergency_rebalance.SecurityRepository"
                ) as mock_stock_repo_class:
                    mock_stock_repo = AsyncMock()
                    from app.domain.models import Security

                    mock_stock = Security(
                        symbol="AAPL",
                        name="Apple Inc.",
                        country="United States",
                        currency=Currency.USD,
                    )
                    mock_stock_repo.get_all_active.return_value = [mock_stock]
                    mock_stock_repo_class.return_value = mock_stock_repo

                    with patch(
                        "app.jobs.emergency_rebalance.RecommendationRepository"
                    ) as mock_rec_repo_class:
                        mock_rec_repo = AsyncMock()
                        mock_rec_repo.dismiss_all_by_portfolio_hash = AsyncMock(
                            return_value=3  # 3 stale recommendations dismissed
                        )
                        mock_rec_repo_class.return_value = mock_rec_repo

                        result = await check_and_rebalance_immediately()

                        assert result is False
                        mock_rec_repo.dismiss_all_by_portfolio_hash.assert_called_once_with(
                            "EMERGENCY:negative_balance_rebalancing"
                        )

    @pytest.mark.asyncio
    async def test_handles_tradernet_not_connected(self):
        """Test handling when Tradernet is not connected."""
        from app.jobs.emergency_rebalance import check_and_rebalance_immediately

        disconnected_client = MagicMock()
        disconnected_client.is_connected = False
        disconnected_client.connect = MagicMock(return_value=False)

        with patch("app.jobs.emergency_rebalance.file_lock") as mock_lock:
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.jobs.emergency_rebalance.get_tradernet_client",
                return_value=disconnected_client,
            ):
                result = await check_and_rebalance_immediately()

                assert result is False

    @pytest.mark.asyncio
    async def test_handles_tradernet_connection_failure(self):
        """Test handling when Tradernet connection fails."""
        from app.jobs.emergency_rebalance import check_and_rebalance_immediately

        client = MagicMock()
        client.is_connected = False
        client.connect = MagicMock(return_value=False)

        with patch("app.jobs.emergency_rebalance.file_lock") as mock_lock:
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.jobs.emergency_rebalance.get_tradernet_client", return_value=client
            ):
                result = await check_and_rebalance_immediately()

                assert result is False

    @pytest.mark.asyncio
    async def test_handles_errors_gracefully(self, mock_tradernet_client):
        """Test that errors are caught and function returns False."""
        from app.jobs.emergency_rebalance import check_and_rebalance_immediately

        mock_tradernet_client.get_cash_balances.side_effect = Exception("API Error")

        with patch("app.jobs.emergency_rebalance.file_lock") as mock_lock:
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.jobs.emergency_rebalance.get_tradernet_client",
                return_value=mock_tradernet_client,
            ):
                result = await check_and_rebalance_immediately()

                # Should return False on error, not raise
                assert result is False

    @pytest.mark.asyncio
    async def test_uses_file_lock_to_prevent_concurrent_execution(
        self, mock_tradernet_client
    ):
        """Test that file_lock is used to prevent concurrent execution."""
        from app.jobs.emergency_rebalance import check_and_rebalance_immediately

        mock_balance = MagicMock()
        mock_balance.currency = "EUR"
        mock_balance.amount = 1000.0
        mock_tradernet_client.get_cash_balances.return_value = [mock_balance]

        with patch("app.jobs.emergency_rebalance.file_lock") as mock_lock:
            mock_lock_context = AsyncMock()
            mock_lock_context.__aenter__ = AsyncMock()
            mock_lock_context.__aexit__ = AsyncMock(return_value=None)
            mock_lock.return_value = mock_lock_context

            with patch(
                "app.jobs.emergency_rebalance.get_tradernet_client",
                return_value=mock_tradernet_client,
            ):
                with patch("app.jobs.emergency_rebalance.SecurityRepository"):
                    with patch("app.jobs.emergency_rebalance.RecommendationRepository"):
                        await check_and_rebalance_immediately()

                        # Verify file_lock was called with correct parameters
                        mock_lock.assert_called_once_with(
                            "emergency_rebalance", timeout=60.0
                        )

    @pytest.mark.asyncio
    async def test_handles_no_trading_currencies(self, mock_tradernet_client):
        """Test handling when there are no trading currencies."""
        from app.jobs.emergency_rebalance import check_and_rebalance_immediately

        # Setup balances above minimum
        mock_balance = MagicMock()
        mock_balance.currency = "EUR"
        mock_balance.amount = 1000.0
        mock_tradernet_client.get_cash_balances.return_value = [mock_balance]

        with patch("app.jobs.emergency_rebalance.file_lock") as mock_lock:
            mock_lock.return_value.__aenter__ = AsyncMock()
            mock_lock.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "app.jobs.emergency_rebalance.get_tradernet_client",
                return_value=mock_tradernet_client,
            ):
                with patch(
                    "app.jobs.emergency_rebalance.SecurityRepository"
                ) as mock_stock_repo_class:
                    mock_stock_repo = AsyncMock()
                    mock_stock_repo.get_all_active.return_value = []  # No stocks
                    mock_stock_repo_class.return_value = mock_stock_repo

                    with patch(
                        "app.jobs.emergency_rebalance.RecommendationRepository"
                    ) as mock_rec_repo_class:
                        mock_rec_repo = AsyncMock()
                        mock_rec_repo.dismiss_all_by_portfolio_hash = AsyncMock(
                            return_value=0
                        )
                        mock_rec_repo_class.return_value = mock_rec_repo

                        result = await check_and_rebalance_immediately()

                        # Should return False when no trading currencies
                        assert result is False
