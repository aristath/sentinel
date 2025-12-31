"""Trade execution application service.

Orchestrates trade execution via Tradernet and records trades.
"""

import logging
from datetime import datetime
from typing import List, Optional

from app.core.events import SystemEvent, emit
from app.domain.models import Recommendation, Trade
from app.domain.repositories.protocols import (
    IPositionRepository,
    ISecurityRepository,
    ISettingsRepository,
    ITradeRepository,
)
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.services.settings_service import SettingsService
from app.infrastructure.external.tradernet import TradernetClient
from app.infrastructure.market_hours import is_market_open, should_check_market_hours
from app.modules.display.services.display_service import set_led4, set_text
from app.modules.scoring.domain.constants import DEFAULT_MIN_HOLD_DAYS
from app.modules.trading.services.trade_execution.trade_recorder import record_trade
from app.shared.domain.value_objects.currency import Currency
from app.shared.services import CurrencyExchangeService
from app.shared.utils import safe_parse_datetime_string

logger = logging.getLogger(__name__)


async def _calculate_commission_in_trade_currency(
    trade_value: float,
    trade_currency,
    transaction_cost_fixed: float,
    transaction_cost_percent: float,
    exchange_rate_service: ExchangeRateService,
) -> float:
    """Calculate total commission in trade currency.

    Commission structure: fixed EUR fee (converted to trade currency) + percentage of trade value.

    Args:
        trade_value: Trade value in trade currency
        trade_currency: Trade currency (Currency enum or string)
        transaction_cost_fixed: Fixed commission in EUR (default 2.0)
        transaction_cost_percent: Variable commission as fraction (default 0.002 = 0.2%)
        exchange_rate_service: Service to get exchange rates for currency conversion

    Returns:
        Total commission in trade currency
    """
    # Get currency string
    currency_str = (
        trade_currency.value
        if hasattr(trade_currency, "value")
        else str(trade_currency)
    )

    # Calculate variable commission (percentage of trade value in trade currency)
    variable_commission = trade_value * transaction_cost_percent

    # Convert fixed EUR commission to trade currency if needed
    if currency_str == "EUR":
        fixed_commission = transaction_cost_fixed
    else:
        try:
            # Use convert method which handles the rate conversion correctly
            # convert() divides by rate: amount_in_to = amount / rate
            fixed_commission = await exchange_rate_service.convert(
                transaction_cost_fixed, "EUR", currency_str
            )
            if fixed_commission <= 0:
                logger.warning(
                    f"Invalid conversion result for commission EUR->{currency_str}, using fixed EUR amount"
                )
                fixed_commission = transaction_cost_fixed
        except Exception as e:
            logger.warning(
                f"Error converting commission EUR to {currency_str}: {e}, using fixed EUR amount"
            )
            fixed_commission = transaction_cost_fixed

    total_commission = fixed_commission + variable_commission
    return total_commission


async def _check_buy_cooldown(
    trade, recently_bought: set, cooldown_days: int, bypass_cooldown: bool = False
) -> Optional[dict]:
    """Check if BUY trade is in cooldown period."""
    if bypass_cooldown:
        return None

    if trade.symbol in recently_bought:
        logger.warning(
            f"SAFETY BLOCK: {trade.symbol} in cooldown period, refusing to execute"
        )
        return {
            "symbol": trade.symbol,
            "status": "blocked",
            "error": f"Cooldown active (bought within {cooldown_days} days)",
        }
    return None


