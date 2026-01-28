"""Job implementations and registration."""

from __future__ import annotations

from sentinel.jobs.registry import Registry, RetryConfig
from sentinel.jobs.implementations.sync import (
    PortfolioSyncJob,
    PriceSyncJob,
    QuoteSyncJob,
    MetadataSyncJob,
    ExchangeRateSyncJob,
)
from sentinel.jobs.implementations.scoring import CalculateScoresJob
from sentinel.jobs.implementations.analytics import (
    CorrelationJob,
    RegimeJob,
    TransferEntropyJob,
)
from sentinel.jobs.implementations.trading import CheckMarketsJob, RebalanceJob, ExecuteTradesJob, RefreshPlanJob
from sentinel.jobs.implementations.ml import MLRetrainJob, MLMonitorJob


async def register_all_jobs(
    registry: Registry,
    db,
    broker,
    portfolio,
    analyzer,
    cleaner,
    detector,
    te_analyzer,
    planner,
    retrainer,
    monitor,
    cache,
) -> None:
    """Register all job types with the registry."""

    # Sync jobs
    await registry.register(
        'sync:portfolio',
        lambda p: PortfolioSyncJob(portfolio),
        RetryConfig.for_sync(),
    )
    await registry.register(
        'sync:prices',
        lambda p: PriceSyncJob(db, broker, cache),
        RetryConfig.for_sync(),
    )
    await registry.register(
        'sync:quotes',
        lambda p: QuoteSyncJob(db, broker),
        RetryConfig.for_sync(),
    )
    await registry.register(
        'sync:metadata',
        lambda p: MetadataSyncJob(db, broker),
        RetryConfig.for_sync(),
    )
    await registry.register(
        'sync:exchange_rates',
        lambda p: ExchangeRateSyncJob(),
        RetryConfig.for_sync(),
    )

    # Scoring
    await registry.register(
        'scoring:calculate',
        lambda p: CalculateScoresJob(analyzer),
        RetryConfig.for_analytics(),
    )

    # Analytics
    await registry.register(
        'analytics:correlation',
        lambda p: CorrelationJob(cleaner, db),
        RetryConfig.for_analytics(),
    )
    await registry.register(
        'analytics:regime',
        lambda p: RegimeJob(detector, db),
        RetryConfig.for_analytics(),
    )
    await registry.register(
        'analytics:transfer_entropy',
        lambda p: TransferEntropyJob(te_analyzer, db),
        RetryConfig.for_analytics(),
    )

    # Trading
    await registry.register(
        'trading:check_markets',
        lambda p: CheckMarketsJob(broker, db, planner),
        RetryConfig.default(),
    )
    await registry.register(
        'trading:execute',
        lambda p: ExecuteTradesJob(broker, db, planner),
        RetryConfig.default(),
    )
    await registry.register(
        'trading:rebalance',
        lambda p: RebalanceJob(planner),
        RetryConfig.default(),
    )
    await registry.register(
        'planning:refresh',
        lambda p: RefreshPlanJob(db, planner),
        RetryConfig.default(),
    )

    # ML (parameterized by symbol)
    def create_ml_retrain(p):
        symbol = p.get('symbol', '')
        if not symbol:
            raise ValueError("ML retrain job requires 'symbol' parameter")
        return MLRetrainJob(symbol, retrainer)

    def create_ml_monitor(p):
        symbol = p.get('symbol', '')
        if not symbol:
            raise ValueError("ML monitor job requires 'symbol' parameter")
        return MLMonitorJob(symbol, monitor)

    await registry.register('ml:retrain', create_ml_retrain, RetryConfig.for_analytics())
    await registry.register('ml:monitor', create_ml_monitor, RetryConfig.default())


__all__ = [
    "register_all_jobs",
    "PortfolioSyncJob",
    "PriceSyncJob",
    "QuoteSyncJob",
    "MetadataSyncJob",
    "ExchangeRateSyncJob",
    "CalculateScoresJob",
    "CorrelationJob",
    "RegimeJob",
    "TransferEntropyJob",
    "CheckMarketsJob",
    "ExecuteTradesJob",
    "RebalanceJob",
    "RefreshPlanJob",
    "MLRetrainJob",
    "MLMonitorJob",
]
