"""
Sentinel - Long-term portfolio management system.

Usage:
    from sentinel import Database, Security, Portfolio, Broker, Settings

    # Initialize
    db = Database()
    await db.connect()

    # Work with securities
    security = Security('AAPL.US')
    await security.load()
    await security.buy(10)

    # Work with portfolio
    portfolio = Portfolio()
    await portfolio.sync()
    value = await portfolio.total_value()
"""

from sentinel.analyzer import Analyzer
from sentinel.broker import Broker
from sentinel.cache import Cache
from sentinel.currency import Currency
from sentinel.database import Database

# Job system
from sentinel.jobs import (
    BaseJob,
    JobWrapper,
    MarketTiming,
    Processor,
    Queue,
    Registry,
    Scheduler,
    SyncScheduler,
)
from sentinel.led import LEDController
from sentinel.portfolio import Portfolio
from sentinel.security import Security
from sentinel.settings import Settings

__all__ = [
    "Database",
    "Settings",
    "Broker",
    "Security",
    "Portfolio",
    "Analyzer",
    "Currency",
    "Cache",
    "LEDController",
    # Job system
    "Queue",
    "Registry",
    "Processor",
    "Scheduler",
    "SyncScheduler",
    "MarketTiming",
    "BaseJob",
    "JobWrapper",
]
