"""Rebalancing application service.

Orchestrates rebalancing operations using domain services and repositories.
Uses long-term value scoring with portfolio-aware allocation fit.
"""

import json
import logging
from typing import Dict, List, Optional

from app.modules.analytics.domain.market_regime import detect_market_regime
from app.domain.exceptions import ValidationError
from app.domain.models import MultiStepRecommendation, Recommendation
from app.domain.repositories.protocols import (
    IAllocationRepository,
    IPositionRepository,
    ISettingsRepository,
    IStockRepository,
    ITradeRepository,
)
from app.core.database.manager import DatabaseManager
from app.domain.services.allocation_calculator import get_max_trades
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.services.settings_service import SettingsService
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.external.tradernet import TradernetClient
from app.modules.planning.services.portfolio_context_builder import (
    build_portfolio_context,
)
from app.modules.portfolio.database.portfolio_repository import PortfolioRepository
from app.modules.scoring.domain.models import PortfolioContext
from app.repositories import RecommendationRepository
from app.shared.domain.value_objects.currency import Currency
from app.shared.domain.value_objects.recommendation_status import RecommendationStatus
from app.shared.domain.value_objects.trade_side import TradeSide


def calculate_min_trade_amount(
    transaction_cost_fixed: float,
    transaction_cost_percent: float,
    max_cost_ratio: float = 0.01,  # 1% max cost-to-trade ratio
) -> float:
    """
    Calculate minimum trade amount where transaction costs are acceptable.

    With Freedom24's €2 + 0.2% fee structure:
    - €50 trade: €2.10 cost = 4.2% drag → not worthwhile
    - €200 trade: €2.40 cost = 1.2% drag → marginal
    - €400 trade: €2.80 cost = 0.7% drag → acceptable

    Args:
        transaction_cost_fixed: Fixed cost per trade (e.g., €2.00)
        transaction_cost_percent: Variable cost as fraction (e.g., 0.002 = 0.2%)
        max_cost_ratio: Maximum acceptable cost-to-trade ratio (default 1%)

    Returns:
        Minimum trade amount in EUR
    """
    # Solve for trade amount where: (fixed + trade * percent) / trade = max_ratio
    # fixed / trade + percent = max_ratio
    # trade = fixed / (max_ratio - percent)
    denominator = max_cost_ratio - transaction_cost_percent
    if denominator <= 0:
        # If variable cost exceeds max ratio, return a high minimum
        return 1000.0
    return transaction_cost_fixed / denominator


logger = logging.getLogger(__name__)


