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

from sentinel.database import Database
from sentinel.settings import Settings
from sentinel.broker import Broker
from sentinel.security import Security
from sentinel.portfolio import Portfolio
from sentinel.analyzer import Analyzer
from sentinel.currency import Currency
from sentinel.cache import Cache
from sentinel.led import LEDController

# Job system
from sentinel.jobs import (
    Queue,
    Registry,
    Processor,
    Scheduler,
    SyncScheduler,
    MarketTiming,
    BaseJob,
    JobWrapper,
)

__all__ = [
    'Database',
    'Settings',
    'Broker',
    'Security',
    'Portfolio',
    'Analyzer',
    'Currency',
    'Cache',
    'LEDController',
    # Job system
    'Queue',
    'Registry',
    'Processor',
    'Scheduler',
    'SyncScheduler',
    'MarketTiming',
    'BaseJob',
    'JobWrapper',
]
