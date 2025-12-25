"""Cash-based rebalance job with drip execution strategy.

Executes ONE trade per cycle (15 minutes) with fresh data before each decision.
Priority: SELL before BUY.
"""

import logging
from typing import TYPE_CHECKING

from app.config import settings
from app.services.tradernet import get_tradernet_client
from app.application.services.trade_safety_service import TradeSafetyService
from app.infrastructure.locking import file_lock
from app.infrastructure.events import emit, SystemEvent
from app.infrastructure.hardware.led_display import set_activity
from app.infrastructure.database.manager import get_db_manager
from app.infrastructure.cache import cache
from app.infrastructure.recommendation_cache import get_recommendation_cache
from app.repositories import (
    StockRepository,
    PositionRepository,
    TradeRepository,
    AllocationRepository,
    SettingsRepository,
    RecommendationRepository,
)
from app.domain.scoring import (
    calculate_all_sell_scores,
    calculate_post_transaction_score,
    PortfolioContext,
    TechnicalData,
)
from app.infrastructure.daily_pnl import get_daily_pnl_tracker

if TYPE_CHECKING:
    from app.domain.models import Recommendation

logger = logging.getLogger(__name__)


async def check_and_rebalance():
    """
    Check for trade opportunities and execute ONE trade if available.

    Priority: SELL before BUY
    Limit: One trade per 15-minute cycle

    This "drip" strategy ensures:
    - Fresh data before each decision
    - Time for broker to settle orders
    - Recalculated recommendations each cycle
    """
    async with file_lock("rebalance", timeout=600.0):
        await _check_and_rebalance_internal()


