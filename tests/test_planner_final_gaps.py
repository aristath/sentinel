"""Tests for final uncovered code paths in planner package."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner import RebalanceEngine


@pytest.fixture
def _make_engine():
    """Factory to create an engine with proper settings_ctx."""

    def _create():
        db = MagicMock()
        engine = RebalanceEngine(db=db)
        engine._broker = MagicMock()
        engine._settings = MagicMock()
        engine._settings.get = AsyncMock(side_effect=lambda key, default=None: default)
        engine._portfolio = MagicMock()
        engine._currency = MagicMock()
        engine._currency.get_rate = AsyncMock(return_value=1.0)
        engine._currency.to_eur = AsyncMock(side_effect=lambda amt, curr: amt)
        return engine

    return _create


class TestRebalanceFinalCoverage:
    """Tests for final uncovered RebalanceEngine paths."""

    @pytest.mark.asyncio
    async def test_check_price_anomaly_zero_price(self, _make_engine):
        """Test zero price handling."""
        engine = _make_engine()

        # Zero price
        hist_rows = [
            {"close": 100.0, "date": "2023-01-01"},
            {"close": 101.0, "date": "2023-01-02"},
            {"close": 102.0, "date": "2023-01-03"},
        ]

        # Test zero price
        is_anomaly, reason = engine._check_price_anomaly(price=0.0, hist_rows=hist_rows, symbol="AAPL.US")
        assert not is_anomaly
        assert reason == ""