async def _handle_buy_currency(
    trade,
    currency_balances: Optional[dict],
    currency_service: Optional[CurrencyExchangeService],
    source_currency: str,
    converted_currencies: set,
    transaction_cost_fixed: float,
    transaction_cost_percent: float,
    exchange_rate_service: ExchangeRateService,
) -> Optional[dict]:
    """Handle currency validation and conversion for BUY orders."""
    trade_value = trade.quantity * trade.estimated_price
    trade_currency = trade.currency or Currency.EUR
    # Get string value for display (Currency enum -> "EUR")
    currency_str = (
        trade_currency.value
        if hasattr(trade_currency, "value")
        else str(trade_currency)
    )

    # Calculate commission in trade currency
    commission = await _calculate_commission_in_trade_currency(
        trade_value,
        trade_currency,
        transaction_cost_fixed,
        transaction_cost_percent,
        exchange_rate_service,
    )

    # Total required = trade value + commission
    required = trade_value + commission

    if currency_service and trade_currency != source_currency:
        available = currency_balances.get(trade_currency, 0) if currency_balances else 0

        # Block trade if balance is already negative
        if available < 0:
            logger.warning(
                f"Blocking BUY {trade.symbol}: negative {currency_str} balance "
                f"({available:.2f} {currency_str})"
            )
            return {
                "symbol": trade.symbol,
                "status": "blocked",
                "error": f"Negative {currency_str} balance ({available:.2f} {currency_str})",
            }

        if available < required:
            if trade_currency not in converted_currencies:
                logger.info(
                    f"Auto-converting {source_currency} to {currency_str} "
                    f"for {trade.symbol} (need {required:.2f} {currency_str}: "
                    f"{trade_value:.2f} trade + {commission:.2f} commission)"
                )
                set_text(f"CONVERTING {source_currency} TO {currency_str}...")
                set_led4(0, 255, 0)  # Green for processing

                if currency_service.ensure_balance(
                    trade_currency, required, source_currency
                ):
                    converted_currencies.add(trade_currency)
                    logger.info(f"Currency conversion successful for {currency_str}")
                    set_text("CURRENCY CONVERSION COMPLETE")
                else:
                    logger.warning(
                        f"Currency conversion failed for {trade.symbol}: "
                        f"could not convert {source_currency} to {currency_str} "
                        f"(need {required:.2f} {currency_str})"
                    )
                    return {
                        "symbol": trade.symbol,
                        "status": "skipped",
                        "error": f"Currency conversion failed ({source_currency} to {currency_str})",
                    }

    elif currency_balances is not None:
        available = currency_balances.get(trade_currency, 0)

        # Block trade if balance is already negative
        if available < 0:
            logger.warning(
                f"Blocking BUY {trade.symbol}: negative {currency_str} balance "
                f"({available:.2f} {currency_str})"
            )
            return {
                "symbol": trade.symbol,
                "status": "blocked",
                "error": f"Negative {currency_str} balance ({available:.2f} {currency_str})",
            }

        if available < required:
            logger.warning(
                f"Skipping {trade.symbol}: insufficient {currency_str} balance "
                f"(need {required:.2f} {currency_str}: {trade_value:.2f} trade + {commission:.2f} commission, "
                f"have {available:.2f})"
            )
            return {
                "symbol": trade.symbol,
                "status": "skipped",
                "error": f"Insufficient {currency_str} balance (need {required:.2f}, have {available:.2f})",
            }

    return None


async def _validate_sell_order(
    trade, position_repo, trade_repo, bypass_min_hold: bool = False
) -> Optional[dict]:
    """Validate SELL order against position and minimum hold time."""
    if not position_repo:
        return None

    position = await position_repo.get_by_symbol(trade.symbol)
    if not position:
        logger.warning(f"Skipping SELL {trade.symbol}: no position found")
        return {
            "symbol": trade.symbol,
            "status": "skipped",
            "error": "No position found for SELL order",
        }

    if trade.quantity > position.quantity:
        logger.warning(
            f"Skipping SELL {trade.symbol}: quantity {trade.quantity} "
            f"> position {position.quantity}"
        )
        return {
            "symbol": trade.symbol,
            "status": "skipped",
            "error": f"SELL quantity ({trade.quantity}) exceeds position ({position.quantity})",
        }

    # Check minimum hold time using the most recent transaction date (buy or sell)
    # Skip if bypass_min_hold is True (for emergency rebalancing)
    if bypass_min_hold:
        return None

    if trade_repo:
        try:
            last_transaction_at = await trade_repo.get_last_transaction_date(
                trade.symbol
            )
            if last_transaction_at:
                transaction_date = safe_parse_datetime_string(last_transaction_at)
                if transaction_date:
                    days_held = (datetime.now() - transaction_date).days
                    if days_held < DEFAULT_MIN_HOLD_DAYS:
                        logger.warning(
                            f"SAFETY BLOCK: {trade.symbol} last transaction {days_held} days ago "
                            f"(minimum {DEFAULT_MIN_HOLD_DAYS} days required)"
                        )
                        return {
                            "symbol": trade.symbol,
                            "status": "blocked",
                            "error": f"Last transaction {days_held} days ago (minimum {DEFAULT_MIN_HOLD_DAYS} days required)",
                        }
        except Exception as e:
            logger.error(f"Failed to check minimum hold time for {trade.symbol}: {e}")
            # On error, be conservative and block
            return {
                "symbol": trade.symbol,
                "status": "blocked",
                "error": "Minimum hold time check failed",
            }

    return None