async def _check_and_rebalance_internal():
    """Internal rebalance implementation with drip execution."""
    from app.jobs.daily_sync import sync_portfolio
    from app.jobs.sync_trades import sync_trades
    from app.services import yahoo
    from app.services.tradernet import get_exchange_rate
    from app.application.services.trade_execution_service import TradeExecutionService
    from app.domain.models import Recommendation
    from app.domain.value_objects.trade_side import TradeSide
    from app.domain.constants import BUY_COOLDOWN_DAYS

    logger.info("Starting trade cycle check...")

    emit(SystemEvent.REBALANCE_START)
    set_activity("CHECKING TRADE OPPORTUNITIES...", duration=300.0)

    try:
        # Step 0: Sync trades from Tradernet for accurate cooldown calculations
        logger.info("Step 0: Syncing trades from Tradernet...")
        await sync_trades()

        # Step 1: Sync portfolio for fresh data
        logger.info("Step 1: Syncing portfolio for fresh data...")
        await sync_portfolio()

        # GUARDRAIL: Check daily P&L circuit breaker
        pnl_tracker = get_daily_pnl_tracker()
        pnl_status = await pnl_tracker.get_trading_status()
        logger.info(f"Daily P&L status: {pnl_status['pnl_display']} ({pnl_status['status']})")

        if pnl_status["status"] == "halted":
            logger.warning(f"Trading halted: {pnl_status['reason']}")
            emit(SystemEvent.ERROR_OCCURRED, message="TRADING HALTED - SEVERE DRAWDOWN")
            emit(SystemEvent.REBALANCE_COMPLETE)
            return

        # Get configurable threshold from database
        from app.domain.services.settings_service import SettingsService
        settings_service = SettingsService(SettingsRepository())
        settings = await settings_service.get_settings()
        min_trade_size = settings.min_trade_size

        # Connect to broker
        client = get_tradernet_client()
        if not client.is_connected:
            if not client.connect():
                logger.warning("Cannot connect to Tradernet, skipping cycle")
                emit(SystemEvent.ERROR_OCCURRED, message="BROKER CONNECTION FAILED")
                return

        cash_balance = client.get_total_cash_eur()
        logger.info(f"Cash balance: €{cash_balance:.2f}, threshold: €{min_trade_size:.2f}")

        # Initialize repositories
        stock_repo = StockRepository()
        position_repo = PositionRepository()
        trade_repo = TradeRepository()
        allocation_repo = AllocationRepository()
        db_manager = get_db_manager()

        # Step 2: Build portfolio context
        logger.info("Step 2: Building portfolio context...")
        set_activity("BUILDING PORTFOLIO CONTEXT...", duration=30.0)

        positions = await position_repo.get_all()
        stocks = await stock_repo.get_all_active()
        allocations = await allocation_repo.get_all()
        total_value = await position_repo.get_total_value()

        # Generate portfolio hash for recommendation matching
        from app.domain.portfolio_hash import generate_portfolio_hash
        position_hash_dicts = [{"symbol": p.symbol, "quantity": p.quantity} for p in positions]
        portfolio_hash = generate_portfolio_hash(position_hash_dicts)

        # Build portfolio context for scoring
        # get_all() returns Dict[str, float] with keys like "geography:name"
        geo_weights = {}
        industry_weights = {}
        for key, target_pct in allocations.items():
            parts = key.split(":", 1)
            if len(parts) == 2:
                alloc_type, name = parts
                if alloc_type == "geography":
                    geo_weights[name] = target_pct
                elif alloc_type == "industry":
                    industry_weights[name] = target_pct

        position_map = {p.symbol: p.market_value_eur or 0 for p in positions}
        stock_geographies = {s.symbol: s.geography for s in stocks}
        stock_industries = {s.symbol: s.industry for s in stocks if s.industry}
        stock_scores = {}

        # Get existing scores
        score_rows = await db_manager.state.fetchall(
            "SELECT symbol, quality_score FROM scores"
        )
        for row in score_rows:
            if row["quality_score"]:
                stock_scores[row["symbol"]] = row["quality_score"]

        portfolio_context = PortfolioContext(
            geo_weights=geo_weights,
            industry_weights=industry_weights,
            positions=position_map,
            total_value=total_value if total_value > 0 else 1.0,
            stock_geographies=stock_geographies,
            stock_industries=stock_industries,
            stock_scores=stock_scores,
        )

        # Step 3: Check for SELL recommendation (priority)
        logger.info("Step 3: Checking for SELL recommendations...")
        set_activity("PROCESSING SELL RECOMMENDATIONS...", duration=30.0)

        # GUARDRAIL: Check if sells are allowed (blocked during drawdowns)
        if not pnl_status["can_sell"]:
            logger.info(f"Sells blocked by P&L guardrail: {pnl_status['reason']}")
            sell_trade = None
        else:
            sell_trade = await _get_best_sell_trade(
                positions, stocks, trade_repo, portfolio_context, db_manager
            )

        if sell_trade:
            # Additional safety check: verify no recent sell order in database
            has_recent = await trade_repo.has_recent_sell_order(sell_trade.symbol, hours=2)
            if has_recent:
                logger.warning(
                    f"Skipping SELL {sell_trade.symbol}: recent sell order found in database "
                    f"(within last 2 hours)"
                )
                emit(SystemEvent.REBALANCE_COMPLETE)
                await _refresh_recommendation_cache()
                return

            logger.info(
                f"Executing SELL: {sell_trade.quantity} {sell_trade.symbol} "
                f"@ €{sell_trade.estimated_price:.2f} = €{sell_trade.estimated_value:.2f} "
                f"({sell_trade.reason})"
            )

            emit(SystemEvent.SYNC_START)

            trade_execution = TradeExecutionService(trade_repo, position_repo)
            results = await trade_execution.execute_trades([sell_trade])

            if results and results[0]["status"] == "success":
                logger.info(f"SELL executed successfully: {sell_trade.symbol}")
                emit(SystemEvent.TRADE_EXECUTED, is_buy=False)

                # Invalidate portfolio-hash-based caches (old portfolio is now stale)
                rec_cache = get_recommendation_cache()
                await rec_cache.invalidate_portfolio_hash(portfolio_hash)

                # Mark matching stored recommendations as executed
                recommendation_repo = RecommendationRepository()
                matching_recs = await recommendation_repo.find_matching_for_execution(
                    symbol=sell_trade.symbol,
                    side=TradeSide.SELL,
                    portfolio_hash=portfolio_hash,
                )
                for rec in matching_recs:
                    await recommendation_repo.mark_executed(rec["uuid"])
                    logger.info(f"Marked recommendation {rec['uuid']} as executed")
            else:
                error = results[0].get("error", "Unknown error") if results else "No result"
                logger.error(f"SELL failed for {sell_trade.symbol}: {error}")
                emit(SystemEvent.ERROR_OCCURRED, message="SELL ORDER FAILED")

            emit(SystemEvent.SYNC_COMPLETE)
            await sync_portfolio()
            await _refresh_recommendation_cache()
            return

        # Step 4: Check for BUY recommendation
        logger.info("Step 4: Checking for BUY recommendations...")

        # GUARDRAIL: Check if buys are allowed (blocked during severe crashes)
        if not pnl_status["can_buy"]:
            logger.warning(f"Buys blocked by P&L guardrail: {pnl_status['reason']}")
            emit(SystemEvent.REBALANCE_COMPLETE)
            return

        if cash_balance < min_trade_size:
            logger.info(
                f"Cash €{cash_balance:.2f} below threshold €{min_trade_size:.2f}, "
                "no buy possible"
            )
            emit(SystemEvent.REBALANCE_COMPLETE)
            return

        currency_balances = {
            cb.currency: cb.amount
            for cb in client.get_cash_balances()
        }
        logger.info(f"Currency balances: {currency_balances}")

        # Deduct pending order amounts from available balances
        pending_totals = client.get_pending_order_totals()
        if pending_totals:
            logger.info(f"Pending order totals by currency: {pending_totals}")
            for currency, pending_amount in pending_totals.items():
                if currency in currency_balances:
                    currency_balances[currency] = max(0, currency_balances[currency] - pending_amount)
                    logger.info(
                        f"Adjusted {currency} balance: {currency_balances[currency]:.2f} "
                        f"(pending: {pending_amount:.2f})"
                    )

            # Check if adjusted total is still above threshold
            adjusted_cash = sum(currency_balances.values())
            if adjusted_cash < min_trade_size:
                logger.info(
                    f"Adjusted cash €{adjusted_cash:.2f} below threshold "
                    f"after pending orders, skipping"
                )
                emit(SystemEvent.REBALANCE_COMPLETE)
                return

        # Get recently bought symbols for cooldown
        recently_bought = await trade_repo.get_recently_bought_symbols(BUY_COOLDOWN_DAYS)

        # Get buy recommendations
        set_activity("PROCESSING BUY RECOMMENDATIONS...", duration=30.0)
        buy_trades = await _get_buy_trades(
            stocks, positions, portfolio_context, recently_bought,
            min_trade_size, db_manager
        )

        if buy_trades:
            emit(SystemEvent.SYNC_START)
            executed = False
            trade_execution = TradeExecutionService(trade_repo, position_repo)

            for trade in buy_trades:
                logger.info(
                    f"Trying BUY: {trade.quantity} {trade.symbol} "
                    f"@ €{trade.estimated_price:.2f} = €{trade.estimated_value:.2f} "
                    f"({trade.reason})"
                )

                results = await trade_execution.execute_trades(
                    [trade],
                    currency_balances=currency_balances,
                    auto_convert_currency=True,
                    source_currency="EUR"
                )

                if results and results[0]["status"] == "success":
                    logger.info(f"BUY executed successfully: {trade.symbol}")
                    emit(SystemEvent.TRADE_EXECUTED, is_buy=True)

                    # Invalidate portfolio-hash-based caches (old portfolio is now stale)
                    rec_cache = get_recommendation_cache()
                    await rec_cache.invalidate_portfolio_hash(portfolio_hash)

                    # Mark matching stored recommendations as executed
                    recommendation_repo = RecommendationRepository()
                    matching_recs = await recommendation_repo.find_matching_for_execution(
                        symbol=trade.symbol,
                        side=TradeSide.BUY,
                        portfolio_hash=portfolio_hash,
                    )
                    for rec in matching_recs:
                        await recommendation_repo.mark_executed(rec["uuid"])
                        logger.info(f"Marked recommendation {rec['uuid']} as executed")

                    executed = True
                    break
                elif results and results[0]["status"] == "skipped":
                    reason = results[0].get("error", "unknown")
                    logger.info(f"Skipped {trade.symbol}: {reason}, trying next...")
                    continue
                else:
                    error = results[0].get("error", "Unknown error") if results else "No result"
                    logger.error(f"BUY failed for {trade.symbol}: {error}")
                    emit(SystemEvent.ERROR_OCCURRED, message="BUY ORDER FAILED")
                    break

            if not executed:
                logger.info("No executable trades found (all skipped or failed)")

            emit(SystemEvent.SYNC_COMPLETE)
            await sync_portfolio()
            await _refresh_recommendation_cache()
            return

        logger.info("No trades recommended this cycle")

        emit(SystemEvent.REBALANCE_COMPLETE)

        # Refresh recommendation cache for LED ticker
        await _refresh_recommendation_cache()

        set_activity("REBALANCE CHECK COMPLETE", duration=5.0)

    except Exception as e:
        logger.error(f"Trade cycle error: {e}", exc_info=True)
        emit(SystemEvent.ERROR_OCCURRED, message="TRADE CYCLE ERROR")


