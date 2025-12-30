"""Negative balance rebalancer service.

Automatically addresses negative cash balances and ensures minimum currency reserves.
"""

import logging
from typing import Dict, List, Set

from app.application.services.currency_exchange_service import CurrencyExchangeService
from app.application.services.trade_execution_service import TradeExecutionService
from app.domain.models import Recommendation
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.value_objects.currency import Currency
from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.events import SystemEvent, emit
from app.infrastructure.external.tradernet import TradernetClient
from app.infrastructure.market_hours import get_open_markets, is_market_open
from app.repositories import PositionRepository, StockRepository

logger = logging.getLogger(__name__)

# Minimum currency reserve per trading currency
MIN_CURRENCY_RESERVE = 5.0


class NegativeBalanceRebalancer:
    """Service to automatically rebalance negative cash balances."""

    def __init__(
        self,
        tradernet_client: TradernetClient,
        currency_exchange_service: CurrencyExchangeService,
        trade_execution_service: TradeExecutionService,
        stock_repo: StockRepository,
        position_repo: PositionRepository,
        exchange_rate_service: ExchangeRateService,
    ):
        """Initialize the rebalancer.

        Args:
            tradernet_client: Tradernet client for balance checks
            currency_exchange_service: Service for currency conversions
            trade_execution_service: Service for executing trades
            stock_repo: Repository for stock data
            position_repo: Repository for position data
            exchange_rate_service: Service for exchange rate conversions
        """
        self._client = tradernet_client
        self._currency_service = currency_exchange_service
        self._trade_execution_service = trade_execution_service
        self._stock_repo = stock_repo
        self._position_repo = position_repo
        self._exchange_rate_service = exchange_rate_service

    async def get_trading_currencies(self) -> Set[str]:
        """Get currencies from active stocks in the universe.

        Returns:
            Set of currency codes (e.g., {"USD", "EUR", "GBP", "HKD"})
        """
        stocks = await self._stock_repo.get_all_active()
        currencies = set()
        for stock in stocks:
            if stock.currency:
                currency_str = (
                    stock.currency.value
                    if hasattr(stock.currency, "value")
                    else str(stock.currency)
                )
                currencies.add(currency_str.upper())
        return currencies

    async def check_currency_minimums(
        self, cash_balances: Dict[str, float]
    ) -> Dict[str, float]:
        """Check which currencies are below minimum reserve.

        Args:
            cash_balances: Dictionary of currency -> balance

        Returns:
            Dictionary of currency -> shortfall amount (positive value)
            Only includes currencies that are below minimum
        """
        trading_currencies = await self.get_trading_currencies()
        shortfalls: Dict[str, float] = {}

        for currency in trading_currencies:
            balance = cash_balances.get(currency, 0.0)
            if balance < MIN_CURRENCY_RESERVE:
                shortfall = MIN_CURRENCY_RESERVE - balance
                shortfalls[currency] = shortfall
                logger.warning(
                    f"Currency {currency} below minimum: balance={balance:.2f}, "
                    f"minimum={MIN_CURRENCY_RESERVE}, shortfall={shortfall:.2f}"
                )

        return shortfalls

    async def rebalance_negative_balances(self) -> bool:
        """Main orchestration method to rebalance negative balances.

        Sequence:
        1. Currency exchange from other currencies
        2. Position sales (if exchange insufficient)
        3. Final currency exchange to ensure all currencies have minimum

        Returns:
            True if rebalancing completed successfully, False otherwise
        """
        if not self._client.is_connected:
            if not self._client.connect():
                logger.error("Cannot connect to Tradernet for rebalancing")
                return False

        # Get current cash balances
        cash_balances_raw = self._client.get_cash_balances()
        cash_balances = {cb.currency: cb.amount for cb in cash_balances_raw}

        # Check for currencies below minimum
        shortfalls = await self.check_currency_minimums(cash_balances)

        if not shortfalls:
            logger.info("All currencies meet minimum reserve requirements")
            return True

        logger.warning(
            f"Starting negative balance rebalancing for {len(shortfalls)} currencies"
        )
        emit(SystemEvent.ERROR_OCCURRED, message="REBALANCING NEGATIVE BALANCES")

        # Step 1: Try currency exchange
        remaining_shortfalls = await self._step_1_currency_exchange(
            shortfalls, cash_balances
        )

        if not remaining_shortfalls:
            logger.info("Currency exchange resolved all shortfalls")
            return True

        # Step 2: Position sales if exchange insufficient
        await self._step_2_position_sales(remaining_shortfalls)

        # Step 3: Final currency exchange
        await self._step_3_final_exchange()

        return True

    async def _step_1_currency_exchange(
        self, shortfalls: Dict[str, float], cash_balances: Dict[str, float]
    ) -> Dict[str, float]:
        """Step 1: Exchange currencies to cover shortfalls.

        Args:
            shortfalls: Dictionary of currency -> shortfall amount
            cash_balances: Current cash balances by currency

        Returns:
            Remaining shortfalls after exchange attempts
        """
        remaining_shortfalls = shortfalls.copy()

        for currency, shortfall in shortfalls.items():
            # Find currencies with excess (balance > minimum + buffer)
            excess_currencies = []
            for other_currency, balance in cash_balances.items():
                if other_currency == currency:
                    continue
                # Check if this currency has enough to cover shortfall (with exchange rate)
                if balance > MIN_CURRENCY_RESERVE:
                    excess_currencies.append((other_currency, balance))

            # Try to exchange from currencies with excess
            for source_currency, source_balance in excess_currencies:
                if currency not in remaining_shortfalls:
                    break  # Already covered

                needed = remaining_shortfalls[currency]

                # Convert needed amount to source currency using exchange rate
                try:
                    rate = await self._exchange_rate_service.get_rate(
                        source_currency, currency
                    )
                    if rate > 0:
                        source_amount_needed = needed * rate
                    else:
                        # Fallback: assume 1:1 if rate unavailable
                        source_amount_needed = needed
                except Exception as e:
                    logger.warning(
                        f"Could not get exchange rate {source_currency}/{currency}: {e}, "
                        f"assuming 1:1"
                    )
                    source_amount_needed = needed

                # Check if we have enough in source currency
                available = source_balance - MIN_CURRENCY_RESERVE
                if available < source_amount_needed:
                    continue  # Not enough in this currency

                logger.info(
                    f"Exchanging {source_amount_needed:.2f} {source_currency} to "
                    f"{currency} to cover shortfall ({needed:.2f} {currency})"
                )

                result = self._currency_service.exchange(
                    source_currency, currency, source_amount_needed
                )

                if result:
                    logger.info(
                        f"Currency exchange successful: {source_currency} -> {currency}"
                    )
                    # Refresh balances from API
                    cash_balances_raw = self._client.get_cash_balances()
                    cash_balances = {cb.currency: cb.amount for cb in cash_balances_raw}

                    # Check if shortfall is resolved
                    if cash_balances.get(currency, 0) >= MIN_CURRENCY_RESERVE:
                        del remaining_shortfalls[currency]
                else:
                    logger.warning(
                        f"Currency exchange failed: {source_currency} -> {currency}"
                    )

        return remaining_shortfalls

    async def _step_2_position_sales(
        self, remaining_shortfalls: Dict[str, float]
    ) -> None:
        """Step 2: Sell positions to cover remaining shortfalls.

        Args:
            remaining_shortfalls: Remaining shortfalls after currency exchange
        """
        if not remaining_shortfalls:
            return

        # Get open markets
        open_markets = await get_open_markets()
        if not open_markets:
            logger.warning("No markets are open, cannot sell positions")
            return

        # Get positions with allow_sell=True
        positions = await self._position_repo.get_with_stock_info()
        sellable_positions = [
            pos
            for pos in positions
            if pos.get("allow_sell", False)
            and is_market_open(pos.get("fullExchangeName", ""))
        ]

        if not sellable_positions:
            logger.warning("No sellable positions available in open markets")
            return

        # Calculate total cash needed in EUR (convert all shortfalls to EUR)
        total_needed_eur = 0.0
        for currency, shortfall in remaining_shortfalls.items():
            try:
                rate = await self._exchange_rate_service.get_rate(currency, "EUR")
                if rate > 0:
                    total_needed_eur += shortfall / rate
                else:
                    total_needed_eur += shortfall  # Fallback: assume 1:1
            except Exception:
                total_needed_eur += shortfall  # Fallback: assume 1:1

        # Select positions to sell (simple: sell from largest positions first)
        sell_recommendations: List[Recommendation] = []
        total_sell_value = 0.0

        for pos in sorted(
            sellable_positions, key=lambda p: p.get("market_value_eur", 0), reverse=True
        ):
            if total_sell_value >= total_needed_eur * 1.1:  # 10% buffer
                break

            symbol = pos["symbol"]
            name = pos.get("name", symbol)
            quantity = pos["quantity"]
            current_price = pos.get("current_price", pos.get("avg_price", 0))
            currency = pos.get("currency", "EUR")

            # Calculate exchange rate for position currency
            rate = 1.0
            try:
                rate = await self._exchange_rate_service.get_rate(currency, "EUR")
                if rate <= 0:
                    rate = 1.0
            except Exception:
                rate = 1.0

            # Sell partial position if needed
            position_value = pos.get("market_value_eur", 0)
            sell_value_eur = min(
                position_value, (total_needed_eur - total_sell_value) * 1.1
            )
            sell_value_in_currency = sell_value_eur / rate
            sell_quantity = min(
                quantity,
                (
                    sell_value_in_currency / current_price
                    if current_price > 0
                    else quantity
                ),
            )

            if sell_quantity > 0:
                # Convert currency string to Currency enum
                try:
                    currency_enum = Currency(currency.upper())
                except (ValueError, AttributeError):
                    currency_enum = Currency.EUR  # Fallback to EUR

                recommendation = Recommendation(
                    symbol=symbol,
                    name=name,
                    side=TradeSide.SELL,
                    quantity=sell_quantity,
                    estimated_price=current_price,
                    estimated_value=sell_value_in_currency,
                    reason="Emergency rebalancing: negative cash balance",
                    currency=currency_enum,
                )
                sell_recommendations.append(recommendation)
                total_sell_value += sell_value_eur

        if sell_recommendations:
            logger.info(
                f"Executing {len(sell_recommendations)} emergency sales to cover "
                f"negative balances (bypassing cooldown and min-hold checks)"
            )

            # Execute with bypass flags
            results = await self._trade_execution_service.execute_trades(
                sell_recommendations,
                bypass_cooldown=True,
                bypass_min_hold=True,
            )

            successful = sum(1 for r in results if r.get("status") == "success")
            logger.info(
                f"Emergency sales completed: {successful}/{len(results)} successful"
            )

    async def _step_3_final_exchange(self) -> None:
        """Step 3: Final currency exchange to ensure all currencies have minimum."""
        # Refresh balances after sales
        cash_balances_raw = self._client.get_cash_balances()
        cash_balances = {cb.currency: cb.amount for cb in cash_balances_raw}

        # Check for remaining shortfalls
        shortfalls = await self.check_currency_minimums(cash_balances)

        if not shortfalls:
            logger.info("All currencies now meet minimum reserve after rebalancing")
            return

        # Try one more round of currency exchange
        await self._step_1_currency_exchange(shortfalls, cash_balances)

        # Final check
        cash_balances_raw = self._client.get_cash_balances()
        cash_balances = {cb.currency: cb.amount for cb in cash_balances_raw}
        final_shortfalls = await self.check_currency_minimums(cash_balances)

        if final_shortfalls:
            logger.error(
                f"Some currencies still below minimum after rebalancing: {final_shortfalls}"
            )
        else:
            logger.info("Negative balance rebalancing completed successfully")