class RebalancingService:
    """Application service for rebalancing operations."""

    def __init__(
        self,
        stock_repo: IStockRepository,
        position_repo: IPositionRepository,
        allocation_repo: IAllocationRepository,
        portfolio_repo: PortfolioRepository,
        trade_repo: ITradeRepository,
        settings_repo: ISettingsRepository,
        recommendation_repo: RecommendationRepository,
        db_manager: DatabaseManager,
        tradernet_client: TradernetClient,
        exchange_rate_service: ExchangeRateService,
    ):
        self._stock_repo = stock_repo
        self._position_repo = position_repo
        self._allocation_repo = allocation_repo
        self._portfolio_repo = portfolio_repo
        self._trade_repo = trade_repo
        self._settings_repo = settings_repo
        self._settings_service = SettingsService(self._settings_repo)
        self._recommendation_repo = recommendation_repo
        self._db_manager = db_manager
        self._tradernet_client = tradernet_client
        self._exchange_rate_service = exchange_rate_service

    async def calculate_rebalance_trades(
        self, available_cash: float
    ) -> List[Recommendation]:
        """
        Calculate optimal trades using get_recommendations() as the source of truth.
        """
        settings = await self._settings_service.get_settings()
        min_trade_amount = calculate_min_trade_amount(
            settings.transaction_cost_fixed,
            settings.transaction_cost_percent,
        )

        if available_cash < min_trade_amount:
            logger.info(
                f"Cash €{available_cash:.2f} below minimum trade €{min_trade_amount:.2f}"
            )
            return []

        max_trades = get_max_trades(available_cash, min_trade_amount)
        if max_trades == 0:
            return []

        # Get unified recommendations (holistic planner sequence)
        unified_steps = await self.get_recommendations()

        if not unified_steps:
            logger.info("No recommendations available")
            return []

        # Extract buy recommendations from the sequence
        buy_steps = [step for step in unified_steps if step.side == TradeSide.BUY]
        if not buy_steps:
            logger.info("No buy recommendations in sequence")
            return []

        # Convert MultiStepRecommendation to Recommendation format
        recommendations = []
        for step in buy_steps[:max_trades]:  # Limit to max_trades
            try:
                currency_val = step.currency
                if isinstance(currency_val, str):
                    currency = Currency.from_string(currency_val)
                else:
                    currency = currency_val

                # Convert string side to TradeSide enum if needed
                side_val = (
                    TradeSide.from_string(step.side)
                    if isinstance(step.side, str)
                    else step.side
                )

                # Validate before creating Recommendation (will raise ValidationError if invalid)
                if step.quantity <= 0 or step.estimated_price <= 0:
                    logger.warning(
                        f"Skipping {step.symbol}: invalid quantity ({step.quantity}) or price ({step.estimated_price})"
                    )
                    continue

                recommendations.append(
                    Recommendation(
                        symbol=step.symbol,
                        name=step.name,
                        side=side_val,
                        quantity=step.quantity,
                        estimated_price=step.estimated_price,
                        estimated_value=step.estimated_value,
                        reason=step.reason,
                        country=None,
                        currency=currency,
                        status=RecommendationStatus.PENDING,
                    )
                )
            except ValidationError as e:
                logger.warning(f"Skipping invalid recommendation {step.symbol}: {e}")
                continue

        if not recommendations:
            logger.info("No buy recommendations available")
            return []

        # Recommendations are already in unified format, just filter valid ones
        trades = []
        for rec in recommendations:
            if (
                rec.quantity is None
                or rec.quantity <= 0
                or rec.estimated_price is None
                or rec.estimated_price <= 0
            ):
                logger.warning(
                    f"Skipping {rec.symbol}: missing or invalid quantity or price"
                )
                continue

            # Recommendation is already in the correct format
            trades.append(rec)

        logger.info(
            f"Generated {len(trades)} trade recommendations from {len(recommendations)} buy recommendations"
        )

        return trades

    async def get_recommendations(self) -> List[MultiStepRecommendation]:
        """
        Generate optimal recommendation sequence using the portfolio optimizer + holistic planner.

        Flow:
        1. Portfolio optimizer calculates target weights (MV + HRP blend)
        2. Holistic planner identifies opportunities from weight gaps
        3. Planner generates action sequences and evaluates end-states
        4. Returns the optimal sequence

        Returns:
            List of MultiStepRecommendation objects representing the optimal sequence
        """
        from app.application.services.optimization import PortfolioOptimizer
        from app.repositories import DividendRepository

        # Get optimizer settings
        optimizer_blend = await self._settings_repo.get_float("optimizer_blend", 0.5)
        optimizer_target = await self._settings_repo.get_float(
            "optimizer_target_return", 0.11
        )
        transaction_fixed = await self._settings_repo.get_float(
            "transaction_cost_fixed", 2.0
        )
        transaction_pct = await self._settings_repo.get_float(
            "transaction_cost_percent", 0.002
        )
        min_cash = await self._settings_repo.get_float("min_cash_reserve", 500.0)
        max_plan_depth = await self._settings_repo.get_int("max_plan_depth", 5)
        max_opportunities_per_category = await self._settings_repo.get_int(
            "max_opportunities_per_category", 5
        )
        enable_combinatorial = (
            await self._settings_repo.get_float("enable_combinatorial_generation", 1.0)
            == 1.0
        )
        priority_threshold = await self._settings_repo.get_float(
            "priority_threshold_for_combinations", 0.3
        )
        combinatorial_max_combinations_per_depth = await self._settings_repo.get_int(
            "combinatorial_max_combinations_per_depth", 50
        )
        combinatorial_max_sells = await self._settings_repo.get_int(
            "combinatorial_max_sells", 4
        )
        combinatorial_max_buys = await self._settings_repo.get_int(
            "combinatorial_max_buys", 4
        )
        combinatorial_max_candidates = await self._settings_repo.get_int(
            "combinatorial_max_candidates", 12
        )
        beam_width = await self._settings_repo.get_int("beam_width", 10)

        # Get positions and stocks (needed for portfolio value calculation)
        positions = await self._position_repo.get_all()
        stocks = await self._stock_repo.get_all_active()

        # Get current cash balance
        available_cash = (
            self._tradernet_client.get_total_cash_eur()
            if self._tradernet_client.is_connected
            else 0.0
        )

        # Fetch and apply pending orders to get hypothetical future state
        pending_orders = []
        if self._tradernet_client.is_connected:
            try:
                pending_orders = self._tradernet_client.get_pending_orders()
                logger.info(f"Found {len(pending_orders)} pending orders")
            except Exception as e:
                logger.warning(f"Failed to fetch pending orders: {e}")

        # Apply pending orders to positions and cash
        if pending_orders:
            from app.domain.models import Position
            from app.domain.portfolio_hash import apply_pending_orders_to_portfolio

            # Convert positions to dict format for adjustment
            position_dicts = [
                {"symbol": p.symbol, "quantity": p.quantity} for p in positions
            ]
            # Get cash balances in all currencies
            cash_balances_raw = (
                self._tradernet_client.get_cash_balances()
                if self._tradernet_client.is_connected
                else []
            )
            cash_balances = (
                {b.currency: b.amount for b in cash_balances_raw}
                if cash_balances_raw
                else {}
            )

            # Apply pending orders
            adjusted_position_dicts, adjusted_cash_balances = (
                apply_pending_orders_to_portfolio(
                    position_dicts, cash_balances, pending_orders
                )
            )

            # Convert adjusted position dicts back to Position objects
            # Create a map of symbol -> Position for lookup
            position_map = {p.symbol: p for p in positions}
            adjusted_positions = []
            for pos_dict in adjusted_position_dicts:
                symbol = pos_dict["symbol"]
                quantity = pos_dict["quantity"]
                if symbol in position_map:
                    # Copy existing position and update quantity
                    original = position_map[symbol]
                    adjusted_positions.append(
                        Position(
                            symbol=original.symbol,
                            quantity=quantity,
                            avg_price=original.avg_price,
                            isin=original.isin,
                            currency=original.currency,
                            currency_rate=original.currency_rate,
                            current_price=original.current_price,
                            market_value_eur=(
                                original.market_value_eur
                                * (quantity / original.quantity)
                                if original.quantity > 0 and original.market_value_eur
                                else None
                            ),
                            cost_basis_eur=(
                                original.cost_basis_eur * (quantity / original.quantity)
                                if original.quantity > 0 and original.cost_basis_eur
                                else None
                            ),
                            unrealized_pnl=original.unrealized_pnl,
                            unrealized_pnl_pct=original.unrealized_pnl_pct,
                            last_updated=original.last_updated,
                            first_bought_at=original.first_bought_at,
                            last_sold_at=original.last_sold_at,
                        )
                    )
                else:
                    # New position from pending BUY order
                    # Find the order to get the price for avg_price
                    order_price = None
                    order_currency = None
                    for order in pending_orders:
                        if (
                            order.get("symbol", "").upper() == symbol
                            and order.get("side", "").lower() == "buy"
                        ):
                            order_price = float(order.get("price", 0))
                            order_currency = order.get("currency", "EUR")
                            break

                    # Use order price as avg_price (required by Position validation)
                    # If we can't find the order, use a minimal valid price
                    avg_price = order_price if order_price and order_price > 0 else 0.01

                    from app.domain.value_objects.currency import Currency

                    currency = (
                        Currency.from_string(order_currency)
                        if order_currency
                        else Currency.EUR
                    )

                    adjusted_positions.append(
                        Position(
                            symbol=symbol,
                            quantity=quantity,
                            avg_price=avg_price,
                            currency=currency,
                            currency_rate=1.0,
                        )
                    )

            # For BUY orders that add new positions, we already handled them above
            # For SELL orders that remove positions, they're already filtered out (qty <= 0)

            positions = adjusted_positions

            # Recalculate available_cash from adjusted cash balances
            if adjusted_cash_balances:
                amounts_in_eur = await self._exchange_rate_service.batch_convert_to_eur(
                    adjusted_cash_balances
                )
                available_cash = sum(amounts_in_eur.values())
                logger.info(
                    f"Adjusted available_cash for pending orders: {available_cash:.2f} EUR"
                )
            else:
                # If no cash balances, available_cash should be 0
                available_cash = 0.0
                logger.info("No cash balances after applying pending orders")

        # Get current prices for portfolio value calculation
        yahoo_symbols: Dict[str, Optional[str]] = {
            s.symbol: s.yahoo_symbol for s in stocks if s.yahoo_symbol
        }
        current_prices = yahoo.get_batch_quotes(yahoo_symbols)

        # Calculate total portfolio value (positions + cash)
        def _get_position_value(p) -> float:
            price = current_prices.get(p.symbol)
            if price is not None:
                return float(p.quantity) * float(price)
            elif p.quantity > 0 and p.market_value_eur is not None:
                return float(p.market_value_eur)
            return 0.0

        total_position_value = sum(_get_position_value(p) for p in positions)
        portfolio_value = total_position_value + available_cash

        # Adjust cash reserve based on market regime (if enabled)
        regime_enabled = await self._settings_repo.get_float(
            "market_regime_detection_enabled", 1.0
        )
        regime: Optional[str] = None
        if regime_enabled == 1.0:
            try:
                regime = await detect_market_regime(self._tradernet_client)
                if regime == "bull":
                    reserve_pct = await self._settings_repo.get_float(
                        "market_regime_bull_cash_reserve", 0.02
                    )
                    # Calculate EUR from percentage, maintain €500 floor
                    min_cash = max(portfolio_value * reserve_pct, 500.0)
                    logger.info(
                        f"Bull market detected: using {reserve_pct*100:.1f}% cash reserve = €{min_cash:.2f}"
                    )
                elif regime == "bear":
                    reserve_pct = await self._settings_repo.get_float(
                        "market_regime_bear_cash_reserve", 0.05
                    )
                    # Calculate EUR from percentage, maintain €500 floor
                    min_cash = max(portfolio_value * reserve_pct, 500.0)
                    logger.info(
                        f"Bear market detected: using {reserve_pct*100:.1f}% cash reserve = €{min_cash:.2f}"
                    )
                elif regime == "sideways":
                    reserve_pct = await self._settings_repo.get_float(
                        "market_regime_sideways_cash_reserve", 0.03
                    )
                    # Calculate EUR from percentage, maintain €500 floor
                    min_cash = max(portfolio_value * reserve_pct, 500.0)
                    logger.info(
                        f"Sideways market detected: using {reserve_pct*100:.1f}% cash reserve = €{min_cash:.2f}"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to detect market regime, using default cash reserve: {e}"
                )
                # min_cash already set to default above

        # Build portfolio context
        portfolio_context = await build_portfolio_context(
            position_repo=self._position_repo,
            stock_repo=self._stock_repo,
            allocation_repo=self._allocation_repo,
            db_manager=self._db_manager,
        )

        # Build positions dict for optimizer
        positions_dict = {p.symbol: p for p in positions}

        # Calculate portfolio value
        portfolio_value = portfolio_context.total_value

        # Get country/industry group targets from allocations
        # Note: target_pct is already stored as a fraction (0-1), not a percentage (0-100)
        country_targets = await self._allocation_repo.get_country_group_targets()
        ind_targets = await self._allocation_repo.get_industry_group_targets()

        # Get pending dividend bonuses (DRIP fallback)
        dividend_repo = DividendRepository()
        dividend_bonuses = await dividend_repo.get_pending_bonuses()

        # Regime already detected above for cash reserves, reuse for expected returns

        # Run portfolio optimizer
        from app.repositories import GroupingRepository

        grouping_repo = GroupingRepository()
        optimizer = PortfolioOptimizer(grouping_repo=grouping_repo)
        optimization_result = await optimizer.optimize(
            stocks=stocks,
            positions=positions_dict,
            portfolio_value=portfolio_value,
            current_prices=current_prices,
            cash_balance=available_cash,
            blend=optimizer_blend,
            target_return=optimizer_target,
            country_targets=country_targets,
            ind_targets=ind_targets,
            min_cash_reserve=min_cash,
            regime=regime,
            dividend_bonuses=dividend_bonuses,
            transaction_cost_fixed=transaction_fixed,
            transaction_cost_percent=transaction_pct,
        )

        # Log optimizer result
        if optimization_result.success:
            logger.info(
                f"Optimizer: blend={optimizer_blend}, "
                f"target={optimizer_target:.1%}, "
                f"achieved={optimization_result.achieved_expected_return:.1%}, "
                f"fallback={optimization_result.fallback_used}"
            )
            target_weights = optimization_result.target_weights
        else:
            logger.warning(
                f"Optimizer failed: {optimization_result.error}, using heuristics"
            )
            target_weights = None

        # Check if incremental mode is enabled
        incremental_enabled = (
            await self._settings_repo.get_float("incremental_planner_enabled", 1.0)
            == 1.0
        )

        plan = None

        # Try incremental mode first if enabled
        if incremental_enabled:
            from app.domain.portfolio_hash import generate_portfolio_hash
            from app.modules.planning.database.planner_repository import (
                PlannerRepository,
            )

            planner_repo = PlannerRepository()
            position_dicts = [
                {"symbol": p.symbol, "quantity": p.quantity} for p in positions
            ]
            # Get cash balances for hash
            cash_balances_for_hash = (
                {
                    b.currency: b.amount
                    for b in self._tradernet_client.get_cash_balances()
                }
                if self._tradernet_client.is_connected
                else {}
            )
            portfolio_hash = generate_portfolio_hash(
                position_dicts, stocks, cash_balances_for_hash, pending_orders
            )
            best_result = await planner_repo.get_best_result(portfolio_hash)

            if best_result:
                # Get best sequence from database
                best_sequence = await planner_repo.get_best_sequence_from_hash(
                    portfolio_hash, best_result["best_sequence_hash"]
                )

                if best_sequence:
                    # Get evaluation for best sequence
                    db = await planner_repo._get_db()
                    eval_row = await db.fetchone(
                        """SELECT end_score, breakdown_json, end_cash, end_context_positions_json,
                                  div_score, total_value
                         FROM evaluations
                         WHERE sequence_hash = ? AND portfolio_hash = ?""",
                        (best_result["best_sequence_hash"], portfolio_hash),
                    )

                    if eval_row:
                        from app.domain.scoring.diversification import (
                            calculate_portfolio_score,
                        )
                        from app.modules.planning.domain.narrative import (
                            generate_plan_narrative,
                            generate_step_narrative,
                        )

                        breakdown = json.loads(eval_row["breakdown_json"])
                        current_score = await calculate_portfolio_score(
                            portfolio_context
                        )

                        # Convert sequence to HolisticPlan
                        from app.modules.planning.domain.holistic_planner import (
                            HolisticPlan,
                            HolisticStep,
                        )

                        steps = []
                        for i, action in enumerate(best_sequence):
                            narrative = generate_step_narrative(
                                action, portfolio_context, {}
                            )
                            # Convert side to string if it's a TradeSide enum
                            side_str = (
                                action.side.value
                                if hasattr(action.side, "value")
                                else str(action.side)
                            )
                            steps.append(
                                HolisticStep(
                                    step_number=i + 1,
                                    side=side_str,
                                    symbol=action.symbol,
                                    name=action.name,
                                    quantity=action.quantity,
                                    estimated_price=action.price,
                                    estimated_value=action.value_eur,
                                    currency=action.currency,
                                    reason=action.reason,
                                    narrative=narrative,
                                )
                            )

                        narrative_summary = generate_plan_narrative(
                            steps, current_score.total, eval_row["end_score"] * 100, {}
                        )

                        plan = HolisticPlan(
                            steps=steps,
                            current_score=current_score.total,
                            end_state_score=eval_row["end_score"] * 100,
                            improvement=(eval_row["end_score"] * 100)
                            - current_score.total,
                            narrative_summary=narrative_summary,
                            score_breakdown=breakdown,
                            cash_required=sum(
                                s.estimated_value for s in steps if s.side == "BUY"
                            ),
                            cash_generated=sum(
                                s.estimated_value for s in steps if s.side == "SELL"
                            ),
                            feasible=True,
                        )
                        logger.info(
                            f"Using best result from incremental planner database (score: {eval_row['end_score']:.3f})"
                        )

        # Fallback to full mode if incremental didn't return a plan
        if not plan:
            from app.modules.planning.domain.holistic_planner import (
                create_holistic_plan,
            )

            logger.info(
                "Using full planner mode (incremental disabled or no database result)"
            )
            # Reserve min_cash_reserve - planner should only use cash above the reserve
            planner_available_cash = max(0.0, available_cash - min_cash)
            if planner_available_cash < available_cash:
                logger.info(
                    f"Reserving €{min_cash:.2f} from available cash, planner can use €{planner_available_cash:.2f}"
                )
            plan = await create_holistic_plan(
                portfolio_context=portfolio_context,
                available_cash=planner_available_cash,
                stocks=stocks,
                positions=positions,
                exchange_rate_service=self._exchange_rate_service,
                target_weights=target_weights,
                current_prices=current_prices,
                transaction_cost_fixed=transaction_fixed,
                transaction_cost_percent=transaction_pct,
                max_plan_depth=max_plan_depth,
                max_opportunities_per_category=max_opportunities_per_category,
                enable_combinatorial=enable_combinatorial,
                priority_threshold=priority_threshold,
                combinatorial_max_combinations_per_depth=combinatorial_max_combinations_per_depth,
                combinatorial_max_sells=combinatorial_max_sells,
                combinatorial_max_buys=combinatorial_max_buys,
                combinatorial_max_candidates=combinatorial_max_candidates,
                beam_width=beam_width,
            )

        # Convert HolisticPlan to MultiStepRecommendation list
        if not plan.steps:
            return []

        from app.domain.scoring.diversification import calculate_portfolio_score

        recommendations = []
        running_cash = available_cash
        current_context = portfolio_context
        current_score_value = plan.current_score

        # Simulate each step and calculate intermediate scores
        for step in plan.steps:
            cash_before = running_cash
            score_before = current_score_value

            # Simulate this single step
            stocks_by_symbol = {s.symbol: s for s in stocks}
            stock = stocks_by_symbol.get(step.symbol)
            country = stock.country if stock else None
            industry = stock.industry if stock else None

            new_positions = dict(current_context.positions)
            new_geographies = dict(current_context.stock_countries or {})
            new_industries = dict(current_context.stock_industries or {})

            if step.side == "SELL":
                current_value = new_positions.get(step.symbol, 0)
                new_positions[step.symbol] = max(
                    0, current_value - step.estimated_value
                )
                if new_positions[step.symbol] <= 0:
                    new_positions.pop(step.symbol, None)
                running_cash += step.estimated_value
                new_total = current_context.total_value
            else:  # BUY
                if step.estimated_value > running_cash:
                    # Skip if can't afford (shouldn't happen, but handle gracefully)
                    continue
                new_positions[step.symbol] = (
                    new_positions.get(step.symbol, 0) + step.estimated_value
                )
                if country:
                    new_geographies[step.symbol] = country
                if industry:
                    new_industries[step.symbol] = industry
                running_cash -= step.estimated_value
                new_total = current_context.total_value

            running_cash = max(0, running_cash)

            # Update context for next iteration
            current_context = PortfolioContext(
                country_weights=current_context.country_weights,
                industry_weights=current_context.industry_weights,
                positions=new_positions,
                total_value=new_total,
                stock_countries=new_geographies,
                stock_industries=new_industries,
                stock_scores=current_context.stock_scores,
                stock_dividends=current_context.stock_dividends,
            )

            # Calculate portfolio score after this step
            portfolio_score_after_step = await calculate_portfolio_score(
                current_context
            )
            score_after = portfolio_score_after_step.total
            score_change = score_after - score_before

            recommendations.append(
                MultiStepRecommendation(
                    step=step.step_number,
                    side=step.side,
                    symbol=step.symbol,
                    name=step.name,
                    quantity=step.quantity,
                    estimated_price=step.estimated_price,
                    estimated_value=step.estimated_value,
                    currency=step.currency,
                    reason=step.narrative,
                    portfolio_score_before=score_before,
                    portfolio_score_after=score_after,
                    score_change=score_change,
                    available_cash_before=cash_before,
                    available_cash_after=running_cash,
                )
            )

            # Update current_score_value for next iteration
            current_score_value = score_after

        logger.info(
            f"Holistic planner generated {len(recommendations)} recommendations"
        )
        return recommendations
