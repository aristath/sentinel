"""
Portfolio Optimizer Service.

Provides portfolio-level optimization using PyPortfolioOpt with a blended
Mean-Variance + Hierarchical Risk Parity approach.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from pypfopt import EfficientFrontier, HRPOpt
from pypfopt.exceptions import OptimizationError

from app.application.services.optimization.constraints_manager import ConstraintsManager
from app.application.services.optimization.expected_returns import (
    ExpectedReturnsCalculator,
)
from app.application.services.optimization.risk_models import RiskModelBuilder
from app.domain.constants import TARGET_PORTFOLIO_VOLATILITY
from app.domain.models import Position, Stock
from app.domain.scoring.constants import (
    OPTIMIZER_TARGET_RETURN,
    OPTIMIZER_WEIGHT_CUTOFF,
)

logger = logging.getLogger(__name__)


@dataclass
class WeightChange:
    """Represents a change in target weight for a stock."""

    symbol: str
    current_weight: float
    target_weight: float
    change: float  # target - current
    reason: Optional[str] = None


@dataclass
class OptimizationResult:
    """Result of portfolio optimization."""

    timestamp: datetime
    target_return: float
    achieved_expected_return: Optional[float]
    blend_used: float
    fallback_used: Optional[
        str
    ]  # None, "min_volatility", "efficient_risk", "max_sharpe", or "hrp"
    target_weights: Dict[str, float]
    weight_changes: List[WeightChange]
    high_correlations: List[Dict]  # Pairs with correlation > 0.80
    constraints_summary: Dict
    success: bool
    error: Optional[str] = None


class PortfolioOptimizer:
    """
    Portfolio optimizer using Mean-Variance + HRP blending.

    The optimizer calculates target portfolio weights by:
    1. Running Mean-Variance optimization targeting 11% return
    2. Running Hierarchical Risk Parity for robustness
    3. Blending the two based on the blend parameter (0-1)

    Fallback strategy (retirement-appropriate for 15-20 year horizon):
    1. Try efficient_return(target=0.11) - Primary strategy
    2. If fails, try min_volatility() - Lower risk for retirement
    3. If fails, try efficient_risk(target_volatility=0.15) - Target 15% volatility
    4. If fails, try max_sharpe() - Final MV fallback
    5. If all fail, use pure HRP
    """

    def __init__(
        self,
        expected_returns_calc: Optional[ExpectedReturnsCalculator] = None,
        risk_model_builder: Optional[RiskModelBuilder] = None,
        constraints_manager: Optional[ConstraintsManager] = None,
    ):
        self._returns_calc = expected_returns_calc or ExpectedReturnsCalculator()
        self._risk_builder = risk_model_builder or RiskModelBuilder()
        self._constraints_manager = constraints_manager or ConstraintsManager()

    async def optimize(
        self,
        stocks: List[Stock],
        positions: Dict[str, Position],
        portfolio_value: float,
        current_prices: Dict[str, float],
        cash_balance: float,
        blend: float = 0.5,
        target_return: float = OPTIMIZER_TARGET_RETURN,
        country_targets: Optional[Dict[str, float]] = None,
        ind_targets: Optional[Dict[str, float]] = None,
        min_cash_reserve: float = 500.0,
        dividend_bonuses: Optional[Dict[str, float]] = None,
        regime: Optional[str] = None,
        transaction_cost_fixed: float = 2.0,
        transaction_cost_percent: float = 0.002,
    ) -> OptimizationResult:
        """
        Optimize portfolio allocation.

        Args:
            stocks: List of Stock objects in universe
            positions: Dict mapping symbol to current Position
            portfolio_value: Total portfolio value in EUR
            current_prices: Dict mapping symbol to current price
            cash_balance: Current cash balance in EUR
            blend: Blend factor (0.0 = pure MV, 1.0 = pure HRP)
            target_return: Target annual return for MV optimization
            country_targets: Country allocation targets
            ind_targets: Industry allocation targets
            min_cash_reserve: Minimum cash to keep (not allocated)
            dividend_bonuses: Pending dividend bonuses per symbol
            regime: Market regime ("bull", "bear", "sideways") for expected returns adjustment
            transaction_cost_fixed: Fixed transaction cost per trade (EUR)
            transaction_cost_percent: Variable transaction cost as fraction (e.g., 0.002 = 0.2%)

        Returns:
            OptimizationResult with target weights and diagnostics
        """
        timestamp = datetime.now()
        country_targets = country_targets or {}
        ind_targets = ind_targets or {}
        dividend_bonuses = dividend_bonuses or {}

        # Get symbols with active stocks
        symbols = [s.symbol for s in stocks if s.active]

        if not symbols:
            return self._error_result(timestamp, blend, "No active stocks")

        # Calculate expected returns (with regime adjustment)
        expected_returns = await self._returns_calc.calculate_expected_returns(
            symbols,
            target_return=target_return,
            dividend_bonuses=dividend_bonuses,
            regime=regime,
        )

        if not expected_returns:
            return self._error_result(timestamp, blend, "No expected returns data")

        # Adjust expected returns for transaction costs
        # This naturally prefers larger positions and fewer trades
        expected_returns = self._adjust_returns_for_transaction_costs(
            expected_returns,
            positions,
            portfolio_value,
            transaction_cost_fixed,
            transaction_cost_percent,
        )

        # Filter to symbols with expected returns
        valid_symbols = list(expected_returns.keys())

        # Build covariance matrix
        cov_matrix, returns_df = await self._risk_builder.build_covariance_matrix(
            valid_symbols
        )

        if cov_matrix is None or returns_df.empty:
            return self._error_result(timestamp, blend, "Insufficient price history")

        # Filter to symbols in covariance matrix
        cov_symbols = list(cov_matrix.index)
        expected_returns = {
            s: expected_returns[s] for s in cov_symbols if s in expected_returns
        }
        valid_symbols = list(expected_returns.keys())

        # Calculate weight bounds
        stocks_map = {s.symbol: s for s in stocks}
        valid_stocks = [stocks_map[s] for s in valid_symbols if s in stocks_map]
        bounds = self._constraints_manager.calculate_weight_bounds(
            valid_stocks, positions, portfolio_value, current_prices
        )

        # Build sector constraints
        country_constraints, ind_constraints = (
            self._constraints_manager.build_sector_constraints(
                valid_stocks, country_targets, ind_targets
            )
        )

        # Get high correlations for reporting
        high_correlations = self._risk_builder.get_correlations(
            returns_df, threshold=0.80
        )

        # Run optimization with fallback strategy
        mv_weights, fallback_used = await self._run_mean_variance(
            expected_returns,
            cov_matrix,
            bounds,
            target_return,
            country_constraints,
            ind_constraints,
        )

        # Run HRP
        hrp_weights = self._run_hrp(returns_df, valid_symbols)
        if hrp_weights:
            # Clamp HRP weights to bounds (HRP doesn't support bounds natively)
            hrp_weights = self._clamp_weights_to_bounds(hrp_weights, bounds)

        # Blend weights
        if mv_weights and hrp_weights:
            target_weights = self._blend_weights(mv_weights, hrp_weights, blend)
            # Clamp blended weights to bounds (blending can violate bounds)
            target_weights = self._clamp_weights_to_bounds(target_weights, bounds)
        elif mv_weights:
            target_weights = mv_weights
            logger.warning("Using pure MV weights (HRP failed)")
        elif hrp_weights:
            target_weights = hrp_weights
            fallback_used = "hrp"
            logger.warning("Using pure HRP weights (MV failed)")
        else:
            return self._error_result(timestamp, blend, "Both MV and HRP failed")

        # Apply weight cutoff (remove tiny allocations)
        target_weights = {
            s: w for s, w in target_weights.items() if w >= OPTIMIZER_WEIGHT_CUTOFF
        }

        # Normalize weights to sum to (1 - cash_reserve_fraction)
        investable_fraction = (
            1.0 - (min_cash_reserve / portfolio_value) if portfolio_value > 0 else 0.9
        )
        target_weights = self._normalize_weights(target_weights, investable_fraction)
        # Clamp weights to bounds (respect portfolio targets)
        # Normalization can push weights above max_portfolio_target bounds
        target_weights = self._clamp_weights_to_bounds(target_weights, bounds)

        # Calculate weight changes
        weight_changes = self._calculate_weight_changes(
            target_weights, positions, portfolio_value
        )

        # Calculate achieved expected return
        achieved_return = sum(
            expected_returns.get(s, 0) * w for s, w in target_weights.items()
        )

        # Build constraints summary
        constraints_summary = self._constraints_manager.get_constraint_summary(
            bounds, country_constraints, ind_constraints
        )

        return OptimizationResult(
            timestamp=timestamp,
            target_return=target_return,
            achieved_expected_return=achieved_return,
            blend_used=blend,
            fallback_used=fallback_used,
            target_weights=target_weights,
            weight_changes=weight_changes,
            high_correlations=high_correlations[:5],  # Top 5 pairs
            constraints_summary=constraints_summary,
            success=True,
        )

    def _validate_constraints(
        self,
        common_symbols: List[str],
        bounds: Dict[str, Tuple[float, float]],
        country_constraints: List,
        ind_constraints: List,
    ) -> Tuple[bool, List[str]]:
        """
        Validate that constraints are feasible.

        Returns:
            Tuple of (is_feasible, list_of_warnings)
        """
        warnings = []
        is_feasible = True

        # Check individual stock bounds
        locked_stocks = []
        for symbol in common_symbols:
            if symbol in bounds:
                lower, upper = bounds[symbol]
                if lower > upper:
                    warnings.append(
                        f"{symbol}: invalid bounds (lower={lower:.2%} > upper={upper:.2%})"
                    )
                    is_feasible = False
                elif lower == upper:
                    locked_stocks.append(symbol)

        if locked_stocks:
            logger.debug(f"Locked stocks (can't change): {len(locked_stocks)}")

        # Check country constraints
        country_min_sum = sum(c.lower for c in country_constraints)
        country_max_sum = sum(c.upper for c in country_constraints)

        if country_constraints:
            if country_min_sum > 1.0:
                warnings.append(
                    f"Country constraints minimum sum ({country_min_sum:.2%}) > 100%"
                )
                is_feasible = False
            if country_max_sum < 0.5:
                warnings.append(
                    f"Country constraints maximum sum ({country_max_sum:.2%}) < 50%"
                )
                # Not necessarily infeasible, but might be too restrictive

            logger.debug(
                f"Country constraints: {len(country_constraints)} sectors, "
                f"min_sum={country_min_sum:.2%}, max_sum={country_max_sum:.2%}"
            )

        # Check industry constraints
        ind_min_sum = sum(c.lower for c in ind_constraints)
        ind_max_sum = sum(c.upper for c in ind_constraints)

        if ind_constraints:
            if ind_min_sum > 1.0:
                warnings.append(
                    f"Industry constraints minimum sum ({ind_min_sum:.2%}) > 100%"
                )
                is_feasible = False
            if ind_max_sum < 0.5:
                warnings.append(
                    f"Industry constraints maximum sum ({ind_max_sum:.2%}) < 50%"
                )
                # Not necessarily infeasible, but might be too restrictive

            logger.debug(
                f"Industry constraints: {len(ind_constraints)} sectors, "
                f"min_sum={ind_min_sum:.2%}, max_sum={ind_max_sum:.2%}"
            )

        # Check total minimum sum across all constraints
        # This is critical - if country + industry minimums exceed 100%, it's infeasible
        # Note: Individual stock minimums are already accounted for in bounds
        total_min_sum = country_min_sum + ind_min_sum
        if total_min_sum > 1.0:
            warnings.append(
                f"Total minimum constraints sum ({total_min_sum:.2%}) > 100% "
                f"(country={country_min_sum:.2%}, industry={ind_min_sum:.2%}). "
                f"This will cause optimization infeasibility."
            )
            is_feasible = False
            logger.warning(
                f"Constraint infeasibility detected: total minimum sum = {total_min_sum:.2%} > 100%"
            )

        # Check if any symbols are missing from sector constraints
        country_symbols = set()
        for constraint in country_constraints:
            country_symbols.update(constraint.symbols)

        ind_symbols = set()
        for constraint in ind_constraints:
            ind_symbols.update(constraint.symbols)

        unconstrained_symbols = set(common_symbols) - country_symbols - ind_symbols
        if unconstrained_symbols and (country_constraints or ind_constraints):
            logger.debug(
                f"{len(unconstrained_symbols)} symbols not in any sector constraint"
            )

        return is_feasible, warnings

    async def _run_mean_variance(
        self,
        expected_returns: Dict[str, float],
        cov_matrix: pd.DataFrame,
        bounds: Dict[str, Tuple[float, float]],
        target_return: float,
        country_constraints: List,
        ind_constraints: List,
    ) -> Tuple[Optional[Dict[str, float]], Optional[str]]:
        """
        Run Mean-Variance optimization with fallback strategy.

        Args:
            expected_returns: Dict mapping symbol to expected return
            cov_matrix: Covariance matrix DataFrame
            bounds: Dict mapping symbol to (lower, upper) weight bounds
            target_return: Target annual return
            country_constraints: List of SectorConstraint for countries
            ind_constraints: List of SectorConstraint for industries

        Returns:
            Tuple of (weights_dict, fallback_used)
        """
        # Convert expected returns to Series
        mu = pd.Series(expected_returns)

        # Ensure same order as covariance matrix
        common_symbols = [s for s in cov_matrix.index if s in mu.index]
        mu = mu[common_symbols]
        S = cov_matrix.loc[common_symbols, common_symbols]

        # Build weight bounds tuple list
        weight_bounds = []
        for symbol in common_symbols:
            if symbol in bounds:
                weight_bounds.append(bounds[symbol])
            else:
                weight_bounds.append((0, 0.20))  # Default

        # Build sector mappers and bounds from country constraints
        country_mapper = {}
        country_lower = {}
        country_upper = {}
        for constraint in country_constraints:
            for symbol in constraint.symbols:
                if symbol in common_symbols:
                    country_mapper[symbol] = constraint.name
            country_lower[constraint.name] = constraint.lower
            country_upper[constraint.name] = constraint.upper

        # Build sector mappers and bounds from industry constraints
        industry_mapper = {}
        industry_lower = {}
        industry_upper = {}
        for constraint in ind_constraints:
            for symbol in constraint.symbols:
                if symbol in common_symbols:
                    industry_mapper[symbol] = constraint.name
            industry_lower[constraint.name] = constraint.lower
            industry_upper[constraint.name] = constraint.upper

        # Validate constraints before attempting optimization
        is_feasible, warnings = self._validate_constraints(
            common_symbols, bounds, country_constraints, ind_constraints
        )

        if warnings:
            logger.warning(f"Constraint validation warnings: {'; '.join(warnings)}")

        # Check for constraint overlap (stocks in both country and industry constraints)
        country_symbols = set()
        for constraint in country_constraints:
            country_symbols.update(constraint.symbols)

        ind_symbols = set()
        for constraint in ind_constraints:
            ind_symbols.update(constraint.symbols)

        overlapping_symbols = country_symbols & ind_symbols
        if overlapping_symbols:
            logger.info(
                f"{len(overlapping_symbols)} symbols appear in both country and industry constraints: "
                f"{', '.join(sorted(overlapping_symbols)[:10])}"
            )

        # Log individual stock bound summary for debugging
        if bounds:
            total_stock_min = sum(lower for lower, _ in bounds.values())
            total_stock_max = sum(upper for _, upper in bounds.values())
            locked_count = sum(
                1 for lower, upper in bounds.values() if lower == upper and lower > 0
            )
            logger.info(
                f"Individual stock bounds: {len(bounds)} stocks, "
                f"min_sum={total_stock_min:.2%}, max_sum={total_stock_max:.2%}, "
                f"locked={locked_count}"
            )

        # Scale down constraints if combined minimums exceed feasibility threshold
        # This is critical - individual stock bounds can add significant minimum requirements
        if bounds and (country_constraints or ind_constraints):
            total_stock_min = sum(lower for lower, _ in bounds.values())
            country_min_sum = sum(c.lower for c in country_constraints)
            ind_min_sum = sum(c.lower for c in ind_constraints)
            total_all_min = total_stock_min + country_min_sum + ind_min_sum

            # Target: total minimums = 85% (leaves 15% slack for optimizer)
            # This is more conservative than 90% to handle complex constraint interactions
            target_total_min = 0.85

            if total_all_min > target_total_min:
                logger.warning(
                    f"Total minimum bounds (stocks={total_stock_min:.2%} + "
                    f"country={country_min_sum:.2%} + industry={ind_min_sum:.2%} = "
                    f"{total_all_min:.2%}) exceed {target_total_min:.0%}, scaling down constraints"
                )

                # Strategy: Scale down proportionally, but prioritize individual stock bounds
                # If stock minimums are very high (>70%), scale them down first
                # Otherwise, scale sector constraints
                if total_stock_min > 0.70:
                    # Stock minimums are too high - scale them down
                    stock_scale_factor = (
                        target_total_min - country_min_sum - ind_min_sum
                    ) / total_stock_min
                    if stock_scale_factor > 0 and stock_scale_factor < 1.0:
                        logger.warning(
                            f"Individual stock minimum bounds ({total_stock_min:.2%}) are too high, "
                            f"scaling down by {stock_scale_factor:.2%}"
                        )
                        # Scale individual stock bounds (modify bounds dict)
                        for symbol in bounds:
                            lower, upper = bounds[symbol]
                            new_lower = lower * stock_scale_factor
                            bounds[symbol] = (new_lower, upper)
                        total_stock_min = sum(lower for lower, _ in bounds.values())
                        total_all_min = total_stock_min + country_min_sum + ind_min_sum

                # Scale sector constraints to reach target
                if total_all_min > target_total_min:
                    target_sector_min = max(0.0, target_total_min - total_stock_min)
                    current_sector_min = country_min_sum + ind_min_sum

                    if (
                        current_sector_min > 0
                        and target_sector_min < current_sector_min
                    ):
                        scale_factor = target_sector_min / current_sector_min
                        for constraint in country_constraints:
                            constraint.lower = constraint.lower * scale_factor
                            constraint.lower = min(constraint.lower, constraint.upper)
                        for constraint in ind_constraints:
                            constraint.lower = constraint.lower * scale_factor
                            constraint.lower = min(constraint.lower, constraint.upper)

                        logger.info(
                            f"Scaled sector minimums by {scale_factor:.2%} to "
                            f"{target_sector_min:.2%} (stocks={total_stock_min:.2%}, "
                            f"total={target_sector_min + total_stock_min:.2%})"
                        )

        def _apply_sector_constraints(ef: EfficientFrontier) -> None:
            """Apply sector constraints to EfficientFrontier."""
            if country_mapper:
                ef.add_sector_constraints(country_mapper, country_lower, country_upper)
            if industry_mapper:
                ef.add_sector_constraints(
                    industry_mapper, industry_lower, industry_upper
                )

        try:
            # Strategy 1: Target return
            ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
            _apply_sector_constraints(ef)
            ef.efficient_return(target_return=target_return)
            cleaned = ef.clean_weights()
            logger.info(
                f"MV optimization succeeded with target return {target_return:.1%}"
            )
            return dict(cleaned), None

        except OptimizationError as e:
            logger.warning(
                f"MV target return failed: {e}. "
                f"Symbols={len(common_symbols)}, "
                f"Country constraints={len(country_constraints)}, "
                f"Industry constraints={len(ind_constraints)}"
            )
            if warnings:
                logger.warning(f"Constraint validation issues: {'; '.join(warnings)}")

            try:
                # Strategy 2: Min Volatility (lower risk for retirement)
                ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
                _apply_sector_constraints(ef)
                ef.min_volatility()
                cleaned = ef.clean_weights()
                logger.info("MV optimization succeeded with min_volatility fallback")
                return dict(cleaned), "min_volatility"

            except OptimizationError as e2:
                logger.warning(
                    f"MV min_volatility failed: {e2}. "
                    f"Trying next fallback strategy..."
                )

                try:
                    # Strategy 3: Efficient Risk (target 15% volatility)
                    ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
                    _apply_sector_constraints(ef)
                    ef.efficient_risk(target_volatility=TARGET_PORTFOLIO_VOLATILITY)
                    cleaned = ef.clean_weights()
                    logger.info(
                        f"MV optimization succeeded with efficient_risk fallback "
                        f"(target volatility {TARGET_PORTFOLIO_VOLATILITY:.1%})"
                    )
                    return dict(cleaned), "efficient_risk"

                except OptimizationError as e3:
                    logger.warning(
                        f"MV efficient_risk failed: {e3}. "
                        f"Trying final fallback strategy..."
                    )

                    try:
                        # Strategy 4: Max Sharpe (final MV fallback)
                        ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
                        _apply_sector_constraints(ef)
                        ef.max_sharpe()
                        cleaned = ef.clean_weights()
                        logger.info(
                            "MV optimization succeeded with max_sharpe fallback"
                        )
                        return dict(cleaned), "max_sharpe"

                    except OptimizationError as e4:
                        logger.warning(
                            f"MV max_sharpe failed: {e4}. "
                            f"All MV strategies failed. Constraint summary: "
                            f"country_min_sum={sum(c.lower for c in country_constraints):.2%}, "
                            f"country_max_sum={sum(c.upper for c in country_constraints):.2%}, "
                            f"ind_min_sum={sum(c.lower for c in ind_constraints):.2%}, "
                            f"ind_max_sum={sum(c.upper for c in ind_constraints):.2%}"
                        )
                        return None, None

    def _run_hrp(
        self,
        returns_df: pd.DataFrame,
        symbols: List[str],
    ) -> Optional[Dict[str, float]]:
        """
        Run Hierarchical Risk Parity optimization.

        Args:
            returns_df: DataFrame of daily returns
            symbols: List of symbols to include

        Returns:
            Dict mapping symbol to weight, or None if failed
        """
        try:
            # Filter returns to requested symbols
            available = [s for s in symbols if s in returns_df.columns]
            if len(available) < 2:
                logger.warning("HRP needs at least 2 symbols")
                return None

            filtered_returns = returns_df[available]

            hrp = HRPOpt(filtered_returns)
            hrp.optimize()
            cleaned = hrp.clean_weights()

            logger.info(f"HRP optimization succeeded for {len(available)} symbols")
            return dict(cleaned)

        except Exception as e:
            logger.error(f"HRP optimization failed: {e}")
            return None

    def _blend_weights(
        self,
        mv_weights: Dict[str, float],
        hrp_weights: Dict[str, float],
        blend: float,
    ) -> Dict[str, float]:
        """
        Blend MV and HRP weights.

        Args:
            mv_weights: Mean-Variance weights
            hrp_weights: HRP weights
            blend: Blend factor (0.0 = pure MV, 1.0 = pure HRP)

        Returns:
            Blended weights dict
        """
        all_symbols = set(mv_weights.keys()) | set(hrp_weights.keys())
        blended = {}

        for symbol in all_symbols:
            mv_w = mv_weights.get(symbol, 0.0)
            hrp_w = hrp_weights.get(symbol, 0.0)
            blended[symbol] = blend * hrp_w + (1 - blend) * mv_w

        logger.debug(f"Blended {len(all_symbols)} weights with blend={blend}")
        return blended

    def _clamp_weights_to_bounds(
        self,
        weights: Dict[str, float],
        bounds: Dict[str, Tuple[float, float]],
    ) -> Dict[str, float]:
        """Clamp weights to their bounds (respects portfolio targets)."""
        clamped = {}
        for symbol, weight in weights.items():
            if symbol in bounds:
                lower, upper = bounds[symbol]
                clamped[symbol] = max(lower, min(upper, weight))
            else:
                clamped[symbol] = weight
        return clamped

    def _normalize_weights(
        self,
        weights: Dict[str, float],
        target_sum: float = 1.0,
    ) -> Dict[str, float]:
        """Normalize weights to sum to target_sum."""
        total = sum(weights.values())
        if total == 0:
            return weights

        factor = target_sum / total
        return {s: w * factor for s, w in weights.items()}

    def _adjust_returns_for_transaction_costs(
        self,
        expected_returns: Dict[str, float],
        positions: Dict[str, Position],
        portfolio_value: float,
        transaction_cost_fixed: float,
        transaction_cost_percent: float,
    ) -> Dict[str, float]:
        """
        Adjust expected returns to account for transaction costs.

        This naturally prefers larger positions and fewer trades by reducing
        expected returns more for positions that would require small trades.

        Args:
            expected_returns: Dict mapping symbol to expected return
            positions: Dict mapping symbol to current Position
            portfolio_value: Total portfolio value in EUR
            transaction_cost_fixed: Fixed cost per trade (EUR)
            transaction_cost_percent: Variable cost as fraction

        Returns:
            Adjusted expected returns dict
        """
        adjusted = {}
        min_trade_value = transaction_cost_fixed / (
            0.01 - transaction_cost_percent
        )  # Trade where cost = 1% of value

        for symbol, exp_return in expected_returns.items():
            # Get current position value
            pos = positions.get(symbol)
            current_value = (
                pos.market_value_eur if pos and pos.market_value_eur else 0.0
            )

            # Estimate potential trade value
            # For new positions, assume minimum trade size
            # For existing positions, assume rebalancing trade (estimate as 5% of portfolio)
            if current_value == 0:
                # New position: assume minimum trade size
                estimated_trade_value = min_trade_value
            else:
                # Existing position: assume rebalancing trade
                # Use a reasonable estimate (5% of portfolio or current position, whichever is smaller)
                estimated_trade_value = min(portfolio_value * 0.05, current_value * 0.5)

            # Calculate transaction cost as percentage of trade value
            if estimated_trade_value > 0:
                cost = (
                    transaction_cost_fixed
                    + estimated_trade_value * transaction_cost_percent
                )
                cost_ratio = cost / estimated_trade_value
            else:
                cost_ratio = 0.01  # Default 1% if we can't estimate

            # Reduce expected return by transaction cost
            # Cap reduction at 2% to avoid over-penalizing
            cost_reduction = min(cost_ratio, 0.02)
            adjusted_return = exp_return - cost_reduction

            adjusted[symbol] = adjusted_return

            logger.debug(
                f"{symbol}: exp_return={exp_return:.2%}, "
                f"cost_ratio={cost_ratio:.2%}, "
                f"adjusted={adjusted_return:.2%}"
            )

        return adjusted

    def _calculate_weight_changes(
        self,
        target_weights: Dict[str, float],
        positions: Dict[str, Position],
        portfolio_value: float,
    ) -> List[WeightChange]:
        """Calculate weight changes from current to target."""
        changes = []

        # Get all symbols (both target and current)
        all_symbols = set(target_weights.keys())
        for symbol, pos in positions.items():
            all_symbols.add(symbol)

        for symbol in all_symbols:
            # Current weight
            pos_maybe = positions.get(symbol)
            if pos_maybe is not None and portfolio_value > 0:
                market_value = pos_maybe.market_value_eur
                if market_value is not None:
                    current = market_value / portfolio_value
                else:
                    current = 0.0
            else:
                current = 0.0

            # Target weight
            target = target_weights.get(symbol, 0.0)

            # Change
            change = target - current

            if abs(change) > 0.001:  # Ignore tiny changes
                changes.append(
                    WeightChange(
                        symbol=symbol,
                        current_weight=round(current, 4),
                        target_weight=round(target, 4),
                        change=round(change, 4),
                    )
                )

        # Sort by absolute change (largest first)
        changes.sort(key=lambda x: abs(x.change), reverse=True)
        return changes

    def _error_result(
        self,
        timestamp: datetime,
        blend: float,
        error: str,
    ) -> OptimizationResult:
        """Create an error result."""
        logger.error(f"Optimization failed: {error}")
        return OptimizationResult(
            timestamp=timestamp,
            target_return=OPTIMIZER_TARGET_RETURN,
            achieved_expected_return=None,
            blend_used=blend,
            fallback_used=None,
            target_weights={},
            weight_changes=[],
            high_correlations=[],
            constraints_summary={},
            success=False,
            error=error,
        )