async def _get_best_sell_trade(
    positions, stocks, trade_repo, portfolio_context, db_manager
) -> "Recommendation | None":
    """Calculate and return the best sell trade, if any."""
    from app.domain.models import Recommendation
    from app.domain.value_objects.trade_side import TradeSide
    from app.domain.scoring import TechnicalData, calculate_all_sell_scores
    import numpy as np
    import pandas as pd
    import empyrical
    import pandas_ta as ta

    if not positions:
        return None

    # Get stock info by symbol for lookup
    stocks_by_symbol = {s.symbol: s for s in stocks}

    # Build position dicts for sell scoring
    position_dicts = []
    for pos in positions:
        stock = stocks_by_symbol.get(pos.symbol)
        if not stock:
            continue

        # Get trade dates for position
        first_buy = await trade_repo.get_first_buy_date(pos.symbol)
        last_sell = await trade_repo.get_last_sell_date(pos.symbol)

        position_dicts.append({
            "symbol": pos.symbol,
            "name": stock.name,
            "quantity": pos.quantity,
            "avg_price": pos.avg_price,
            "current_price": pos.current_price,
            "market_value_eur": pos.market_value_eur,
            "currency": pos.currency,
            "geography": stock.geography,
            "industry": stock.industry,
            "allow_sell": stock.allow_sell,
            "first_bought_at": first_buy,
            "last_sold_at": last_sell,
        })

    if not position_dicts:
        return None

    # Get technical data for instability scoring
    technical_data = {}
    for pos in position_dicts:
        symbol = pos["symbol"]
        try:
            history_db = await db_manager.history(symbol)
            rows = await history_db.fetchall(
                """
                SELECT date, close_price FROM daily_prices
                ORDER BY date DESC LIMIT 400
                """,
            )

            if len(rows) < 60:
                technical_data[symbol] = TechnicalData(
                    current_volatility=0.20,
                    historical_volatility=0.20,
                    distance_from_ma_200=0.0
                )
                continue

            closes = np.array([row["close_price"] for row in reversed(rows)])
            closes_series = pd.Series(closes)

            # Current volatility (last 60 days)
            if len(closes) >= 60:
                recent_returns = np.diff(closes[-60:]) / closes[-60:-1]
                current_vol = float(empyrical.annual_volatility(recent_returns))
                if not np.isfinite(current_vol) or current_vol < 0:
                    current_vol = 0.20
            else:
                current_vol = 0.20

            # Historical volatility
            returns = np.diff(closes) / closes[:-1]
            historical_vol = float(empyrical.annual_volatility(returns))
            if not np.isfinite(historical_vol) or historical_vol < 0:
                historical_vol = 0.20

            # Distance from 200-day EMA
            if len(closes) >= 200:
                ema_200 = ta.ema(closes_series, length=200)
                if ema_200 is not None and len(ema_200) > 0 and not pd.isna(ema_200.iloc[-1]):
                    ema_value = float(ema_200.iloc[-1])
                else:
                    ema_value = float(np.mean(closes[-200:]))
                current_price = float(closes[-1])
                distance = (current_price - ema_value) / ema_value if ema_value > 0 else 0.0
            else:
                distance = 0.0

            technical_data[symbol] = TechnicalData(
                current_volatility=current_vol,
                historical_volatility=historical_vol,
                distance_from_ma_200=distance
            )

        except Exception as e:
            logger.warning(f"Error getting technical data for {symbol}: {e}")
            technical_data[symbol] = TechnicalData(
                current_volatility=0.20,
                historical_volatility=0.20,
                distance_from_ma_200=0.0
            )

    # Calculate sell scores
    total_value = portfolio_context.total_value
    if total_value <= 0:
        total_value = 1.0  # Prevent division by zero
    
    geo_allocations = {
        geo: sum(pos["market_value_eur"] or 0 for pos in position_dicts if pos.get("geography") == geo) / total_value
        for geo in set(pos.get("geography") for pos in position_dicts if pos.get("geography"))
    }
    ind_allocations = {
        ind: sum(pos["market_value_eur"] or 0 for pos in position_dicts if pos.get("industry") == ind) / total_value
        for ind in set(pos.get("industry") for pos in position_dicts if pos.get("industry"))
    }

    # Get sell settings
    from app.domain.services.settings_service import SettingsService
    from app.domain.value_objects.settings import TradingSettings
    settings_service = SettingsService(SettingsRepository())
    settings = await settings_service.get_settings()
    trading_settings = TradingSettings.from_settings(settings)
    sell_settings = {
        "min_hold_days": trading_settings.min_hold_days,
        "sell_cooldown_days": trading_settings.sell_cooldown_days,
        "max_loss_threshold": trading_settings.max_loss_threshold,
        "target_annual_return": trading_settings.target_annual_return,
    }

    sell_scores = await calculate_all_sell_scores(
        positions=position_dicts,
        total_portfolio_value=total_value,
        geo_allocations=geo_allocations,
        ind_allocations=ind_allocations,
        technical_data=technical_data,
        settings=sell_settings,
    )

    # Get best eligible sell
    eligible_sells = [s for s in sell_scores if s.eligible]
    if not eligible_sells:
        return None

    best_sell = eligible_sells[0]

    # Build trade recommendation
    pos = next((p for p in position_dicts if p["symbol"] == best_sell.symbol), None)
    if not pos:
        return None

    # Build reason string
    reason_parts = []
    if best_sell.profit_pct > 0.30:
        reason_parts.append(f"profit {best_sell.profit_pct*100:.1f}%")
    elif best_sell.profit_pct < 0:
        reason_parts.append(f"loss {best_sell.profit_pct*100:.1f}%")
    if best_sell.underperformance_score >= 0.7:
        reason_parts.append("underperforming")
    if best_sell.time_held_score >= 0.8:
        reason_parts.append(f"held {best_sell.days_held} days")
    if best_sell.portfolio_balance_score >= 0.7:
        reason_parts.append("overweight")
    reason_parts.append(f"sell score: {best_sell.total_score:.2f}")
    reason = ", ".join(reason_parts) if reason_parts else "eligible for sell"

    from app.domain.value_objects.currency import Currency
    from app.domain.value_objects.recommendation_status import RecommendationStatus
    
    currency_str = pos.get("currency", "EUR")
    currency_enum = Currency.from_string(currency_str) if isinstance(currency_str, str) else currency_str
    stock = next((s for s in stocks if s.get("symbol") == best_sell.symbol), None)
    
    return Recommendation(
        symbol=best_sell.symbol,
        name=pos.get("name", best_sell.symbol),
        side=TradeSide.SELL,
        quantity=best_sell.suggested_sell_quantity,
        estimated_price=round(pos.get("current_price") or pos.get("avg_price", 0), 2),
        estimated_value=round(best_sell.suggested_sell_value, 2),
        reason=reason,
        geography=stock.get("geography", "") if stock else "",
        currency=currency_enum,
        status=RecommendationStatus.PENDING,
    )


