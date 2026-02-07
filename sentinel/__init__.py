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

from sentinel.broker import Broker
from sentinel.cache import Cache
from sentinel.currency import Currency
from sentinel.database import Database

# Job system
from sentinel.jobs import (
    BrokerMarketChecker,
    MarketChecker,
    get_status,
    init,
    reschedule,
    run_now,
    stop,
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
    "Currency",
    "Cache",
    "LEDController",
    # Job system
    "init",
    "stop",
    "reschedule",
    "run_now",
    "get_status",
    "MarketChecker",
    "BrokerMarketChecker",
]
