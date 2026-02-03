"""FastAPI dependencies for API routers.

Provides common dependencies that can be injected into route handlers.
"""

from dataclasses import dataclass

from sentinel.broker import Broker
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.settings import Settings


@dataclass
class CommonDependencies:
    """Common dependencies used across API routes.

    Usage:
        @router.get("/endpoint")
        async def my_endpoint(deps: Annotated[CommonDependencies, Depends(get_common_deps)]):
            settings = deps.settings
            # ...
    """

    db: Database
    settings: Settings
    broker: Broker
    currency: Currency


async def get_common_deps() -> CommonDependencies:
    """Factory for common dependencies.

    Returns singleton instances of Database, Settings, Broker, and Currency.
    """
    return CommonDependencies(
        db=Database(),
        settings=Settings(),
        broker=Broker(),
        currency=Currency(),
    )