async def _check_pending_orders(trade, client, trade_repo) -> bool:
    """
    Check if there are pending orders for this symbol.

    Checks both:
    1. Broker API for pending orders
    2. Database for very recent orders (last 5 minutes) to catch orders
       that were just placed but not yet visible in broker API

    This check is NEVER bypassed, even for emergency trades, to prevent duplicate orders.
    """
    has_pending = client.has_pending_order_for_symbol(trade.symbol)

    # Also check database for very recent orders (last 5 minutes)
    # This catches orders that were just placed but broker API hasn't updated yet
    if not has_pending:
        try:
            # Check for very recent orders (5 minutes) to catch race conditions
            # where an order was just placed but broker API hasn't updated
            # Check both BUY and SELL orders
            from datetime import timedelta

            cutoff = (datetime.now() - timedelta(hours=0.083)).isoformat()  # 5 minutes
            row = await trade_repo._db.fetchone(
                """
                SELECT 1 FROM trades
                WHERE symbol = ?
                  AND UPPER(side) = ?
                  AND executed_at >= ?
                  AND (order_id IS NULL OR order_id NOT LIKE 'RESEARCH_%')
                LIMIT 1
                """,
                (trade.symbol.upper(), trade.side.upper(), cutoff),
            )
            if row:
                has_pending = True
                logger.info(
                    f"Found very recent {trade.side} order in database for {trade.symbol} "
                    "(within last 5 minutes), blocking duplicate trade"
                )
        except Exception as e:
            logger.warning(f"Failed to check database for recent orders: {e}")

    if has_pending:
        logger.warning(
            f"SAFETY BLOCK: {trade.symbol} has pending order, refusing to execute"
        )

    return has_pending


async def _get_recently_bought_symbols(
    trade_repo, trades, cooldown_days: int
) -> Optional[set]:
    """Get recently bought symbols for cooldown check."""
    try:
        return await trade_repo.get_recently_bought_symbols(cooldown_days)
    except Exception as e:
        logger.error(f"SAFETY: Failed to get recently bought symbols: {e}")
        return None


def _create_cooldown_failed_results(trades) -> List[dict]:
    """Create failure results when cooldown check fails."""
    return [
        {
            "symbol": t.symbol,
            "status": "failed",
            "error": "Cooldown check failed",
        }
        for t in trades
        if t.side.upper() == "BUY"
    ]


async def _check_market_hours(trade, security_repo) -> Optional[dict]:
    """Check if the security's market is currently open (if required for this trade)."""
    try:
        security = await security_repo.get_by_symbol(trade.symbol)
        if not security:
            logger.warning(
                f"Security {trade.symbol} not found, cannot check market hours. Allowing trade."
            )
            return None

        exchange = getattr(security, "fullExchangeName", None)
        if not exchange:
            logger.warning(
                f"Security {trade.symbol} has no exchange set. Allowing trade."
            )
            return None

        # Check if market hours validation is required for this trade
        if not should_check_market_hours(exchange, trade.side.value):
            # Market hours check not required (e.g., BUY order on flexible hours market)
            return None

        if not is_market_open(exchange):
            logger.info(
                f"Market closed for {trade.symbol} (exchange: {exchange}). Blocking trade."
            )
            return {
                "symbol": trade.symbol,
                "status": "blocked",
                "error": f"Market closed for {exchange}",
                "exchange": exchange,
            }

        return None
    except Exception as e:
        logger.warning(f"Failed to check market hours for {trade.symbol}: {e}")
        # On error, allow trade (fail open) - better than blocking all trades
        return None


