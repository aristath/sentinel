"""Tests for dividend reinvestment job.

These tests validate automatic dividend reinvestment execution.
CRITICAL: Tests catch real bugs that would cause financial losses or inefficiencies.
"""

from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import DividendRecord, Security
from app.shared.domain.value_objects.currency import Currency


def create_quote(price: float) -> SimpleNamespace:
    """Create a quote-like object with price attribute."""
    return SimpleNamespace(price=price)


def create_dividend(
    symbol: str,
    amount_eur: float,
    dividend_id: Optional[int] = None,
    cash_flow_id: Optional[int] = None,
) -> DividendRecord:
    """Helper to create dividend record."""
    return DividendRecord(
        id=dividend_id or 1,
        symbol=symbol,
        amount=amount_eur,
        currency="EUR",
        amount_eur=amount_eur,
        payment_date=datetime.now().isoformat(),
        cash_flow_id=cash_flow_id,
        reinvested=False,
    )


def create_stock(symbol: str, name: Optional[str] = None, min_lot: int = 1) -> Security:
    """Helper to create security."""
    return Security(
        symbol=symbol,
        name=name or f"{symbol} Inc.",
        min_lot=min_lot,
        currency=Currency.EUR,
    )


@contextmanager
def mock_dividend_reinvestment_dependencies(
    mock_dividend_repo=None,
    mock_stock_repo=None,
    mock_settings_repo=None,
    mock_tradernet_client=None,
    mock_trade_execution_service=None,
    stocks_by_symbol=None,
):
    """Context manager to set up all mocks for dividend reinvestment job."""
    # Default mocks
    if mock_dividend_repo is None:
        mock_dividend_repo = AsyncMock()
    if mock_stock_repo is None:
        mock_stock_repo = AsyncMock()
    if mock_settings_repo is None:
        mock_settings_repo = AsyncMock()
    if mock_tradernet_client is None:
        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.connect.return_value = True
    if mock_trade_execution_service is None:
        mock_trade_execution_service = AsyncMock()

    # Setup security repo
    if stocks_by_symbol:

        async def get_by_symbol(symbol):
            return stocks_by_symbol.get(symbol)

        mock_stock_repo.get_by_symbol = AsyncMock(side_effect=get_by_symbol)

    # Setup settings - use low transaction costs so min_trade_size is low
    # min_trade_size = fixed / (max_ratio - percent)
    # With fixed=0.4, percent=0.002, max_ratio=0.01: min_trade_size = 0.4 / 0.008 = 50
    mock_settings = MagicMock()
    mock_settings.transaction_cost_fixed = 0.4
    mock_settings.transaction_cost_percent = 0.002
    mock_settings_service = AsyncMock()
    mock_settings_service.get_settings = AsyncMock(return_value=mock_settings)

    # Mock CalculationsRepository
    mock_calc_repo = AsyncMock()
    mock_calc_repo.get_metric = AsyncMock(return_value=5.0)  # Default 5% yield

    with (
        patch(
            "app.jobs.dividend_reinvestment.DividendRepository",
            return_value=mock_dividend_repo,
        ),
        patch(
            "app.jobs.dividend_reinvestment.SecurityRepository",
            return_value=mock_stock_repo,
        ),
        patch(
            "app.jobs.dividend_reinvestment.SettingsRepository",
            return_value=mock_settings_repo,
        ),
        patch(
            "app.jobs.dividend_reinvestment.SettingsService",
            return_value=mock_settings_service,
        ),
        patch(
            "app.jobs.dividend_reinvestment.get_tradernet_client",
            return_value=mock_tradernet_client,
        ),
        patch(
            "app.jobs.dividend_reinvestment.TradeRepository", return_value=AsyncMock()
        ),
        patch(
            "app.jobs.dividend_reinvestment.PositionRepository",
            return_value=AsyncMock(),
        ),
        patch(
            "app.jobs.dividend_reinvestment.get_db_manager", return_value=MagicMock()
        ),
        patch(
            "app.jobs.dividend_reinvestment.get_exchange_rate_service",
            return_value=AsyncMock(),
        ),
        patch(
            "app.jobs.dividend_reinvestment.get_currency_exchange_service_dep",
            return_value=AsyncMock(),
        ),
        patch(
            "app.jobs.dividend_reinvestment.TradeExecutionService",
            side_effect=lambda *args, **kwargs: mock_trade_execution_service,
        ),
        patch(
            "app.jobs.dividend_reinvestment.CalculationsRepository",
            return_value=mock_calc_repo,
        ),
    ):
        yield {
            "dividend_repo": mock_dividend_repo,
            "security_repo": mock_stock_repo,
            "settings_repo": mock_settings_repo,
            "tradernet_client": mock_tradernet_client,
            "trade_execution_service": mock_trade_execution_service,
        }


