"""Sync job implementations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from sentinel.jobs.types import BaseJob, MarketTiming

logger = logging.getLogger(__name__)


@dataclass
class PortfolioSyncJob(BaseJob):
    """Sync portfolio positions from broker."""

    _portfolio: object = field(default=None, repr=False)

    def __init__(self, portfolio):
        super().__init__(
            _id='sync:portfolio',
            _job_type='sync:portfolio',
            _timeout=timedelta(minutes=5),
            _market_timing=MarketTiming.ANY_TIME,
        )
        self._portfolio = portfolio

    async def execute(self) -> None:
        """Execute portfolio sync."""
        await self._portfolio.sync()
        logger.info("Portfolio sync complete")


@dataclass
class PriceSyncJob(BaseJob):
    """Sync historical prices for all securities."""

    _db: object = field(default=None, repr=False)
    _broker: object = field(default=None, repr=False)
    _cache: object = field(default=None, repr=False)

    def __init__(self, db, broker, cache):
        super().__init__(
            _id='sync:prices',
            _job_type='sync:prices',
            _timeout=timedelta(minutes=30),
            _market_timing=MarketTiming.ANY_TIME,
        )
        self._db = db
        self._broker = broker
        self._cache = cache

    async def execute(self) -> None:
        """Execute price sync."""
        # Clear analysis cache since prices are changing
        cleared = self._cache.clear()
        logger.info(f"Cleared {cleared} cached analyses before price sync")

        securities = await self._db.get_all_securities(active_only=True)
        symbols = [s['symbol'] for s in securities]

        prices = await self._broker.get_historical_prices_bulk(symbols, years=10)
        synced = 0

        for symbol, data in prices.items():
            if data and len(data) > 0:
                await self._db.replace_prices(symbol, data)
                synced += 1

        logger.info(f"Price sync complete: {synced}/{len(symbols)} securities updated")


@dataclass
class QuoteSyncJob(BaseJob):
    """Sync quote data for all securities."""

    _db: object = field(default=None, repr=False)
    _broker: object = field(default=None, repr=False)

    def __init__(self, db, broker):
        super().__init__(
            _id='sync:quotes',
            _job_type='sync:quotes',
            _timeout=timedelta(minutes=10),
            _market_timing=MarketTiming.ANY_TIME,
        )
        self._db = db
        self._broker = broker

    async def execute(self) -> None:
        """Execute quote sync."""
        securities = await self._db.get_all_securities(active_only=True)
        symbols = [s['symbol'] for s in securities]

        if not symbols:
            logger.info("No securities to sync quotes for")
            return

        quotes = await self._broker.get_quotes(symbols)
        if quotes:
            await self._db.update_quotes_bulk(quotes)
            logger.info(f"Quote sync complete: {len(quotes)} securities")
        else:
            logger.warning("No quotes returned from broker")


@dataclass
class MetadataSyncJob(BaseJob):
    """Sync security metadata from broker."""

    _db: object = field(default=None, repr=False)
    _broker: object = field(default=None, repr=False)

    def __init__(self, db, broker):
        super().__init__(
            _id='sync:metadata',
            _job_type='sync:metadata',
            _timeout=timedelta(minutes=15),
            _market_timing=MarketTiming.ANY_TIME,
        )
        self._db = db
        self._broker = broker

    async def execute(self) -> None:
        """Execute metadata sync."""
        securities = await self._db.get_all_securities(active_only=True)
        synced = 0

        for sec in securities:
            symbol = sec['symbol']
            info = await self._broker.get_security_info(symbol)
            if info:
                market_id = str(info.get('mrkt', {}).get('mkt_id', ''))
                await self._db.update_security_metadata(symbol, info, market_id)
                synced += 1

        logger.info(f"Metadata sync complete: {synced} securities")


@dataclass
class ExchangeRateSyncJob(BaseJob):
    """Sync exchange rates."""

    def __init__(self):
        super().__init__(
            _id='sync:exchange_rates',
            _job_type='sync:exchange_rates',
            _timeout=timedelta(minutes=5),
            _market_timing=MarketTiming.ANY_TIME,
        )

    async def execute(self) -> None:
        """Execute exchange rate sync."""
        from sentinel.currency import Currency

        currency = Currency()
        rates = await currency.sync_rates()
        logger.info(f"Exchange rates synced: {len(rates)} currencies")
