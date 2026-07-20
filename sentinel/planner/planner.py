"""Planner - Generate deterministic contrarian trade recommendations.

This is a facade that delegates to specialized components:
- AllocationCalculator: ideal portfolio computation
- PortfolioAnalyzer: current state queries
- RebalanceEngine: trade recommendation generation
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from math import ceil
from typing import Any, Optional

from sentinel.broker import Broker
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.portfolio import Portfolio
from sentinel.services.valuation import PortfolioValuationService

from .allocation import AllocationCalculator
from .analyzer import PortfolioAnalyzer
from .models import (
    PLANNING_HORIZON_MONTHS,
    LongTermPlan,
    LongTermTarget,
    PlannerState,
    TradeRecommendation,
)
from .rebalance import RebalanceEngine


class Planner:
    """Facade over allocation, analysis, and rebalance components."""

    def __init__(
        self,
        db: Database | None = None,
        broker: Broker | None = None,
        portfolio: Portfolio | None = None,
    ):
        """Initialize planner with optional dependency injection.

        Args:
            db: Database instance (uses singleton if None)
            broker: Broker instance (uses singleton if None)
            portfolio: Portfolio instance (uses singleton if None)
        """
        self._db = db or Database()
        self._broker = broker or Broker()
        self._portfolio = portfolio or Portfolio()
        self._currency = Currency()

        # Initialize specialized components
        self._allocation_calculator = AllocationCalculator(
            db=self._db,
            portfolio=self._portfolio,
            currency=self._currency,
        )
        self._portfolio_analyzer = PortfolioAnalyzer(
            db=self._db,
            portfolio=self._portfolio,
            currency=self._currency,
        )
        self._rebalance_engine = RebalanceEngine(
            db=self._db,
            broker=self._broker,
            portfolio=self._portfolio,
            currency=self._currency,
        )

    async def calculate_ideal_portfolio(self, as_of_date: Optional[str] = None) -> dict[str, float]:
        """Calculate ideal portfolio allocations.

        Returns:
            dict: symbol -> target allocation percentage (0-1)
        """
        return await self._allocation_calculator.calculate_ideal_portfolio(as_of_date=as_of_date)

    def get_last_allocation_diagnostics(self, as_of_date: Optional[str] = None) -> dict[str, Any]:
        """Return diagnostics from the most recent allocation run for this as-of context."""
        return self._allocation_calculator.get_last_signal_bundle(as_of_date=as_of_date) or {}

    async def get_current_allocations(self, as_of_date: Optional[str] = None) -> dict[str, float]:
        """Get current portfolio allocations by symbol.

        Returns:
            dict: symbol -> allocation percentage (0-1)
        """
        return await self._portfolio_analyzer.get_current_allocations(as_of_date=as_of_date)

    async def get_recommendations(
        self,
        min_trade_value: Optional[float] = None,
        as_of_date: Optional[str] = None,
        eligible_symbols: set[str] | None = None,
        track_fallback_state: bool = False,
        state: PlannerState | None = None,
    ) -> list[TradeRecommendation]:
        """Generate trade recommendations to move toward ideal portfolio.

        Args:
            min_trade_value: Minimum trade value in EUR (uses setting if None)
            as_of_date: Optional date (YYYY-MM-DD). When set (e.g. backtest),
                prices and "today" are scoped to this date.

        Returns:
            List of TradeRecommendation, sorted by priority
        """
        state = await self._resolve_live_state(as_of_date=as_of_date, state=state)
        ideal, current, total_value, signal_bundle = await self._planning_inputs(
            as_of_date=as_of_date,
            state=state,
        )
        return await self._rebalance_engine.get_recommendations(
            ideal=ideal,
            current=current,
            total_value=total_value,
            min_trade_value=min_trade_value,
            as_of_date=as_of_date,
            precomputed_rebalance_signals=signal_bundle.get("rebalance_signals"),
            precomputed_sleeves=signal_bundle.get("sleeves"),
            eligible_symbols=eligible_symbols,
            track_fallback_state=track_fallback_state,
            state=state,
        )

    async def get_recommendations_with_plan(
        self,
        min_trade_value: Optional[float] = None,
        as_of_date: Optional[str] = None,
        eligible_symbols: set[str] | None = None,
        track_fallback_state: bool = False,
        state: PlannerState | None = None,
    ) -> tuple[list[TradeRecommendation], LongTermPlan]:
        """Generate today's actions and a whole-lot twelve-month deployment target."""
        state = await self._resolve_live_state(as_of_date=as_of_date, state=state)
        ideal, current, total_value, signal_bundle = await self._planning_inputs(
            as_of_date=as_of_date,
            state=state,
        )
        avg_monthly_net_deposit_eur = (
            float(state.avg_monthly_net_deposit_eur)
            if state is not None and state.avg_monthly_net_deposit_eur is not None
            else await self._rebalance_engine._get_avg_monthly_net_deposit(as_of_date)
        )
        recommendations = await self._rebalance_engine.get_recommendations(
            ideal=ideal,
            current=current,
            total_value=total_value,
            min_trade_value=min_trade_value,
            as_of_date=as_of_date,
            precomputed_rebalance_signals=signal_bundle.get("rebalance_signals"),
            precomputed_sleeves=signal_bundle.get("sleeves"),
            avg_monthly_net_deposit_eur=avg_monthly_net_deposit_eur,
            eligible_symbols=eligible_symbols,
            track_fallback_state=track_fallback_state,
            state=state,
        )
        security_constraints = await self._load_security_constraints()
        plan = self._build_long_term_plan(
            ideal=ideal,
            current=current,
            total_value=total_value,
            signal_bundle=signal_bundle,
            avg_monthly_net_deposit_eur=avg_monthly_net_deposit_eur,
            as_of_date=as_of_date,
            security_constraints=security_constraints,
            security_data=self._rebalance_engine.get_last_security_data(),
            recommendations=recommendations,
            min_trade_value=float(min_trade_value or 0.0),
            current_cash_eur=state.cash_eur() if state is not None else None,
        )
        return recommendations, plan

    async def _resolve_live_state(
        self,
        *,
        as_of_date: str | None,
        state: PlannerState | None,
    ) -> PlannerState | None:
        """Use the same account-and-quote valuation as the portfolio status API."""
        if state is not None or as_of_date is not None:
            return state
        valuation = await PortfolioValuationService(
            db=self._db,
            broker=self._broker,
            currency=self._currency,
        ).current()
        return PlannerState(
            positions=list(valuation.get("positions") or []),
            cash_balances={"EUR": float(valuation.get("total_cash_eur", 0.0) or 0.0)},
        )

    async def _load_security_constraints(self) -> dict[str, dict[str, Any]]:
        securities = await self._db.get_all_securities(active_only=False)
        return {str(sec["symbol"]): sec for sec in securities if sec.get("symbol")}

    async def _planning_inputs(
        self,
        *,
        as_of_date: str | None,
        state: PlannerState | None,
    ) -> tuple[dict[str, float], dict[str, float], float, dict[str, Any]]:
        ideal = await self.calculate_ideal_portfolio(as_of_date=as_of_date)
        if state is None:
            current = await self.get_current_allocations(as_of_date=as_of_date)
            total_value = await self._portfolio_analyzer.get_total_value(as_of_date=as_of_date)
        else:
            total_value = self._total_value_from_state(state)
            current = self._allocations_from_state(state, total_value)
        signal_bundle = self._allocation_calculator.get_last_signal_bundle(as_of_date=as_of_date) or {}
        return ideal, current, total_value, signal_bundle

    @classmethod
    def _build_long_term_plan(
        cls,
        *,
        ideal: dict[str, float],
        current: dict[str, float],
        total_value: float,
        signal_bundle: dict[str, Any],
        avg_monthly_net_deposit_eur: float,
        as_of_date: str | None,
        security_constraints: dict[str, dict[str, Any]] | None = None,
        security_data: dict[str, dict[str, Any]] | None = None,
        recommendations: list[TradeRecommendation] | None = None,
        min_trade_value: float = 0.0,
        current_cash_eur: float | None = None,
    ) -> LongTermPlan:
        plan_date = date.fromisoformat(as_of_date) if as_of_date else date.today()
        horizon_end = cls._add_months(plan_date, PLANNING_HORIZON_MONTHS)
        expected_contributions = avg_monthly_net_deposit_eur * PLANNING_HORIZON_MONTHS
        terminal_value = total_value + expected_contributions
        if terminal_value <= 0:
            terminal_value = total_value
            expected_contributions = 0.0

        signals = signal_bundle.get("rebalance_signals") or {}
        if current_cash_eur is None:
            current_invested_allocation = sum(float(value or 0.0) for value in current.values())
            current_cash_eur = total_value * (1.0 - current_invested_allocation)
        security_constraints = security_constraints or {}
        security_data = security_data or {}
        recommendations = recommendations or []
        recommendation_symbols = {recommendation.symbol for recommendation in recommendations}
        target_specs: dict[str, dict[str, Any]] = {}
        for symbol in set(ideal) | set(current) | recommendation_symbols:
            signal = signals.get(symbol) or {}
            raw_clara_score = signal.get("user_multiplier", 0.5)
            model_target_allocation = float(ideal.get(symbol, 0.0) or 0.0)
            current_value_eur = float(current.get(symbol, 0.0) or 0.0) * total_value
            model_target_value_eur = model_target_allocation * terminal_value
            sec = {**(security_constraints.get(symbol) or {}), **(security_data.get(symbol) or {})}
            allow_sell_raw = sec.get("allow_sell", 1)
            allow_sell = bool(1 if allow_sell_raw is None else int(allow_sell_raw))
            allow_buy_raw = sec.get("allow_buy", 1)
            allow_buy = bool(1 if allow_buy_raw is None else int(allow_buy_raw))
            price = float(sec.get("price", 0.0) or 0.0)
            fx_rate = float(sec.get("fx_rate", 1.0) or 1.0)
            lot_size = max(1, int(sec.get("lot_size", sec.get("min_lot", 1)) or 1))
            current_quantity = float(sec.get("current_qty", 0.0) or 0.0)
            if current_quantity <= 0 and price > 0 and fx_rate > 0 and current_value_eur > 0:
                current_quantity = current_value_eur / (price * fx_rate)
            target_specs[symbol] = {
                "symbol": symbol,
                "clara_score": float(0.5 if raw_clara_score is None else raw_clara_score),
                "opportunity_score": float(signal.get("opp_score", 0.0) or 0.0),
                "current_value_eur": current_value_eur,
                "target_value_eur": current_value_eur,
                "current_quantity": current_quantity,
                "target_quantity": current_quantity,
                "model_target_allocation": model_target_allocation,
                "model_target_value_eur": model_target_value_eur,
                "allow_buy": allow_buy,
                "sell_locked": not allow_sell,
                "trade_blocked": bool(sec.get("trade_blocked", False)),
                "price": price,
                "currency": str(sec.get("currency", "EUR") or "EUR"),
                "fx_rate": fx_rate,
                "lot_size": lot_size,
                "planned_buy_value_eur": 0.0,
            }

        # The deployable budget consists only of cash, forecast contributions,
        # and proceeds from the explicit sells in today's executable plan.
        available_budget_eur = current_cash_eur + expected_contributions
        for recommendation in recommendations:
            if recommendation.action != "sell":
                continue
            spec = target_specs[recommendation.symbol]
            sell_value = min(spec["target_value_eur"], abs(float(recommendation.value_delta_eur)))
            sell_quantity = min(spec["target_quantity"], float(recommendation.quantity))
            spec["target_value_eur"] -= sell_value
            spec["target_quantity"] -= sell_quantity
            available_budget_eur += sell_value

        # Preserve today's explicit buys in the twelve-month target, then use
        # the remaining horizon budget for additional whole-lot deployment.
        for recommendation in recommendations:
            if recommendation.action != "buy":
                continue
            spec = target_specs[recommendation.symbol]
            buy_value = abs(float(recommendation.value_delta_eur))
            if buy_value > available_budget_eur + 1e-9:
                continue
            spec["target_value_eur"] += buy_value
            spec["target_quantity"] += float(recommendation.quantity)
            spec["planned_buy_value_eur"] += buy_value
            available_budget_eur -= buy_value

        while available_budget_eur > 0:
            best: tuple[float, str, float, int] | None = None
            for symbol, spec in target_specs.items():
                if not spec["allow_buy"] or spec["trade_blocked"]:
                    continue
                lot_value_eur = spec["price"] * spec["fx_rate"] * spec["lot_size"]
                if lot_value_eur <= 0:
                    continue
                increment_lots = 1
                if spec["planned_buy_value_eur"] <= 0 and min_trade_value > lot_value_eur:
                    increment_lots = ceil(min_trade_value / lot_value_eur)
                increment_value_eur = lot_value_eur * increment_lots
                if increment_value_eur > available_budget_eur + 1e-9:
                    continue
                before_error = spec["model_target_value_eur"] - spec["target_value_eur"]
                after_error = before_error - increment_value_eur
                improvement = before_error**2 - after_error**2
                if improvement <= 1e-9:
                    continue
                candidate = (improvement, symbol, increment_value_eur, increment_lots)
                if (
                    best is None
                    or candidate[0] > best[0] + 1e-9
                    or (abs(candidate[0] - best[0]) <= 1e-9 and candidate[1] < best[1])
                ):
                    best = candidate
            if best is None:
                break
            _, symbol, increment_value_eur, increment_lots = best
            spec = target_specs[symbol]
            spec["target_value_eur"] += increment_value_eur
            spec["target_quantity"] += increment_lots * spec["lot_size"]
            spec["planned_buy_value_eur"] += increment_value_eur
            available_budget_eur -= increment_value_eur

        target_cash_value_eur = available_budget_eur
        target_cash_allocation = target_cash_value_eur / terminal_value if terminal_value > 0 else 0.0

        targets: list[LongTermTarget] = []
        for spec in target_specs.values():
            target_value_eur = spec["target_value_eur"]
            target_allocation = target_value_eur / terminal_value if terminal_value > 0 else 0.0
            targets.append(
                LongTermTarget(
                    symbol=spec["symbol"],
                    clara_score=spec["clara_score"],
                    opportunity_score=spec["opportunity_score"],
                    target_allocation=target_allocation,
                    current_value_eur=spec["current_value_eur"],
                    target_value_eur=target_value_eur,
                    gap_eur=target_value_eur - spec["current_value_eur"],
                    model_target_allocation=spec["model_target_allocation"],
                    model_target_value_eur=spec["model_target_value_eur"],
                    sell_locked=spec["sell_locked"],
                    current_quantity=spec["current_quantity"],
                    target_quantity=spec["target_quantity"],
                    quantity_delta=spec["target_quantity"] - spec["current_quantity"],
                    price=spec["price"] or None,
                    currency=spec["currency"],
                    lot_size=spec["lot_size"],
                )
            )
        targets.sort(key=lambda target: (-target.target_allocation, target.symbol))

        return LongTermPlan(
            as_of_date=plan_date.isoformat(),
            horizon_end_date=horizon_end.isoformat(),
            horizon_months=PLANNING_HORIZON_MONTHS,
            current_total_value_eur=total_value,
            avg_monthly_net_deposit_eur=avg_monthly_net_deposit_eur,
            expected_contributions_eur=expected_contributions,
            terminal_portfolio_value_eur=terminal_value,
            current_cash_eur=current_cash_eur,
            target_cash_allocation=target_cash_allocation,
            target_cash_value_eur=target_cash_value_eur,
            cash_gap_eur=target_cash_value_eur - current_cash_eur,
            targets=targets,
        )

    @staticmethod
    def _total_value_from_state(state: PlannerState) -> float:
        """Calculate total value from planner state values that are already EUR."""
        positions_value = sum(
            float(pos.get("value_eur", pos.get("current_value_eur", 0.0)) or 0.0) for pos in state.positions
        )
        return positions_value + state.cash_eur()

    @staticmethod
    def _allocations_from_state(state: PlannerState, total_value: float) -> dict[str, float]:
        """Calculate symbol allocations from EUR state without FX conversion."""
        if total_value <= 0:
            return {}
        allocations: dict[str, float] = {}
        for pos in state.positions:
            symbol = str(pos.get("symbol", ""))
            if not symbol:
                continue
            value_eur = float(pos.get("value_eur", pos.get("current_value_eur", 0.0)) or 0.0)
            if value_eur <= 0:
                continue
            allocations[symbol] = value_eur / total_value
        return allocations

    async def get_rebalance_summary(self) -> dict:
        """Get summary of portfolio alignment with ideal allocations.

        Returns:
            dict with alignment metrics and status
        """
        return await self._portfolio_analyzer.get_rebalance_summary()

    @staticmethod
    def _add_months(source: date, months: int) -> date:
        month_index = source.month - 1 + months
        year = source.year + month_index // 12
        month = month_index % 12 + 1
        day = min(source.day, monthrange(year, month)[1])
        return date(year, month, day)