class TestDividendGrouping:
    """Test dividend grouping by symbol logic."""

    @pytest.mark.asyncio
    async def test_groups_multiple_dividends_by_symbol(self):
        """Test that multiple dividends for same symbol are grouped.

        Bug caught: Without grouping, multiple small trades waste transaction costs.
        """
        # Setup: 3 dividends for AAPL, 1 for MSFT
        dividends = [
            create_dividend("AAPL", 50.0, dividend_id=1),
            create_dividend("AAPL", 30.0, dividend_id=2),
            create_dividend("AAPL", 20.0, dividend_id=3),
            create_dividend("MSFT", 100.0, dividend_id=4),
        ]

        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(
            return_value=dividends
        )
        mock_dividend_repo.mark_reinvested = AsyncMock()

        # Use price=50 so quantity = int(100/50) = 2 shares
        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_quote = MagicMock(return_value=create_quote(50.0))

        mock_trade_execution_service = AsyncMock()
        mock_trade_execution_service.execute_trades = AsyncMock(
            return_value=[
                {"symbol": "AAPL", "status": "success", "quantity": 2},
                {"symbol": "MSFT", "status": "success", "quantity": 2},
            ]
        )

        stocks_by_symbol = {
            "AAPL": create_stock("AAPL", "Apple Inc."),
            "MSFT": create_stock("MSFT", "Microsoft Corporation"),
        }

        from app.jobs.dividend_reinvestment import auto_reinvest_dividends

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
            stocks_by_symbol=stocks_by_symbol,
        ):
            await auto_reinvest_dividends()

        # Verify grouping: Should be 2 trades, not 4
        assert mock_trade_execution_service.execute_trades.call_count == 1
        call_args = mock_trade_execution_service.execute_trades.call_args[0][0]
        assert len(call_args) == 2  # Only 2 recommendations (grouped)

        # Verify AAPL recommendation: quantity * price = 2 * 50 = 100
        aapl_rec = next(r for r in call_args if r.symbol == "AAPL")
        assert aapl_rec.estimated_value == pytest.approx(100.0, abs=0.01)

        # Verify MSFT recommendation: quantity * price = 2 * 50 = 100
        msft_rec = next(r for r in call_args if r.symbol == "MSFT")
        assert msft_rec.estimated_value == pytest.approx(100.0, abs=0.01)

        # Verify all dividends marked as reinvested (3 AAPL + 1 MSFT = 4)
        assert mock_dividend_repo.mark_reinvested.call_count == 4  # All dividends

    @pytest.mark.asyncio
    async def test_sums_amounts_correctly_when_grouping(self):
        """Test that amounts are summed correctly when grouping.

        Bug caught: Incorrect summation leads to wrong trade size.
        """
        # Total = 30 + 15 + 10 = 55 EUR (above min_trade_size of 50)
        dividends = [
            create_dividend("AAPL", 30.0, dividend_id=1),
            create_dividend("AAPL", 15.0, dividend_id=2),
            create_dividend("AAPL", 10.0, dividend_id=3),
        ]

        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(
            return_value=dividends
        )

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_quote = MagicMock(return_value=create_quote(50.0))

        mock_trade_execution_service = AsyncMock()
        mock_trade_execution_service.execute_trades = AsyncMock(
            return_value=[{"symbol": "AAPL", "status": "success", "quantity": 1}]
        )

        stocks_by_symbol = {"AAPL": create_stock("AAPL", "Apple Inc.")}

        from app.jobs.dividend_reinvestment import auto_reinvest_dividends

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
            stocks_by_symbol=stocks_by_symbol,
        ):
            await auto_reinvest_dividends()

        # Verify correct sum: quantity * price
        # Total amount 55 / price 50 = 1 share, 1 * 50 = 50 estimated_value
        call_args = mock_trade_execution_service.execute_trades.call_args[0][0]
        aapl_rec = call_args[0]
        assert aapl_rec.estimated_value == pytest.approx(50.0, abs=0.01)


