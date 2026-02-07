"""Tests for job task functions."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.jobs.tasks import sync_prices


class TestSyncPricesClearsAnalysisCache:
    """Tests that sync_prices clears analysis cache before fetching new prices."""

    @pytest.mark.asyncio
    async def test_sync_prices_clears_analysis_cache_before_fetch(self):
        """Verify cache.clear() is called before broker.get_historical_prices_bulk."""
        # Track cross-object call ordering via a shared list
        call_order = []

        db = MagicMock()
        db.get_all_securities = AsyncMock(
            return_value=[
                {"symbol": "TEST.EU"},
            ]
        )

        db.save_prices = AsyncMock()

        broker = MagicMock()

        async def track_fetch(symbols, **kwargs):
            call_order.append(("broker.get_historical_prices_bulk",))
            return {"TEST.EU": [{"date": "2025-01-01", "close": 100.0}]}

        broker.get_historical_prices_bulk = AsyncMock(side_effect=track_fetch)

        cache = MagicMock()

        def track_analysis_cache_clear():
            call_order.append(("cache.clear",))
            return 5

        cache.clear = MagicMock(side_effect=track_analysis_cache_clear)

        await sync_prices(db, broker, cache)

        # analysis cache must have been cleared
        cache.clear.assert_called_once()

        # Verify ordering: cache clear happens before broker fetch
        clear_idx = next(i for i, c in enumerate(call_order) if c[0] == "cache.clear")
        fetch_idx = next(i for i, c in enumerate(call_order) if c[0] == "broker.get_historical_prices_bulk")
        assert clear_idx < fetch_idx, (
            f"cache.clear (index {clear_idx}) must precede get_historical_prices_bulk (index {fetch_idx})"
        )