async def _get_buy_trades(
    stocks, positions, portfolio_context, recently_bought, min_trade_size, db_manager
) -> "list[Recommendation]":
    """Calculate and return buy trades."""
    from app.domain.models import Recommendation
    from app.services import yahoo
    from app.services.tradernet import get_exchange_rate
    from app.domain.value_objects.trade_side import TradeSide
    from app.domain.scoring import (
        calculate_portfolio_score,
        calculate_post_transaction_score,
    )

    candidates = []

    for stock in stocks:
        symbol = stock.symbol

        # Skip if allow_buy is disabled
        if not stock.allow_buy:
            continue

        # Skip if in cooldown
        if symbol in recently_bought:
            continue

        # Get current price
        price = yahoo.get_current_price(symbol, stock.yahoo_symbol)
        if not price or price <= 0:
            continue

        # Get stock scores from database
        score_row = await db_manager.state.fetchone(
            "SELECT * FROM scores WHERE symbol = ?",
            (symbol,)
        )

        if not score_row:
            continue

        quality_score = score_row["quality_score"] or 0.5
        opportunity_score = score_row["opportunity_score"] or 0.5
        analyst_score = score_row["analyst_score"] or 0.5
        total_score = score_row["total_score"] or 0.5

        if total_score < settings.min_stock_score:
            continue

        # Determine currency and exchange rate
        currency = stock.currency or "EUR"
        exchange_rate = 1.0
        if currency != "EUR":
            exchange_rate = get_exchange_rate(currency, "EUR")
            if exchange_rate <= 0:
                exchange_rate = 1.0

        # Get Sortino ratio for risk-adjusted position sizing (PyFolio enhancement)
        sortino_ratio = None
        try:
            from datetime import datetime, timedelta
            from app.domain.analytics import get_position_risk_metrics
            
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            risk_metrics = await get_position_risk_metrics(symbol, start_date, end_date)
            sortino_ratio = risk_metrics.get("sortino_ratio")
        except Exception as e:
            logger.debug(f"Could not get Sortino ratio for {symbol}: {e}")
        
        # Calculate risk-adjusted trade size
        risk_adjusted_size = min_trade_size
        if sortino_ratio is not None:
            if sortino_ratio > 2.0:
                risk_adjusted_size = min_trade_size * 1.15
            elif sortino_ratio > 1.5:
                risk_adjusted_size = min_trade_size * 1.05
            elif sortino_ratio < 0.5:
                risk_adjusted_size = min_trade_size * 0.8
            elif sortino_ratio < 1.0:
                risk_adjusted_size = min_trade_size * 0.9
        
        # Calculate trade quantity
        min_lot = stock.min_lot or 1
        lot_cost_native = min_lot * price
        lot_cost_eur = lot_cost_native / exchange_rate

        if lot_cost_eur > risk_adjusted_size:
            quantity = min_lot
            trade_value_native = lot_cost_native
        else:
            base_trade_amount_native = risk_adjusted_size * exchange_rate
            num_lots = int(base_trade_amount_native / lot_cost_native)
            quantity = num_lots * min_lot
            trade_value_native = quantity * price

        trade_value_eur = trade_value_native / exchange_rate

        # Calculate post-transaction portfolio score
        dividend_yield = 0
        if score_row.get("history_years"):
            # We could fetch dividend data, but for now use stored cagr as proxy
            pass

        new_score, score_change = await calculate_post_transaction_score(
            symbol=symbol,
            geography=stock.geography,
            industry=stock.industry,
            proposed_value=trade_value_eur,
            stock_quality=quality_score,
            stock_dividend=dividend_yield,
            portfolio_context=portfolio_context,
        )

        # Skip if worsens portfolio balance significantly
        if score_change < -1.0:
            continue

        # Calculate final priority
        base_score = (
            quality_score * 0.35 +
            opportunity_score * 0.35 +
            analyst_score * 0.05  # Reduced from 0.15 - tiebreaker only
        )
        normalized_score_change = max(0, min(1, (score_change + 5) / 10))
        final_score = base_score * 0.75 + normalized_score_change * 0.25  # Increased portfolio impact weight

        # Apply priority multiplier
        final_score *= stock.priority_multiplier or 1.0

        # Build reason
        reason_parts = []
        if quality_score >= 0.7:
            reason_parts.append("high quality")
        if opportunity_score >= 0.7:
            reason_parts.append("buy opportunity")
        if score_change > 0.5:
            reason_parts.append(f"↑{score_change:.1f} portfolio")
        if stock.priority_multiplier and stock.priority_multiplier != 1.0:
            reason_parts.append(f"{stock.priority_multiplier:.1f}x mult")
        reason = ", ".join(reason_parts) if reason_parts else "good score"

        candidates.append({
            "symbol": symbol,
            "name": stock.name,
            "quantity": quantity,
            "price": price,
            "trade_value_eur": trade_value_eur,
            "final_score": final_score,
            "reason": reason,
            "currency": currency,
        })

    # Sort by score
    candidates.sort(key=lambda x: x["final_score"], reverse=True)

    # Build trade recommendations
    from app.domain.value_objects.currency import Currency
    from app.domain.value_objects.recommendation_status import RecommendationStatus
    
    trades = []
    for c in candidates[:5]:  # Top 5 candidates
        currency_str = c.get("currency", "EUR")
        currency_enum = Currency.from_string(currency_str) if isinstance(currency_str, str) else currency_str
        stock = next((s for s in stocks if s.symbol == c["symbol"]), None)
        
        trades.append(Recommendation(
            symbol=c["symbol"],
            name=c["name"],
            side=TradeSide.BUY,
            quantity=c["quantity"],
            estimated_price=round(c["price"], 2),
            estimated_value=round(c["trade_value_eur"], 2),
            reason=c["reason"],
            geography=stock.geography if stock else "",
            currency=currency_enum,
            status=RecommendationStatus.PENDING,
        ))

    return trades


