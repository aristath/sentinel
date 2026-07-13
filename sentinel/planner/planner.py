"""Planner - Generate deterministic contrarian trade recommendations.

This is a facade that delegates to specialized components:
- AllocationCalculator: ideal portfolio computation
- PortfolioAnalyzer: current state queries
- RebalanceEngine: trade recommendation generation
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any, Optional

from sentinel.broker import Broker
from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.portfolio import Portfolio
from sentinel.settings import Settings

from .allocation import AllocationCalculator
from .analyzer import PortfolioAnalyzer
from .models import PlannerState, TradeRecommendation
from .rebalance import RebalanceEngine
from .rebalance_rules import calculate_transaction_cost


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
        self._settings = Settings()

        # Initialize specialized components
        self._allocation_calculator = AllocationCalculator(
            db=self._db,
            portfolio=self._portfolio,
            currency=self._currency,
            settings=self._settings,
        )
        self._portfolio_analyzer = PortfolioAnalyzer(
            db=self._db,
            portfolio=self._portfolio,
            currency=self._currency,
            settings=self._settings,
        )
        self._rebalance_engine = RebalanceEngine(
            db=self._db,
            broker=self._broker,
            portfolio=self._portfolio,
            settings=self._settings,
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
        ideal = await self.calculate_ideal_portfolio(as_of_date=as_of_date)
        if state is None:
            current = await self.get_current_allocations(as_of_date=as_of_date)
            total_value = await self._portfolio_analyzer.get_total_value(as_of_date=as_of_date)
        else:
            total_value = self._total_value_from_state(state)
            current = self._allocations_from_state(state, total_value)
        signal_bundle = self._allocation_calculator.get_last_signal_bundle(as_of_date=as_of_date) or {}

        return await self._rebalance_engine.get_recommendations(
            ideal=ideal,
            current=current,
            total_value=total_value,
            min_trade_value=min_trade_value,
            as_of_date=as_of_date,
            precomputed_rebalance_signals=signal_bundle.get("rebalance_signals"),
            precomputed_sleeves=signal_bundle.get("sleeves"),
            state=state,
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

    async def forecast_monthly_plans(
        self,
        *,
        months: int = 6,
        initial_state: PlannerState | None = None,
        monthly_deposit_eur: float | None = None,
        min_trade_value: Optional[float] = None,
        start_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Forecast repeated monthly plans from explicit EUR planner state."""
        if months <= 0:
            return []

        state = self._copy_state(initial_state or await self.build_current_state())
        forecast_start_date = start_date or date.today()
        deposit_eur = (
            float(monthly_deposit_eur)
            if monthly_deposit_eur is not None
            else float(state.avg_monthly_net_deposit_eur or 0.0)
        )
        forecast: list[dict[str, Any]] = []

        for month_index in range(1, months + 1):
            month_as_of_date = self._add_months(forecast_start_date, month_index - 1).isoformat()
            starting_cash = self._cash_eur_from_state(state)
            starting_total = self._total_value_from_state(state)
            recommendations = await self.get_recommendations(
                min_trade_value=min_trade_value,
                as_of_date=month_as_of_date,
                state=state,
            )
            value_summary = await self._recommendation_value_summary(recommendations)
            state = await self._state_after_recommendations(state, recommendations)
            ending_cash = self._cash_eur_from_state(state)
            ending_total = self._total_value_from_state(state)

            forecast.append(
                {
                    "month": month_index,
                    "as_of_date": month_as_of_date,
                    "starting_cash_eur": starting_cash,
                    "starting_total_value_eur": starting_total,
                    "recommendations": recommendations,
                    **value_summary,
                    "ending_cash_eur": ending_cash,
                    "ending_total_value_eur": ending_total,
                    "next_deposit_eur": deposit_eur if month_index < months else 0.0,
                }
            )

            if month_index < months and deposit_eur:
                state.cash_balances["EUR"] = self._cash_eur_from_state(state) + deposit_eur

        return forecast

    @staticmethod
    def _add_months(source: date, months: int) -> date:
        month_index = source.month - 1 + months
        year = source.year + month_index // 12
        month = month_index % 12 + 1
        day = min(source.day, monthrange(year, month)[1])
        return date(year, month, day)

    async def build_current_state(self) -> PlannerState:
        """Build planner state from live portfolio inputs, converted to EUR."""
        positions: list[dict] = []
        for pos in await self._portfolio.positions():
            quantity = float(pos.get("quantity", 0) or 0)
            price = float(pos.get("current_price", 0) or 0)
            currency = str(pos.get("currency", "EUR") or "EUR")
            value_eur = await self._currency.to_eur(quantity * price, currency)
            positions.append(
                {
                    "symbol": pos["symbol"],
                    "quantity": pos.get("quantity", 0),
                    "current_price": price,
                    "currency": currency,
                    "value_eur": value_eur,
                }
            )

        cash_eur = 0.0
        for currency, amount in (await self._portfolio.get_cash_balances()).items():
            cash_eur += await self._currency.to_eur(float(amount or 0.0), currency)

        return PlannerState(
            positions=positions,
            cash_balances={"EUR": cash_eur},
            avg_monthly_net_deposit_eur=await self._rebalance_engine._get_avg_monthly_net_deposit(None),
        )

    @staticmethod
    def _copy_state(state: PlannerState) -> PlannerState:
        return PlannerState(
            positions=[dict(pos) for pos in state.positions],
            cash_balances=dict(state.cash_balances),
            avg_monthly_net_deposit_eur=state.avg_monthly_net_deposit_eur,
        )

    @staticmethod
    def _cash_eur_from_state(state: PlannerState) -> float:
        return state.cash_eur()

    async def _recommendation_value_summary(self, recommendations: list[TradeRecommendation]) -> dict[str, float]:
        fixed_fee = float(await self._settings.get("transaction_fee_fixed", 2.0) or 0.0)
        pct_fee = float(await self._settings.get("transaction_fee_percent", 0.2) or 0.0) / 100.0
        total_buy_value = 0.0
        total_sell_value = 0.0
        buy_fees = 0.0
        sell_fees = 0.0

        for rec in recommendations:
            value_eur = abs(float(rec.value_delta_eur))
            fee_eur = calculate_transaction_cost(value_eur, fixed_fee, pct_fee)
            if rec.action == "buy":
                total_buy_value += value_eur
                buy_fees += fee_eur
            else:
                total_sell_value += value_eur
                sell_fees += fee_eur

        total_fees = buy_fees + sell_fees
        return {
            "total_buy_value_eur": total_buy_value,
            "total_sell_value_eur": total_sell_value,
            "buy_fees_eur": buy_fees,
            "sell_fees_eur": sell_fees,
            "total_fees_eur": total_fees,
            "net_trade_cash_delta_eur": total_sell_value - sell_fees - total_buy_value - buy_fees,
        }

    async def _state_after_recommendations(
        self,
        state: PlannerState,
        recommendations: list[TradeRecommendation],
    ) -> PlannerState:
        next_state = self._copy_state(state)
        positions = {str(pos.get("symbol", "")): dict(pos) for pos in next_state.positions if pos.get("symbol")}
        cash_eur = self._cash_eur_from_state(next_state)
        fixed_fee = float(await self._settings.get("transaction_fee_fixed", 2.0) or 0.0)
        pct_fee = float(await self._settings.get("transaction_fee_percent", 0.2) or 0.0) / 100.0

        for rec in recommendations:
            value_eur = abs(float(rec.value_delta_eur))
            fee_eur = calculate_transaction_cost(value_eur, fixed_fee, pct_fee)
            position = positions.get(rec.symbol) or {
                "symbol": rec.symbol,
                "quantity": 0,
                "current_price": rec.price,
                "currency": rec.currency,
                "value_eur": 0.0,
            }
            quantity = float(position.get("quantity", 0) or 0)
            position_value = float(position.get("value_eur", position.get("current_value_eur", 0.0)) or 0.0)

            if rec.action == "buy":
                quantity += rec.quantity
                position_value += value_eur
                cash_eur -= value_eur + fee_eur
            else:
                quantity = max(0.0, quantity - rec.quantity)
                position_value = max(0.0, position_value - value_eur)
                cash_eur += value_eur - fee_eur

            position.update(
                {
                    "quantity": quantity,
                    "current_price": rec.price,
                    "currency": rec.currency,
                    "value_eur": position_value,
                }
            )
            positions[rec.symbol] = position

        next_state.positions = [
            pos
            for pos in positions.values()
            if float(pos.get("quantity", 0) or 0) > 0 or float(pos.get("value_eur", 0) or 0) > 0
        ]
        next_state.cash_balances = {"EUR": cash_eur}
        return next_state