async def _validate_trade_before_execution(
    trade,
    recently_bought: set,
    cooldown_days: int,
    currency_balances: Optional[dict],
    currency_service: Optional[CurrencyExchangeService],
    source_currency: str,
    converted_currencies: set,
    position_repo,
    client,
    trade_repo,
    security_repo,
    transaction_cost_fixed: float,
    transaction_cost_percent: float,
    exchange_rate_service: ExchangeRateService,
    bypass_cooldown: bool = False,
    bypass_min_hold: bool = False,
) -> tuple[Optional[dict], int]:
    """Validate trade before execution and return blocking result if any."""
    # Check market hours first (if required for this trade)
    market_hours_result = await _check_market_hours(trade, security_repo)
    if market_hours_result:
        return market_hours_result, 0

    if trade.side.upper() == "BUY":
        cooldown_result = await _check_buy_cooldown(
            trade, recently_bought, cooldown_days, bypass_cooldown
        )
        if cooldown_result:
            return cooldown_result, 0

        currency_result = await _handle_buy_currency(
            trade,
            currency_balances,
            currency_service,
            source_currency,
            converted_currencies,
            transaction_cost_fixed,
            transaction_cost_percent,
            exchange_rate_service,
        )
        if currency_result:
            return currency_result, 1

    if trade.side.upper() == "SELL":
        sell_result = await _validate_sell_order(
            trade, position_repo, trade_repo, bypass_min_hold
        )
        if sell_result:
            return sell_result, 1

    has_pending = await _check_pending_orders(trade, client, trade_repo)
    if has_pending:
        return {
            "symbol": trade.symbol,
            "status": "blocked",
            "error": f"Pending order already exists for {trade.symbol}",
        }, 0

    return None, 0


async def _execute_and_record_trade(trade, client, service) -> Optional[dict]:
    """Execute trade and record it if successful."""
    execution_result = await _execute_single_trade(trade, client)
    if execution_result and execution_result.get("status") == "success":
        result = execution_result["result"]
        await service.record_trade(
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            price=result.price,
            order_id=result.order_id,
            currency=trade.currency,
            estimated_price=trade.estimated_price,
            source="tradernet",
        )
        return execution_result
    return execution_result


async def _process_single_trade(
    trade,
    recently_bought: set,
    cooldown_days: int,
    currency_balances: Optional[dict],
    currency_service: Optional[CurrencyExchangeService],
    source_currency: str,
    converted_currencies: set,
    position_repo,
    client,
    trade_repo,
    security_repo,
    service,
    transaction_cost_fixed: float,
    transaction_cost_percent: float,
    exchange_rate_service: ExchangeRateService,
    bypass_cooldown: bool = False,
    bypass_min_hold: bool = False,
) -> tuple[Optional[dict], int]:
    """Process a single trade and return result and skipped count."""
    try:
        validation_result, skipped = await _validate_trade_before_execution(
            trade,
            recently_bought,
            cooldown_days,
            currency_balances,
            currency_service,
            source_currency,
            converted_currencies,
            position_repo,
            client,
            trade_repo,
            security_repo,
            transaction_cost_fixed,
            transaction_cost_percent,
            exchange_rate_service,
            bypass_cooldown,
            bypass_min_hold,
        )
        if validation_result:
            return validation_result, skipped

        execution_result = await _execute_and_record_trade(trade, client, service)
        return execution_result, 0

    except Exception as e:
        logger.error(f"Failed to execute trade for {trade.symbol}: {e}")
        error_msg = "ORDER PLACEMENT FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_text(error_msg)
        set_led4(255, 0, 0)  # Red for error
        return {
            "symbol": trade.symbol,
            "status": "error",
            "error": str(e),
        }, 0