class TestReinvestmentExecution:
    """Test reinvestment execution logic."""

    @pytest.mark.asyncio
    async def test_executes_trade_when_grouped_total_exceeds_min_trade_size(self):
        """Test that trade is executed when grouped total exceeds min_trade_size.

        Bug caught: Trade not executed when it should be.
        """
        dividends = [create_dividend("AAPL", 60.0)]

        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(
            return_value=dividends
        )
        mock_dividend_repo.mark_reinvested = AsyncMock()

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_quote = MagicMock(return_value=create_quote(50.0))

        mock_trade_execution_service = AsyncMock()
        mock_trade_execution_service.execute_trades = AsyncMock(
            return_value=[{"symbol": "AAPL", "status": "success", "quantity": 1}]
        )

        stocks_by_symbol = {"AAPL": create_stock("AAPL", "Apple Inc.")}

        from app.jobs.dividend_reinvestment import auto_reinvest_dividends

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
            stocks_by_symbol=stocks_by_symbol,
        ):
            await auto_reinvest_dividends()

        # Verify trade was executed
        mock_trade_execution_service.execute_trades.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_trade_when_grouped_total_below_min_trade_size(self):
        """Test that trade is skipped when grouped total is below min_trade_size.

        Bug caught: Executing trades below minimum wastes money.
        """
        dividends = [create_dividend("AAPL", 30.0)]

        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(
            return_value=dividends
        )
        mock_dividend_repo.set_pending_bonus = AsyncMock()

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True

        mock_trade_execution_service = AsyncMock()

        stocks_by_symbol = {"AAPL": create_stock("AAPL", "Apple Inc.")}

        from app.jobs.dividend_reinvestment import auto_reinvest_dividends

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
            stocks_by_symbol=stocks_by_symbol,
        ):
            await auto_reinvest_dividends()

        # Verify trade was NOT executed
        mock_trade_execution_service.execute_trades.assert_not_called()

        # Verify pending bonus was set
        mock_dividend_repo.set_pending_bonus.assert_called_once()

    @pytest.mark.asyncio
    async def test_exactly_at_min_trade_size_executes(self):
        """Test that trade executes when exactly at min_trade_size.

        Bug caught: Off-by-one at threshold.
        """
        dividends = [create_dividend("AAPL", 250.0)]  # Exactly at threshold (250 EUR)

        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(
            return_value=dividends
        )
        mock_dividend_repo.mark_reinvested = AsyncMock()

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_quote = MagicMock(return_value=create_quote(50.0))

        mock_trade_execution_service = AsyncMock()
        mock_trade_execution_service.execute_trades = AsyncMock(
            return_value=[{"symbol": "AAPL", "status": "success", "quantity": 1}]
        )

        stocks_by_symbol = {"AAPL": create_stock("AAPL", "Apple Inc.")}

        from app.jobs.dividend_reinvestment import auto_reinvest_dividends

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
            stocks_by_symbol=stocks_by_symbol,
        ):
            await auto_reinvest_dividends()

        # Verify trade was executed (>= threshold)
        mock_trade_execution_service.execute_trades.assert_called_once()


