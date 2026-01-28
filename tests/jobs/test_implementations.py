"""Tests for job implementations."""

import pytest
import pytest_asyncio
from datetime import timedelta

from sentinel.jobs.types import MarketTiming
from sentinel.jobs.registry import Registry
from sentinel.jobs.implementations import (
    PortfolioSyncJob,
    PriceSyncJob,
    QuoteSyncJob,
    MetadataSyncJob,
    ExchangeRateSyncJob,
    CalculateScoresJob,
    CorrelationJob,
    RegimeJob,
    TransferEntropyJob,
    CheckMarketsJob,
    RebalanceJob,
    MLRetrainJob,
    MLMonitorJob,
    register_all_jobs,
)


class MockPortfolio:
    def __init__(self):
        self.synced = False

    async def sync(self):
        self.synced = True


class MockBroker:
    def __init__(self):
        self.connected = True

    async def get_historical_prices_bulk(self, symbols, years):
        return {s: [{'date': '2024-01-01', 'close': 100}] for s in symbols}

    async def get_quotes(self, symbols):
        return {s: {'price': 100} for s in symbols}

    async def get_security_info(self, symbol):
        return {'mrkt': {'mkt_id': '123'}}

    async def get_market_status(self, market):
        return {'m': []}


class MockDB:
    def __init__(self):
        self.securities = [{'symbol': 'TEST.US'}]

    async def get_all_securities(self, active_only=True):
        return self.securities

    async def replace_prices(self, symbol, prices):
        pass

    async def update_quotes_bulk(self, quotes):
        pass

    async def update_security_metadata(self, symbol, info, market_id):
        pass


class MockCache:
    def clear(self):
        return 5


class MockAnalyzer:
    async def update_scores(self):
        return 1


class MockCleaner:
    async def calculate_raw_correlation(self, symbols, days):
        return None, []

    async def clean_correlation(self, raw):
        return raw

    async def store_matrices(self, raw, cleaned, symbols):
        pass


class MockDetector:
    async def train_model(self, symbols):
        return True


class MockTEAnalyzer:
    async def calculate_matrix(self, symbols):
        return []


class MockPlanner:
    async def get_rebalance_summary(self):
        return {'needs_rebalance': False}

    async def get_recommendations(self):
        return []


class MockRetrainer:
    async def retrain_symbol(self, symbol):
        return {'validation_rmse': 0.1, 'training_samples': 100}


class MockMonitor:
    async def track_symbol_performance(self, symbol):
        return {'predictions_evaluated': 0}


def test_portfolio_sync_job_config():
    """PortfolioSyncJob should have correct configuration."""
    job = PortfolioSyncJob(MockPortfolio())

    assert job.id() == 'sync:portfolio'
    assert job.type() == 'sync:portfolio'
    assert job.market_timing() == MarketTiming.ANY_TIME
    assert job.timeout() == timedelta(minutes=5)


@pytest.mark.asyncio
async def test_portfolio_sync_job_execute():
    """PortfolioSyncJob should call portfolio.sync()."""
    portfolio = MockPortfolio()
    job = PortfolioSyncJob(portfolio)

    await job.execute()

    assert portfolio.synced is True


def test_price_sync_job_config():
    """PriceSyncJob should have correct configuration."""
    job = PriceSyncJob(MockDB(), MockBroker(), MockCache())

    assert job.id() == 'sync:prices'
    assert job.type() == 'sync:prices'
    assert job.market_timing() == MarketTiming.ANY_TIME
    assert job.timeout() == timedelta(minutes=30)


def test_ml_retrain_job_config():
    """MLRetrainJob should have correct configuration."""
    job = MLRetrainJob('AAPL.US', MockRetrainer())

    assert job.id() == 'ml:retrain:AAPL.US'
    assert job.type() == 'ml:retrain'
    assert job.subject() == 'AAPL.US'
    assert job.market_timing() == MarketTiming.ALL_MARKETS_CLOSED


def test_ml_monitor_job_config():
    """MLMonitorJob should have correct configuration."""
    job = MLMonitorJob('AAPL.US', MockMonitor())

    assert job.id() == 'ml:monitor:AAPL.US'
    assert job.type() == 'ml:monitor'
    assert job.subject() == 'AAPL.US'
    assert job.market_timing() == MarketTiming.ANY_TIME


def test_correlation_job_config():
    """CorrelationJob should have correct configuration."""
    job = CorrelationJob(MockCleaner(), MockDB())

    assert job.id() == 'analytics:correlation'
    assert job.type() == 'analytics:correlation'
    assert job.market_timing() == MarketTiming.ALL_MARKETS_CLOSED


def test_check_markets_job_config():
    """CheckMarketsJob should have correct configuration."""
    job = CheckMarketsJob(MockBroker(), MockDB(), MockPlanner())

    assert job.id() == 'trading:check_markets'
    assert job.type() == 'trading:check_markets'
    assert job.market_timing() == MarketTiming.DURING_MARKET_OPEN


@pytest_asyncio.fixture
async def registry_with_all_jobs():
    """Create a registry with all jobs registered."""
    registry = Registry()

    await register_all_jobs(
        registry,
        db=MockDB(),
        broker=MockBroker(),
        portfolio=MockPortfolio(),
        analyzer=MockAnalyzer(),
        cleaner=MockCleaner(),
        detector=MockDetector(),
        te_analyzer=MockTEAnalyzer(),
        planner=MockPlanner(),
        retrainer=MockRetrainer(),
        monitor=MockMonitor(),
        cache=MockCache(),
    )

    return registry


@pytest.mark.asyncio
async def test_register_all_jobs_registers_sync_jobs(registry_with_all_jobs):
    """register_all_jobs should register all sync job types."""
    registry = registry_with_all_jobs

    assert registry.is_registered('sync:portfolio')
    assert registry.is_registered('sync:prices')
    assert registry.is_registered('sync:quotes')
    assert registry.is_registered('sync:metadata')
    assert registry.is_registered('sync:exchange_rates')


@pytest.mark.asyncio
async def test_register_all_jobs_registers_analytics_jobs(registry_with_all_jobs):
    """register_all_jobs should register all analytics job types."""
    registry = registry_with_all_jobs

    assert registry.is_registered('analytics:correlation')
    assert registry.is_registered('analytics:regime')
    assert registry.is_registered('analytics:transfer_entropy')


@pytest.mark.asyncio
async def test_register_all_jobs_registers_ml_jobs(registry_with_all_jobs):
    """register_all_jobs should register ML job types."""
    registry = registry_with_all_jobs

    assert registry.is_registered('ml:retrain')
    assert registry.is_registered('ml:monitor')


@pytest.mark.asyncio
async def test_registry_creates_ml_jobs_with_params(registry_with_all_jobs):
    """Registry should create ML jobs with symbol parameter."""
    registry = registry_with_all_jobs

    job = await registry.create('ml:retrain', {'symbol': 'TSLA.US'})
    assert job.id() == 'ml:retrain:TSLA.US'
    assert job.subject() == 'TSLA.US'

    job = await registry.create('ml:monitor', {'symbol': 'GOOG.US'})
    assert job.id() == 'ml:monitor:GOOG.US'
    assert job.subject() == 'GOOG.US'
