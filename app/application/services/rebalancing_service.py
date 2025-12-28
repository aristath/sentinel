"""Rebalancing application service.

Orchestrates rebalancing operations using domain services and repositories.
Uses long-term value scoring with portfolio-aware allocation fit.
"""

import logging
from typing import Dict, List, Optional

from app.application.services.recommendation.portfolio_context_builder import (
    build_portfolio_context,
)
from app.domain.analytics.market_regime import detect_market_regime
from app.domain.models import MultiStepRecommendation, Recommendation
from app.domain.repositories.protocols import (
    IAllocationRepository,
    IPositionRepository,
    ISettingsRepository,
    IStockRepository,
    ITradeRepository,
)
from app.domain.services.allocation_calculator import get_max_trades
from app.domain.services.exchange_rate_service import ExchangeRateService
from app.domain.services.settings_service import SettingsService
from app.domain.value_objects.currency import Currency
from app.domain.value_objects.recommendation_status import RecommendationStatus
from app.domain.value_objects.trade_side import TradeSide
from app.infrastructure.database.manager import DatabaseManager
from app.infrastructure.external import yahoo_finance as yahoo
from app.infrastructure.external.tradernet import TradernetClient
from app.repositories import PortfolioRepository, RecommendationRepository


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
        from app.domain.planning.holistic_planner import create_holistic_plan
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

        # Get positions and stocks (needed for portfolio value calculation)
        positions = await self._position_repo.get_all()
        stocks = await self._stock_repo.get_all_active()

        # Get current cash balance
        available_cash = (
            self._tradernet_client.get_total_cash_eur()
            if self._tradernet_client.is_connected
            else 0.0
        )

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

        # Get country/industry targets from allocations
        country_allocations = await self._allocation_repo.get_by_type("country")
        ind_allocations = await self._allocation_repo.get_by_type("industry")
        country_targets = {a.name: a.target_pct / 100 for a in country_allocations}
        ind_targets = {a.name: a.target_pct / 100 for a in ind_allocations}

        # Get pending dividend bonuses (DRIP fallback)
        dividend_repo = DividendRepository()
        dividend_bonuses = await dividend_repo.get_pending_bonuses()

        # Regime already detected above for cash reserves, reuse for expected returns

        # Run portfolio optimizer
        optimizer = PortfolioOptimizer()
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

        # Create holistic plan with optimizer weights
        plan = await create_holistic_plan(
            portfolio_context=portfolio_context,
            available_cash=available_cash,
            stocks=stocks,
            positions=positions,
            exchange_rate_service=self._exchange_rate_service,
            target_weights=target_weights,
            current_prices=current_prices,
            transaction_cost_fixed=transaction_fixed,
            transaction_cost_percent=transaction_pct,
            max_plan_depth=max_plan_depth,
        )

        # Convert HolisticPlan to MultiStepRecommendation list
        if not plan.steps:
            return []

        recommendations = []
        running_cash = available_cash
        for step in plan.steps:
            cash_before = running_cash
            if step.side == TradeSide.SELL:
                running_cash += step.estimated_value
            else:
                running_cash -= step.estimated_value
            running_cash = max(0, running_cash)

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
                    portfolio_score_before=plan.current_score,
                    portfolio_score_after=plan.end_state_score,
                    score_change=plan.improvement,
                    available_cash_before=cash_before,
                    available_cash_after=running_cash,
                )
            )

        logger.info(
            f"Holistic planner generated {len(recommendations)} recommendations"
        )
        return recommendations
