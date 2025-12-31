# API routers - re-exported from modules for backward compatibility
# Note: These are imported directly in main.py from their module locations
from app.api import charts  # charts.py is still in app/api/
from app.api import settings  # settings.py is still in app/api/
from app.modules.allocation.api import allocation
from app.modules.cash_flows.api import cash_flows
from app.modules.optimization.api import optimizer
from app.modules.planning.api import planner, recommendations
from app.modules.portfolio.api import portfolio
from app.modules.system.api import status
from app.modules.trading.api import trades
from app.modules.universe.api import securities

__all__ = [
    "portfolio",
    "securities",
    "trades",
    "status",
    "allocation",
    "cash_flows",
    "charts",
    "recommendations",
    "optimizer",
    "planner",
    "settings",
]
