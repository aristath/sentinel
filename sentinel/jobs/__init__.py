"""
Jobs system - Heartbeat-based job scheduling with dependencies and market timing.

Usage:
    from sentinel.jobs import Queue, Registry, Processor, Scheduler

    queue = Queue()
    registry = Registry()
    processor = Processor(db, queue, registry, market_checker)
    scheduler = Scheduler(db, queue, registry, market_checker)

    await processor.start()
    await scheduler.start()
"""

from sentinel.jobs.types import MarketTiming, Job, BaseJob, JobWrapper
from sentinel.jobs.queue import Queue
from sentinel.jobs.registry import Registry, RetryConfig
from sentinel.jobs.processor import Processor
from sentinel.jobs.scheduler import Scheduler, SyncScheduler
from sentinel.jobs.market import MarketChecker, BrokerMarketChecker

__all__ = [
    # Types
    "MarketTiming",
    "Job",
    "BaseJob",
    "JobWrapper",
    # Queue
    "Queue",
    # Registry
    "Registry",
    "RetryConfig",
    # Processor
    "Processor",
    # Scheduler
    "Scheduler",
    "SyncScheduler",
    # Market
    "MarketChecker",
    "BrokerMarketChecker",
]