async def _process_trades(
    trades: List[Recommendation],
    recently_bought: set,
    cooldown_days: int,
    currency_balances: Optional[dict],
    currency_service: Optional[CurrencyExchangeService],
    source_currency: str,
    converted_currencies: set,
    position_repo,
    client,
    trade_repo,
    security_repo,
    service,
    transaction_cost_fixed: float,
    transaction_cost_percent: float,
    exchange_rate_service: ExchangeRateService,
    bypass_cooldown: bool = False,
    bypass_min_hold: bool = False,
) -> tuple[List[dict], int]:
    """Process all trades and return results and skipped count."""
    results = []
    skipped_count = 0

    for trade in trades:
        result, skipped = await _process_single_trade(
            trade,
            recently_bought,
            cooldown_days,
            currency_balances,
            currency_service,
            source_currency,
            converted_currencies,
            position_repo,
            client,
            trade_repo,
            security_repo,
            service,
            transaction_cost_fixed,
            transaction_cost_percent,
            exchange_rate_service,
            bypass_cooldown,
            bypass_min_hold,
        )
        if result:
            results.append(result)
        skipped_count += skipped

    return results, skipped_count


def _handle_skipped_trades_warning(skipped_count: int) -> None:
    """Handle warning for skipped trades."""
    if skipped_count > 0:
        logger.warning(
            f"Skipped {skipped_count} trades due to insufficient currency balance"
        )
        if skipped_count >= 2:
            error_msg = "INSUFFICIENT FOREIGN CURRENCY BALANCE"
            emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
            set_text(error_msg)
        set_led4(255, 0, 0)  # Red for error


async def _execute_single_trade(trade, client) -> Optional[dict]:
    """Execute a single trade and return result."""
    side_text = "BUYING" if trade.side.upper() == "BUY" else "SELLING"
    value = int(trade.quantity * trade.estimated_price)
    symbol_short = trade.symbol.split(".")[0]
    set_text(f"{side_text} {symbol_short} €{value}")
    set_led4(0, 255, 0)  # Green for processing

    result = client.place_order(
        symbol=trade.symbol,
        side=trade.side.value,
        quantity=trade.quantity,
    )

    if result:
        return {
            "symbol": trade.symbol,
            "status": "success",
            "order_id": result.order_id,
            "side": trade.side,
            "price": result.price,
            "result": result,
        }
    else:
        error_msg = "ORDER PLACEMENT FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_text(error_msg)
        set_led4(255, 0, 0)  # Red for error
        return {
            "symbol": trade.symbol,
            "status": "failed",
            "error": "Order placement returned None",
        }


