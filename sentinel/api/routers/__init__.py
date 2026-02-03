"""API routers for Sentinel.

Each router handles a specific domain of the API.
"""

from sentinel.api.routers.jobs import router as jobs_router
from sentinel.api.routers.jobs import set_scheduler
from sentinel.api.routers.ml import (
    backup_router,
    regime_router,
)
from sentinel.api.routers.ml import (
    router as ml_router,
)
from sentinel.api.routers.planner import router as planner_router
from sentinel.api.routers.portfolio import allocation_router, targets_router
from sentinel.api.routers.portfolio import router as portfolio_router
from sentinel.api.routers.securities import prices_router, scores_router, unified_router
from sentinel.api.routers.securities import router as securities_router
from sentinel.api.routers.settings import led_router
from sentinel.api.routers.settings import router as settings_router
from sentinel.api.routers.system import (
    backtest_router,
    cache_router,
    exchange_rates_router,
    markets_router,
    meta_router,
    pulse_router,
)
from sentinel.api.routers.system import (
    router as system_router,
)
from sentinel.api.routers.trading import cashflows_router, trading_actions_router
from sentinel.api.routers.trading import router as trading_router

__all__ = [
    "settings_router",
    "led_router",
    "portfolio_router",
    "allocation_router",
    "targets_router",
    "securities_router",
    "prices_router",
    "scores_router",
    "unified_router",
    "trading_router",
    "cashflows_router",
    "trading_actions_router",
    "planner_router",
    "jobs_router",
    "set_scheduler",
    "ml_router",
    "regime_router",
    "backup_router",
    "system_router",
    "cache_router",
    "backtest_router",
    "exchange_rates_router",
    "markets_router",
    "meta_router",
    "pulse_router",
]
