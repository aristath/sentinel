"""Stock setup service for adding stocks to the universe.

Handles comprehensive stock setup by accepting either a Tradernet symbol or ISIN,
resolving all necessary data from Tradernet and Yahoo Finance, and preparing
the stock for use in the application.
"""

import logging
from typing import Optional

from app.core.database.manager import DatabaseManager
from app.domain.events import StockAddedEvent, get_event_bus
from app.domain.models import Stock
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.external.tradernet import TradernetClient
from app.jobs.stocks_data_sync import _sync_historical_for_symbol
from app.modules.universe.database.stock_repository import StockRepository
from app.modules.universe.domain.symbol_resolver import IdentifierType, SymbolResolver
from app.shared.domain.value_objects.currency import Currency

logger = logging.getLogger(__name__)


class StockSetupService:
    """Service for setting up new stocks in the universe."""

    def __init__(
        self,
        stock_repo: StockRepository,
        scoring_service,
        tradernet_client: TradernetClient,
        db_manager: DatabaseManager,
        symbol_resolver: Optional[SymbolResolver] = None,
    ):
        """Initialize the service.

        Args:
            stock_repo: Stock repository
            scoring_service: Scoring service for calculating initial scores
            tradernet_client: Tradernet client for API calls
            db_manager: Database manager for history operations
            symbol_resolver: Optional symbol resolver (will create if not provided)
        """
        self._stock_repo = stock_repo
        self._scoring_service = scoring_service
        self._tradernet_client = tradernet_client
        self._db_manager = db_manager
        self._symbol_resolver = symbol_resolver or SymbolResolver(
            tradernet_client, stock_repo
        )

    async def add_stock_by_identifier(
        self,
        identifier: str,
        min_lot: int = 1,
        allow_buy: bool = True,
        allow_sell: bool = True,
    ) -> Stock:
        """Add a stock to the universe by symbol or ISIN.

        This method:
        1. Resolves the identifier to get all necessary symbols
        2. Fetches data from Tradernet (symbol, name, currency, ISIN)
        3. Fetches data from Yahoo Finance (country, exchange, industry)
        4. Creates the stock in the database
        5. Fetches historical price data (10 years initial seed)
        6. Calculates and saves the initial stock score

        Args:
            identifier: Stock identifier - Tradernet symbol (e.g., "AAPL.US") or ISIN (e.g., "US0378331005")
            min_lot: Minimum lot size (default: 1)
            allow_buy: Whether buying is allowed (default: True)
            allow_sell: Whether selling is allowed (default: True)

        Returns:
            Created Stock domain object

        Raises:
            ValueError: If stock already exists or identifier is invalid
            ConnectionError: If Tradernet connection fails when required
        """
        identifier = identifier.strip().upper()
        if not identifier:
            raise ValueError("Identifier cannot be empty")

        # Check if stock already exists
        existing = await self._stock_repo.get_by_identifier(identifier)
        if existing:
            raise ValueError(f"Stock already exists: {existing.symbol}")

        # Step 1: Detect identifier type and resolve
        id_type = self._symbol_resolver.detect_type(identifier)
        symbol_info = await self._symbol_resolver.resolve(identifier)

        # Step 2: Fetch data from Tradernet
        tradernet_symbol: Optional[str] = None
        tradernet_name: Optional[str] = None
        currency: Optional[Currency] = None
        isin: Optional[str] = symbol_info.isin  # Use ISIN from resolver if available

        if id_type == IdentifierType.TRADERNET:
            # Already have Tradernet symbol
            tradernet_symbol = identifier
            tradernet_data = await self._get_tradernet_data(tradernet_symbol)
            if tradernet_data:
                # Prefer ISIN from resolver, fallback to API data
                if not isin:
                    isin = tradernet_data.get("isin")
                if not currency:
                    currency = tradernet_data.get("currency")  # type: ignore[assignment]
        elif id_type == IdentifierType.ISIN:
            # Need to look up Tradernet symbol from ISIN
            isin = identifier  # Use the provided ISIN
            lookup_result = await self._get_tradernet_symbol_from_isin(isin)
            if not lookup_result:
                raise ValueError(f"Could not find Tradernet symbol for ISIN: {isin}")
            tradernet_symbol = lookup_result["symbol"]
            tradernet_name = lookup_result.get("name")
            currency = lookup_result.get("currency")  # type: ignore[assignment]
            # Validate ISIN matches (warn if different, but use the one we looked up)
            resolved_isin = lookup_result.get("isin")
            if resolved_isin and resolved_isin != isin:
                logger.warning(
                    f"ISIN mismatch: requested {isin}, got {resolved_isin}. Using requested ISIN."
                )
        else:
            # Yahoo format - try to use as-is, but we still need Tradernet symbol
            raise ValueError(
                f"Cannot add stock with identifier '{identifier}'. "
                "Please provide a Tradernet symbol (e.g., AAPL.US) or ISIN (e.g., US0378331005)."
            )

        if not tradernet_symbol:
            raise ValueError(f"Could not resolve Tradernet symbol for: {identifier}")

        # Ensure we have ISIN - try to get it if we don't have it yet
        if not isin:
            tradernet_data = await self._get_tradernet_data(tradernet_symbol)
            if tradernet_data:
                isin = tradernet_data.get("isin")

        # Step 3: Fetch data from Yahoo Finance
        yahoo_symbol = symbol_info.yahoo_symbol or isin or tradernet_symbol
        country, full_exchange_name = yahoo.get_stock_country_and_exchange(
            tradernet_symbol, yahoo_symbol
        )
        industry = yahoo.get_stock_industry(tradernet_symbol, yahoo_symbol)

        # Get name - prefer Tradernet name, fallback to Yahoo Finance
        name = tradernet_name
        if not name:
            name = await self._get_stock_name_from_yahoo(tradernet_symbol, yahoo_symbol)

        if not name:
            raise ValueError(f"Could not determine stock name for: {identifier}")

        # Step 4: Create stock
        # Create stock using factory, but we need to handle ISIN separately
        # since factory doesn't support it directly. Create Stock directly instead.
        # Type assertions: we've validated all required fields above
        assert tradernet_symbol is not None, "tradernet_symbol must be set"
        assert name is not None, "name must be set"
        stock = Stock(
            symbol=tradernet_symbol,
            name=name,
            country=country,
            fullExchangeName=full_exchange_name,
            yahoo_symbol=yahoo_symbol,
            isin=isin,
            industry=industry,
            priority_multiplier=1.0,
            min_lot=min_lot,
            active=True,
            allow_buy=allow_buy,
            allow_sell=allow_sell,
            currency=currency,
        )

        await self._stock_repo.create(stock)

        # Publish domain event
        event_bus = get_event_bus()
        event_bus.publish(StockAddedEvent(stock=stock))

        # Step 5: Fetch historical data (10 years initial seed)
        try:
            await _sync_historical_for_symbol(stock.symbol)
            logger.info(f"Fetched historical data for {stock.symbol}")
        except Exception as e:
            logger.warning(
                f"Failed to fetch historical data for {stock.symbol}: {e}",
                exc_info=True,
            )
            # Continue - historical data failure shouldn't block stock creation

        # Step 6: Calculate initial score
        try:
            await self._scoring_service.calculate_and_save_score(
                stock.symbol, stock.yahoo_symbol, country=country, industry=industry
            )
            logger.info(f"Calculated initial score for {stock.symbol}")
        except Exception as e:
            logger.warning(
                f"Failed to calculate score for {stock.symbol}: {e}", exc_info=True
            )
            # Continue - score calculation failure shouldn't block stock creation

        return stock

    async def _get_tradernet_data(
        self, symbol: str
    ) -> Optional[dict[str, Optional[str | Currency]]]:
        """Get data from Tradernet for a symbol.

        Args:
            symbol: Tradernet symbol

        Returns:
            Dict with 'currency' and 'isin' keys, or None if fetch fails
        """
        try:
            # ensure_tradernet_connected is async, but we need to handle connection ourselves
            if not self._tradernet_client.is_connected:
                if not self._tradernet_client.connect():
                    logger.warning("Tradernet not connected, skipping data fetch")
                    return None

            response = self._tradernet_client.get_quotes_raw([symbol])
            quotes_list = response.get("result", {}).get("q", [])
            if quotes_list and len(quotes_list) > 0:
                quote_data = quotes_list[0]
                currency_str = quote_data.get("x_curr")
                currency = Currency.from_string(currency_str) if currency_str else None
                isin = quote_data.get("issue_nb")
                return {"currency": currency, "isin": isin}
            return None
        except Exception as e:
            logger.warning(f"Failed to get Tradernet data for {symbol}: {e}")
            return None

    async def _get_tradernet_symbol_from_isin(
        self, isin: str
    ) -> Optional[dict[str, Optional[str | Currency]]]:
        """Get Tradernet symbol, name, and currency from ISIN using find_symbol.

        Args:
            isin: ISIN identifier

        Returns:
            Dict with 'symbol', 'name', 'currency', and 'isin' keys, or None if not found
        """
        try:
            # Ensure Tradernet is connected
            if not self._tradernet_client.is_connected:
                if not self._tradernet_client.connect():
                    logger.warning("Tradernet not connected, cannot lookup ISIN")
                    return None

            result = self._tradernet_client.find_symbol(isin)
            found_list = result.get("found", [])
            if not found_list or len(found_list) == 0:
                logger.warning(f"No results from find_symbol for ISIN: {isin}")
                return None

            # Use first result (typically the primary exchange listing)
            instrument = found_list[0]
            symbol = instrument.get("t")
            name = instrument.get("nm")
            currency_str = instrument.get("x_curr")
            currency = Currency.from_string(currency_str) if currency_str else None
            resolved_isin = instrument.get("isin")

            if not symbol:
                logger.warning(f"No symbol in find_symbol result for ISIN: {isin}")
                return None

            return {
                "symbol": symbol,
                "name": name,
                "currency": currency,
                "isin": resolved_isin,
            }
        except Exception as e:
            logger.error(
                f"Failed to lookup ISIN {isin} via find_symbol: {e}", exc_info=True
            )
            return None

    async def _get_stock_name_from_yahoo(
        self, symbol: str, yahoo_symbol: Optional[str]
    ) -> Optional[str]:
        """Get stock name from Yahoo Finance.

        Args:
            symbol: Tradernet symbol (for logging)
            yahoo_symbol: Yahoo Finance symbol to look up

        Returns:
            Stock name or None if unavailable
        """
        try:
            import yfinance as yf

            yf_symbol = yahoo_symbol or symbol
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info

            # Try longName first, then shortName, then name
            name = info.get("longName") or info.get("shortName") or info.get("name")
            return name
        except Exception as e:
            logger.warning(f"Failed to get name from Yahoo Finance for {symbol}: {e}")
            return None
