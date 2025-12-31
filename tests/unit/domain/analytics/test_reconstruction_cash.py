"""Tests for cash balance reconstruction.

These tests validate the reconstruction of historical cash balance
from cash flows and trades.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.domain.models import CashFlow, Trade
from app.domain.value_objects.trade_side import TradeSide
from app.shared.domain.value_objects.currency import Currency


@pytest.fixture
def mock_cash_flow_repo():
    """Mock CashFlowRepository."""
    repo = AsyncMock()
    repo.get_by_date_range.return_value = []
    return repo


@pytest.fixture
def mock_trade_repo():
    """Mock TradeRepository."""
    repo = AsyncMock()
    repo.get_all_in_range.return_value = []
    return repo


class TestReconstructCashBalance:
    """Test reconstruct_cash_balance function."""

    @pytest.mark.asyncio
    async def test_returns_series_with_initial_cash(
        self, mock_cash_flow_repo, mock_trade_repo
    ):
        """Test that series is returned with initial cash balance."""
        from app.domain.analytics.reconstruction.cash import reconstruct_cash_balance

        with patch(
            "app.domain.analytics.reconstruction.cash.CashFlowRepository",
            return_value=mock_cash_flow_repo,
        ):
            with patch(
                "app.domain.analytics.reconstruction.cash.TradeRepository",
                return_value=mock_trade_repo,
            ):
                result = await reconstruct_cash_balance(
                    start_date="2024-01-01", end_date="2024-01-05", initial_cash=1000.0
                )

                assert isinstance(result, pd.Series)
                assert len(result) == 5  # 5 days
                assert result.iloc[0] == 1000.0  # Initial cash
                assert (result == 1000.0).all()  # No transactions, all same

    @pytest.mark.asyncio
    async def test_handles_deposit_transaction(
        self, mock_cash_flow_repo, mock_trade_repo
    ):
        """Test handling of deposit cash flow."""
        from app.domain.analytics.reconstruction.cash import reconstruct_cash_balance

        cash_flow = CashFlow(
            transaction_id="TX1",
            type_doc_id=1,
            transaction_type="DEPOSIT",
            date="2024-01-03",
            amount=500.0,
            currency=Currency.EUR,
            amount_eur=500.0,
        )
        mock_cash_flow_repo.get_by_date_range.return_value = [cash_flow]

        with patch(
            "app.domain.analytics.reconstruction.cash.CashFlowRepository",
            return_value=mock_cash_flow_repo,
        ):
            with patch(
                "app.domain.analytics.reconstruction.cash.TradeRepository",
                return_value=mock_trade_repo,
            ):
                result = await reconstruct_cash_balance(
                    start_date="2024-01-01", end_date="2024-01-05", initial_cash=1000.0
                )

                # Before deposit: 1000
                assert result.iloc[0] == 1000.0  # 2024-01-01
                assert result.iloc[1] == 1000.0  # 2024-01-02
                # After deposit: 1500
                assert result.iloc[2] == 1500.0  # 2024-01-03 (deposit date)
                assert result.iloc[3] == 1500.0  # 2024-01-04
                assert result.iloc[4] == 1500.0  # 2024-01-05

    @pytest.mark.asyncio
    async def test_handles_withdrawal_transaction(
        self, mock_cash_flow_repo, mock_trade_repo
    ):
        """Test handling of withdrawal cash flow."""
        from app.domain.analytics.reconstruction.cash import reconstruct_cash_balance

        cash_flow = CashFlow(
            transaction_id="TX1",
            type_doc_id=1,
            transaction_type="WITHDRAWAL",
            date="2024-01-03",
            amount=200.0,
            currency=Currency.EUR,
            amount_eur=200.0,
        )
        mock_cash_flow_repo.get_by_date_range.return_value = [cash_flow]

        with patch(
            "app.domain.analytics.reconstruction.cash.CashFlowRepository",
            return_value=mock_cash_flow_repo,
        ):
            with patch(
                "app.domain.analytics.reconstruction.cash.TradeRepository",
                return_value=mock_trade_repo,
            ):
                result = await reconstruct_cash_balance(
                    start_date="2024-01-01", end_date="2024-01-05", initial_cash=1000.0
                )

                # After withdrawal: 1000 - 200 = 800
                assert result.iloc[2] == 800.0  # 2024-01-03 (withdrawal date)

    @pytest.mark.asyncio
    async def test_handles_dividend_transaction(
        self, mock_cash_flow_repo, mock_trade_repo
    ):
        """Test handling of dividend cash flow."""
        from app.domain.analytics.reconstruction.cash import reconstruct_cash_balance

        cash_flow = CashFlow(
            transaction_id="TX1",
            type_doc_id=1,
            transaction_type="DIVIDEND",
            date="2024-01-03",
            amount=50.0,
            currency=Currency.EUR,
            amount_eur=50.0,
        )
        mock_cash_flow_repo.get_by_date_range.return_value = [cash_flow]

        with patch(
            "app.domain.analytics.reconstruction.cash.CashFlowRepository",
            return_value=mock_cash_flow_repo,
        ):
            with patch(
                "app.domain.analytics.reconstruction.cash.TradeRepository",
                return_value=mock_trade_repo,
            ):
                result = await reconstruct_cash_balance(
                    start_date="2024-01-01", end_date="2024-01-05", initial_cash=1000.0
                )

                # After dividend: 1000 + 50 = 1050
                assert result.iloc[2] == 1050.0  # 2024-01-03 (dividend date)

    @pytest.mark.asyncio
    async def test_handles_buy_trade(self, mock_cash_flow_repo, mock_trade_repo):
        """Test handling of buy trade (cash decreases)."""
        from app.domain.analytics.reconstruction.cash import reconstruct_cash_balance

        trade = Trade(
            symbol="AAPL",
            side=TradeSide.BUY,
            quantity=10.0,
            price=100.0,
            executed_at=datetime(2024, 1, 3, 10, 0, 0),
            value_eur=1000.0,
        )
        mock_trade_repo.get_all_in_range.return_value = [trade]

        with patch(
            "app.domain.analytics.reconstruction.cash.CashFlowRepository",
            return_value=mock_cash_flow_repo,
        ):
            with patch(
                "app.domain.analytics.reconstruction.cash.TradeRepository",
                return_value=mock_trade_repo,
            ):
                result = await reconstruct_cash_balance(
                    start_date="2024-01-01", end_date="2024-01-05", initial_cash=2000.0
                )

                # After buy: 2000 - 1000 = 1000
                assert result.iloc[2] == 1000.0  # 2024-01-03 (buy date)

    @pytest.mark.asyncio
    async def test_handles_sell_trade(self, mock_cash_flow_repo, mock_trade_repo):
        """Test handling of sell trade (cash increases)."""
        from app.domain.analytics.reconstruction.cash import reconstruct_cash_balance

        trade = Trade(
            symbol="AAPL",
            side=TradeSide.SELL,
            quantity=10.0,
            price=100.0,
            executed_at=datetime(2024, 1, 3, 10, 0, 0),
            value_eur=1000.0,
        )
        mock_trade_repo.get_all_in_range.return_value = [trade]

        with patch(
            "app.domain.analytics.reconstruction.cash.CashFlowRepository",
            return_value=mock_cash_flow_repo,
        ):
            with patch(
                "app.domain.analytics.reconstruction.cash.TradeRepository",
                return_value=mock_trade_repo,
            ):
                result = await reconstruct_cash_balance(
                    start_date="2024-01-01", end_date="2024-01-05", initial_cash=1000.0
                )

                # After sell: 1000 + 1000 = 2000
                assert result.iloc[2] == 2000.0  # 2024-01-03 (sell date)

    @pytest.mark.asyncio
    async def test_handles_trade_without_value_eur(
        self, mock_cash_flow_repo, mock_trade_repo
    ):
        """Test handling of trade without value_eur (calculated from quantity * price)."""
        from app.domain.analytics.reconstruction.cash import reconstruct_cash_balance

        trade = Trade(
            symbol="AAPL",
            side=TradeSide.BUY,
            quantity=10.0,
            price=100.0,
            executed_at=datetime(2024, 1, 3, 10, 0, 0),
            value_eur=None,  # Not provided
            currency_rate=1.0,
        )
        mock_trade_repo.get_all_in_range.return_value = [trade]

        with patch(
            "app.domain.analytics.reconstruction.cash.CashFlowRepository",
            return_value=mock_cash_flow_repo,
        ):
            with patch(
                "app.domain.analytics.reconstruction.cash.TradeRepository",
                return_value=mock_trade_repo,
            ):
                result = await reconstruct_cash_balance(
                    start_date="2024-01-01", end_date="2024-01-05", initial_cash=2000.0
                )

                # Calculated: 10 * 100 * 1.0 = 1000
                assert result.iloc[2] == 1000.0  # 2000 - 1000

    @pytest.mark.asyncio
    async def test_handles_multiple_transactions_on_same_date(
        self, mock_cash_flow_repo, mock_trade_repo
    ):
        """Test handling of multiple transactions on the same date."""
        from app.domain.analytics.reconstruction.cash import reconstruct_cash_balance

        cash_flow = CashFlow(
            transaction_id="TX1",
            type_doc_id=1,
            transaction_type="DEPOSIT",
            date="2024-01-03",
            amount=500.0,
            currency=Currency.EUR,
            amount_eur=500.0,
        )
        trade = Trade(
            symbol="AAPL",
            side=TradeSide.BUY,
            quantity=10.0,
            price=100.0,
            executed_at=datetime(2024, 1, 3, 10, 0, 0),
            value_eur=1000.0,
        )
        mock_cash_flow_repo.get_by_date_range.return_value = [cash_flow]
        mock_trade_repo.get_all_in_range.return_value = [trade]

        with patch(
            "app.domain.analytics.reconstruction.cash.CashFlowRepository",
            return_value=mock_cash_flow_repo,
        ):
            with patch(
                "app.domain.analytics.reconstruction.cash.TradeRepository",
                return_value=mock_trade_repo,
            ):
                result = await reconstruct_cash_balance(
                    start_date="2024-01-01", end_date="2024-01-05", initial_cash=1000.0
                )

                # Net on 2024-01-03: +500 (deposit) - 1000 (buy) = -500
                # Final: 1000 - 500 = 500
                assert result.iloc[2] == 500.0

    @pytest.mark.asyncio
    async def test_filters_trades_outside_date_range(
        self, mock_cash_flow_repo, mock_trade_repo
    ):
        """Test that trades outside date range are filtered."""
        from app.domain.analytics.reconstruction.cash import reconstruct_cash_balance

        trade_before = Trade(
            symbol="AAPL",
            side=TradeSide.BUY,
            quantity=10.0,
            price=100.0,
            executed_at=datetime(2023, 12, 30, 10, 0, 0),  # Before range
            value_eur=1000.0,
        )
        trade_in_range = Trade(
            symbol="MSFT",
            side=TradeSide.BUY,
            quantity=5.0,
            price=200.0,
            executed_at=datetime(2024, 1, 3, 10, 0, 0),  # In range
            value_eur=1000.0,
        )
        trade_after = Trade(
            symbol="GOOG",
            side=TradeSide.BUY,
            quantity=2.0,
            price=150.0,
            executed_at=datetime(2024, 1, 10, 10, 0, 0),  # After range
            value_eur=300.0,
        )
        mock_trade_repo.get_all_in_range.return_value = [
            trade_before,
            trade_in_range,
            trade_after,
        ]

        with patch(
            "app.domain.analytics.reconstruction.cash.CashFlowRepository",
            return_value=mock_cash_flow_repo,
        ):
            with patch(
                "app.domain.analytics.reconstruction.cash.TradeRepository",
                return_value=mock_trade_repo,
            ):
                result = await reconstruct_cash_balance(
                    start_date="2024-01-01", end_date="2024-01-05", initial_cash=2000.0
                )

                # Only trade_in_range should affect result
                # 2000 - 1000 = 1000
                assert result.iloc[2] == 1000.0

    @pytest.mark.asyncio
    async def test_handles_trade_with_datetime_string_executed_at(
        self, mock_cash_flow_repo, mock_trade_repo
    ):
        """Test handling of trade with string executed_at (ISO format)."""
        from app.domain.analytics.reconstruction.cash import reconstruct_cash_balance

        # Create a trade with string executed_at
        trade = MagicMock(spec=Trade)
        trade.side = TradeSide.BUY
        trade.value_eur = 1000.0
        trade.executed_at = "2024-01-03T10:00:00"  # String instead of datetime
        trade.quantity = 10.0
        trade.price = 100.0
        trade.currency_rate = None

        mock_trade_repo.get_all_in_range.return_value = [trade]

        with patch(
            "app.domain.analytics.reconstruction.cash.CashFlowRepository",
            return_value=mock_cash_flow_repo,
        ):
            with patch(
                "app.domain.analytics.reconstruction.cash.TradeRepository",
                return_value=mock_trade_repo,
            ):
                result = await reconstruct_cash_balance(
                    start_date="2024-01-01", end_date="2024-01-05", initial_cash=2000.0
                )

                # Should extract date correctly from string
                assert result.iloc[2] == 1000.0

    @pytest.mark.asyncio
    async def test_handles_empty_cash_flows_and_trades(
        self, mock_cash_flow_repo, mock_trade_repo
    ):
        """Test handling when no cash flows or trades exist."""
        from app.domain.analytics.reconstruction.cash import reconstruct_cash_balance

        with patch(
            "app.domain.analytics.reconstruction.cash.CashFlowRepository",
            return_value=mock_cash_flow_repo,
        ):
            with patch(
                "app.domain.analytics.reconstruction.cash.TradeRepository",
                return_value=mock_trade_repo,
            ):
                result = await reconstruct_cash_balance(
                    start_date="2024-01-01", end_date="2024-01-05", initial_cash=500.0
                )

                # Should return constant series with initial cash
                assert len(result) == 5
                assert (result == 500.0).all()

    @pytest.mark.asyncio
    async def test_handles_zero_initial_cash(
        self, mock_cash_flow_repo, mock_trade_repo
    ):
        """Test handling of zero initial cash."""
        from app.domain.analytics.reconstruction.cash import reconstruct_cash_balance

        cash_flow = CashFlow(
            transaction_id="TX1",
            type_doc_id=1,
            transaction_type="DEPOSIT",
            date="2024-01-03",
            amount=1000.0,
            currency=Currency.EUR,
            amount_eur=1000.0,
        )
        mock_cash_flow_repo.get_by_date_range.return_value = [cash_flow]

        with patch(
            "app.domain.analytics.reconstruction.cash.CashFlowRepository",
            return_value=mock_cash_flow_repo,
        ):
            with patch(
                "app.domain.analytics.reconstruction.cash.TradeRepository",
                return_value=mock_trade_repo,
            ):
                result = await reconstruct_cash_balance(
                    start_date="2024-01-01", end_date="2024-01-05", initial_cash=0.0
                )

                assert result.iloc[0] == 0.0
                assert result.iloc[2] == 1000.0  # After deposit