class TradeExecutionService:
    """Application service for trade execution."""

    def __init__(
        self,
        trade_repo: ITradeRepository,
        position_repo: IPositionRepository,
        security_repo: ISecurityRepository,
        tradernet_client: TradernetClient,
        currency_exchange_service: CurrencyExchangeService,
        exchange_rate_service: ExchangeRateService,
        settings_repo: Optional[ISettingsRepository] = None,
    ):
        self._trade_repo = trade_repo
        self._position_repo = position_repo
        self._stock_repo = security_repo
        self._tradernet_client = tradernet_client
        self._currency_exchange_service = currency_exchange_service
        self._exchange_rate_service = exchange_rate_service
        self._settings_repo = settings_repo

    async def record_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_id: Optional[str] = None,
        currency: Optional[str] = None,
        estimated_price: Optional[float] = None,
        source: str = "tradernet",
    ) -> Optional[Trade]:
        """
        Record a trade in the database.

        Handles duplicate order_id checking and creates Trade record.

        Args:
            symbol: Security symbol
            side: Trade side (BUY or SELL)
            quantity: Trade quantity
            price: Execution price (use estimated_price if price <= 0)
            order_id: Broker order ID (optional)
            currency: Trade currency (optional)
            estimated_price: Estimated price to use if price <= 0 (optional)
            source: Trade source (default: "tradernet")

        Returns:
            Trade object if recorded successfully, None if duplicate or error
        """
        return await record_trade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            trade_repo=self._trade_repo,
            position_repo=self._position_repo,
            exchange_rate_service=self._exchange_rate_service,
            order_id=order_id,
            currency=currency,
            estimated_price=estimated_price,
            source=source,
        )

    async def execute_trades(
        self,
        trades: List[Recommendation],
        currency_balances: Optional[dict[str, float]] = None,
        auto_convert_currency: bool = False,
        source_currency: str = Currency.EUR,
        bypass_cooldown: bool = False,
        bypass_min_hold: bool = False,
        bypass_frequency_limit: bool = False,
    ) -> List[dict]:
        """
        Execute a list of trade recommendations via Tradernet.

        Args:
            trades: List of trade recommendations to execute
            currency_balances: Per-currency cash balances for validation (optional)
            auto_convert_currency: If True, automatically convert currency before buying
            source_currency: Currency to convert from when auto_convert is enabled (default: EUR)
            bypass_cooldown: If True, bypass buy cooldown checks (for emergency rebalancing)
            bypass_min_hold: If True, bypass minimum hold time checks (for emergency rebalancing)
            bypass_frequency_limit: If True, bypass trade frequency limit checks (for emergency rebalancing)

        Returns:
            List of execution results with status for each trade
        """
        # Check trade frequency limits (unless bypassed for emergency rebalancing)
        if self._settings_repo and not bypass_frequency_limit:
            from app.modules.trading.services.trade_frequency_service import (
                TradeFrequencyService,
            )

            frequency_service = TradeFrequencyService(
                self._trade_repo, self._settings_repo
            )
            can_trade, reason = await frequency_service.can_execute_trade()
            if not can_trade:
                logger.warning(f"Trade blocked by frequency limit: {reason}")
                error_msg = "TRADE FREQUENCY LIMIT"
                emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
                set_text(error_msg)
                set_led4(255, 0, 0)  # Red for error
                # Return blocked result for all trades
                return [
                    {
                        "symbol": trade.symbol,
                        "status": "blocked",
                        "error": reason,
                    }
                    for trade in trades
                ]

        client = self._tradernet_client

        if not client.is_connected:
            if not client.connect():
                error_msg = "TRADE EXECUTION FAILED"
                emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
                set_text(error_msg)
                set_led4(255, 0, 0)  # Red for error
                raise ConnectionError("Failed to connect to Tradernet")

        # Use currency exchange service if auto-convert is enabled
        currency_service = (
            self._currency_exchange_service if auto_convert_currency else None
        )

        return await self._execute_trades_internal(
            trades,
            client,
            currency_balances=currency_balances,
            currency_service=currency_service,
            source_currency=source_currency,
            bypass_cooldown=bypass_cooldown,
            bypass_min_hold=bypass_min_hold,
        )

    async def _execute_trades_internal(
        self,
        trades: List[Recommendation],
        client,
        currency_balances: Optional[dict[str, float]] = None,
        currency_service: Optional[CurrencyExchangeService] = None,
        source_currency: str = Currency.EUR,
        bypass_cooldown: bool = False,
        bypass_min_hold: bool = False,
    ) -> List[dict]:
        """Internal method to execute trades."""
        results: list[dict] = []
        skipped_count = 0
        converted_currencies: set[str] = (
            set()
        )  # Track which currencies we've converted to

        # Get transaction cost settings
        if self._settings_repo:
            settings_service = SettingsService(self._settings_repo)
            settings = await settings_service.get_settings()
            transaction_cost_fixed = settings.transaction_cost_fixed
            transaction_cost_percent = settings.transaction_cost_percent
        else:
            # Use defaults if settings repository not available
            transaction_cost_fixed = 2.0
            transaction_cost_percent = 0.002
            logger.warning(
                "Settings repository not available, using default transaction costs "
                f"(fixed={transaction_cost_fixed}, percent={transaction_cost_percent})"
            )

        from app.domain.constants import BUY_COOLDOWN_DAYS

        recently_bought = await _get_recently_bought_symbols(
            self._trade_repo, trades, BUY_COOLDOWN_DAYS
        )
        if recently_bought is None:
            return _create_cooldown_failed_results(trades)

        results, skipped_count = await _process_trades(
            trades,
            recently_bought,
            BUY_COOLDOWN_DAYS,
            currency_balances,
            currency_service,
            source_currency,
            converted_currencies,
            self._position_repo,
            client,
            self._trade_repo,
            self._stock_repo,
            self,
            transaction_cost_fixed,
            transaction_cost_percent,
            self._exchange_rate_service,
            bypass_cooldown,
            bypass_min_hold,
        )

        _handle_skipped_trades_warning(skipped_count)

        return results