async def _refresh_recommendation_cache():
    """Refresh the recommendation cache for the LED ticker display."""
    from app.application.services.rebalancing_service import RebalancingService

    try:
        # Create settings_repo once and reuse
        settings_repo = SettingsRepository()
        rebalancing_service = RebalancingService(settings_repo=settings_repo)

        # Get recommendation depth setting
        depth = await settings_repo.get_int("recommendation_depth", 1)

        # Get multi-step recommendations if depth > 1
        if depth > 1:
            # Use diversification strategy by default for cache refresh
            strategy = "diversification"
            multi_step_steps = await rebalancing_service.get_multi_step_recommendations(depth=depth, strategy_type=strategy)
            if multi_step_steps:
                multi_step_data = {
                    "strategy": strategy,
                    "depth": depth,
                    "steps": [
                        {
                            "step": step.step,
                            "side": step.side,
                            "symbol": step.symbol,
                            "name": step.name,
                            "quantity": step.quantity,
                            "estimated_price": step.estimated_price,
                            "estimated_value": step.estimated_value,
                            "currency": step.currency,
                            "reason": step.reason,
                            "portfolio_score_before": step.portfolio_score_before,
                            "portfolio_score_after": step.portfolio_score_after,
                            "score_change": step.score_change,
                            "available_cash_before": step.available_cash_before,
                            "available_cash_after": step.available_cash_after,
                        }
                        for step in multi_step_steps
                    ],
                    "total_score_improvement": sum(step.score_change for step in multi_step_steps),
                    "final_available_cash": multi_step_steps[-1].available_cash_after if multi_step_steps else 0.0,
                }
                default_cache_key = f"multi_step_recommendations:{strategy}:default"
                cache.set(default_cache_key, multi_step_data, ttl_seconds=900)
                cache.set(f"multi_step_recommendations:{strategy}:{depth}", multi_step_data, ttl_seconds=900)
                logger.info(f"Multi-step recommendation cache refreshed: {len(multi_step_steps)} steps")
        else:
            # Clear multi-step cache if depth is 1
            cache.invalidate("multi_step_recommendations:diversification:default")

        # Always cache single recommendations (for fallback and depth=1)
        buy_recommendations = await rebalancing_service.get_recommendations(limit=3)
        buy_recs = {
            "recommendations": [
                {"symbol": r.symbol, "amount": r.estimated_value}
                for r in buy_recommendations
            ]
        }
        cache.set("recommendations:3", buy_recs, ttl_seconds=900)

        # Get sell recommendations
        sell_recommendations = await rebalancing_service.calculate_sell_recommendations(limit=3)
        sell_recs = {
            "recommendations": [
                {"symbol": r.symbol, "estimated_value": r.estimated_value}
                for r in sell_recommendations
            ]
        }
        cache.set("sell_recommendations:3", sell_recs, ttl_seconds=900)

        logger.info(f"Recommendation cache refreshed: {len(buy_recommendations)} buy, {len(sell_recommendations)} sell")

    except Exception as e:
        logger.warning(f"Failed to refresh recommendation cache: {e}")