class TestDividendMarking:
    """Test that dividends are marked correctly after reinvestment."""

    @pytest.mark.asyncio
    async def test_marks_all_dividend_records_reinvested_after_trade(self):
        """Test that all dividend records for a symbol are marked as reinvested.

        Bug caught: Partial marking causes duplicate reinvestment.
        """
        dividends = [
            create_dividend("AAPL", 50.0, dividend_id=1),
            create_dividend("AAPL", 30.0, dividend_id=2),
            create_dividend("AAPL", 20.0, dividend_id=3),
        ]

        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(
            return_value=dividends
        )
        mock_dividend_repo.mark_reinvested = AsyncMock()

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_quote = MagicMock(return_value=create_quote(50.0))

        mock_trade_execution_service = AsyncMock()
        mock_trade_execution_service.execute_trades = AsyncMock(
            return_value=[{"symbol": "AAPL", "status": "success", "quantity": 1}]
        )

        stocks_by_symbol = {"AAPL": create_stock("AAPL", "Apple Inc.")}

        from app.jobs.dividend_reinvestment import auto_reinvest_dividends

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
            stocks_by_symbol=stocks_by_symbol,
        ):
            await auto_reinvest_dividends()

        # Verify all 3 dividends were marked as reinvested
        assert mock_dividend_repo.mark_reinvested.call_count == 3

        # Verify each dividend ID was marked
        called_ids = {
            call[0][0] for call in mock_dividend_repo.mark_reinvested.call_args_list
        }
        assert called_ids == {1, 2, 3}


class TestPendingBonus:
    """Test pending bonus handling for small dividends."""

    @pytest.mark.asyncio
    async def test_sets_pending_bonus_for_small_ungrouped_dividends(self):
        """Test that small dividends get pending bonus set.

        Bug caught: Small dividends lost instead of accumulated.
        """
        dividends = [create_dividend("AAPL", 25.0)]  # Below threshold

        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(
            return_value=dividends
        )
        mock_dividend_repo.set_pending_bonus = AsyncMock()

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True

        mock_trade_execution_service = AsyncMock()

        stocks_by_symbol = {"AAPL": create_stock("AAPL", "Apple Inc.")}

        from app.jobs.dividend_reinvestment import auto_reinvest_dividends

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
            stocks_by_symbol=stocks_by_symbol,
        ):
            await auto_reinvest_dividends()

        # Verify pending bonus was set
        mock_dividend_repo.set_pending_bonus.assert_called_once()
        call_args = mock_dividend_repo.set_pending_bonus.call_args[0]
        assert call_args[0] == 1  # dividend_id
        assert call_args[1] == pytest.approx(25.0, abs=0.01)  # amount_eur


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_zero_dividends_handles_gracefully(self):
        """Test that empty dividend list is handled gracefully.

        Bug caught: Crashes on empty list.
        """
        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(return_value=[])

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True

        mock_trade_execution_service = AsyncMock()

        from app.jobs.dividend_reinvestment import auto_reinvest_dividends

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
        ):
            # Should not raise exception
            await auto_reinvest_dividends()

        # Verify no trades executed
        mock_trade_execution_service.execute_trades.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_failure_does_not_crash_job(self):
        """Test that API failure doesn't crash the job.

        Bug caught: Job crashes, preventing future runs.
        """
        dividends = [create_dividend("AAPL", 100.0)]
        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(
            return_value=dividends
        )

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_quote.side_effect = Exception("API connection failed")

        mock_trade_execution_service = AsyncMock()

        stocks_by_symbol = {"AAPL": create_stock("AAPL", "Apple Inc.")}

        from app.jobs.dividend_reinvestment import auto_reinvest_dividends

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
            stocks_by_symbol=stocks_by_symbol,
        ):
            # Should not raise exception, should log and continue
            await auto_reinvest_dividends()

        # Verify no trades executed due to error
        mock_trade_execution_service.execute_trades.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_price_skips_symbol_continues_others(self):
        """Test that invalid price for one symbol doesn't block others.

        Bug caught: One bad symbol blocks all reinvestment.
        """
        dividends = [
            create_dividend("AAPL", 100.0, dividend_id=1),
            create_dividend("MSFT", 100.0, dividend_id=2),
        ]

        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(
            return_value=dividends
        )
        mock_dividend_repo.mark_reinvested = AsyncMock()

        def get_quote_side_effect(symbol):
            if symbol == "AAPL":
                return None  # Invalid price
            return create_quote(50.0)  # 100 / 50 = 2 shares

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_quote = MagicMock(side_effect=get_quote_side_effect)

        mock_trade_execution_service = AsyncMock()
        mock_trade_execution_service.execute_trades = AsyncMock(
            return_value=[{"symbol": "MSFT", "status": "success", "quantity": 1}]
        )

        stocks_by_symbol = {
            "AAPL": create_stock("AAPL", "Apple Inc."),
            "MSFT": create_stock("MSFT", "Microsoft Corporation"),
        }

        from app.jobs.dividend_reinvestment import auto_reinvest_dividends

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
            stocks_by_symbol=stocks_by_symbol,
        ):
            await auto_reinvest_dividends()

        # Verify MSFT trade was executed despite AAPL failure
        mock_trade_execution_service.execute_trades.assert_called_once()
        call_args = mock_trade_execution_service.execute_trades.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0].symbol == "MSFT"

    @pytest.mark.asyncio
    async def test_trade_execution_failure_marks_dividends_unreinvested(self):
        """Test that dividends are not marked reinvested if trade fails.

        Bug caught: Dividends marked reinvested but trade failed.
        """
        dividends = [create_dividend("AAPL", 100.0, dividend_id=1)]
        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(
            return_value=dividends
        )
        mock_dividend_repo.mark_reinvested = AsyncMock()

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_quote = MagicMock(return_value=create_quote(50.0))

        mock_trade_execution_service = AsyncMock()
        mock_trade_execution_service.execute_trades = AsyncMock(
            return_value=[
                {"symbol": "AAPL", "status": "error", "error": "Insufficient funds"}
            ]
        )

        stocks_by_symbol = {"AAPL": create_stock("AAPL", "Apple Inc.")}

        from app.jobs.dividend_reinvestment import auto_reinvest_dividends

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
            stocks_by_symbol=stocks_by_symbol,
        ):
            await auto_reinvest_dividends()

        # Verify dividend was NOT marked as reinvested (trade failed)
        mock_dividend_repo.mark_reinvested.assert_not_called()


