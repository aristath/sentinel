"""Job implementations and registration."""

from __future__ import annotations

from sentinel.jobs.implementations.analytics import (
    RegimeJob,
)
from sentinel.jobs.implementations.backup import BackupR2Job
from sentinel.jobs.implementations.ml import MLMonitorJob, MLRetrainJob
from sentinel.jobs.implementations.scoring import CalculateScoresJob
from sentinel.jobs.implementations.sync import (
    ExchangeRateSyncJob,
    MetadataSyncJob,
    PortfolioSyncJob,
    PriceSyncJob,
    QuoteSyncJob,
)
from sentinel.jobs.implementations.trading import CheckMarketsJob, ExecuteTradesJob, RebalanceJob, RefreshPlanJob
from sentinel.jobs.registry import Registry, RetryConfig


async def register_all_jobs(
    registry: Registry,
    db,
    broker,
    portfolio,
    analyzer,
    detector,
    planner,
    retrainer,
    monitor,
    cache,
) -> None:
    """Register all job types with the registry."""

    # Sync jobs
    await registry.register(
        "sync:portfolio",
        lambda p: PortfolioSyncJob(portfolio),
        RetryConfig.for_sync(),
    )
    await registry.register(
        "sync:prices",
        lambda p: PriceSyncJob(db, broker, cache),
        RetryConfig.for_sync(),
    )
    await registry.register(
        "sync:quotes",
        lambda p: QuoteSyncJob(db, broker),
        RetryConfig.for_sync(),
    )
    await registry.register(
        "sync:metadata",
        lambda p: MetadataSyncJob(db, broker),
        RetryConfig.for_sync(),
    )
    await registry.register(
        "sync:exchange_rates",
        lambda p: ExchangeRateSyncJob(),
        RetryConfig.for_sync(),
    )

    # Scoring
    await registry.register(
        "scoring:calculate",
        lambda p: CalculateScoresJob(analyzer),
        RetryConfig.for_analytics(),
    )

    # Analytics
    await registry.register(
        "analytics:regime",
        lambda p: RegimeJob(detector, db),
        RetryConfig.for_analytics(),
    )

    # Trading
    await registry.register(
        "trading:check_markets",
        lambda p: CheckMarketsJob(broker, db, planner),
        RetryConfig.default(),
    )
    await registry.register(
        "trading:execute",
        lambda p: ExecuteTradesJob(broker, db, planner),
        RetryConfig.default(),
    )
    await registry.register(
        "trading:rebalance",
        lambda p: RebalanceJob(planner),
        RetryConfig.default(),
    )
    await registry.register(
        "planning:refresh",
        lambda p: RefreshPlanJob(db, planner),
        RetryConfig.default(),
    )

    # ML (parameterized by symbol)
    def create_ml_retrain(p):
        symbol = p.get("symbol", "")
        if not symbol:
            raise ValueError("ML retrain job requires 'symbol' parameter")
        return MLRetrainJob(symbol, retrainer)

    def create_ml_monitor(p):
        symbol = p.get("symbol", "")
        if not symbol:
            raise ValueError("ML monitor job requires 'symbol' parameter")
        return MLMonitorJob(symbol, monitor)

    await registry.register("ml:retrain", create_ml_retrain, RetryConfig.for_analytics())
    await registry.register("ml:monitor", create_ml_monitor, RetryConfig.default())

    # Backup
    await registry.register(
        "backup:r2",
        lambda p: BackupR2Job(db),
        RetryConfig.for_sync(),
    )


__all__ = [
    "register_all_jobs",
    "PortfolioSyncJob",
    "PriceSyncJob",
    "QuoteSyncJob",
    "MetadataSyncJob",
    "ExchangeRateSyncJob",
    "CalculateScoresJob",
    "RegimeJob",
    "CheckMarketsJob",
    "ExecuteTradesJob",
    "RebalanceJob",
    "RefreshPlanJob",
    "MLRetrainJob",
    "MLMonitorJob",
    "BackupR2Job",
]
