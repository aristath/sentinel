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
            logger.warning(f"MV target return failed: {e}")

            try:
                # Strategy 2: Min Volatility (lower risk for retirement)
                ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
                _apply_sector_constraints(ef)
                ef.min_volatility()
                cleaned = ef.clean_weights()
                logger.info("MV optimization succeeded with min_volatility fallback")
                return dict(cleaned), "min_volatility"

            except OptimizationError as e2:
                logger.warning(f"MV min_volatility failed: {e2}")

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
                    logger.warning(f"MV efficient_risk failed: {e3}")

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
                        logger.warning(f"MV max_sharpe failed: {e4}")
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