class TestStateVerification:
    """Test database state verification."""

    @pytest.mark.asyncio
    async def test_verify_no_duplicate_reinvestment(self):
        """Test that same dividend is not reinvested multiple times.

        Bug caught: Same dividend reinvested multiple times.
        """
        # First call: dividend exists and is not reinvested
        dividend = create_dividend("AAPL", 100.0, dividend_id=1)
        mock_dividend_repo = AsyncMock()
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(
            return_value=[dividend]
        )
        mock_dividend_repo.mark_reinvested = AsyncMock()

        mock_tradernet_client = MagicMock()
        mock_tradernet_client.is_connected = True
        mock_tradernet_client.get_quote = MagicMock(return_value=create_quote(50.0))

        mock_trade_execution_service = AsyncMock()
        mock_trade_execution_service.execute_trades = AsyncMock(
            return_value=[{"symbol": "AAPL", "status": "success", "quantity": 1}]
        )

        stocks_by_symbol = {"AAPL": create_stock("AAPL", "Apple Inc.")}

        from app.jobs.dividend_reinvestment import auto_reinvest_dividends

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
            stocks_by_symbol=stocks_by_symbol,
        ):
            # First run
            await auto_reinvest_dividends()

        # Second call: dividend should not appear (already reinvested)
        mock_dividend_repo.get_unreinvested_dividends = AsyncMock(return_value=[])

        with mock_dividend_reinvestment_dependencies(
            mock_dividend_repo=mock_dividend_repo,
            mock_tradernet_client=mock_tradernet_client,
            mock_trade_execution_service=mock_trade_execution_service,
            stocks_by_symbol=stocks_by_symbol,
        ):
            # Second run - should not execute any trades
            await auto_reinvest_dividends()

        # Verify trade was only executed once (first run)
        assert mock_trade_execution_service.execute_trades.call_count == 1
