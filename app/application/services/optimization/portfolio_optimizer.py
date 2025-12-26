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
    fallback_used: Optional[str]  # None, "max_sharpe", or "hrp"
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

    Fallback strategy:
    1. Try efficient_return(target=0.11)
    2. If fails, try max_sharpe()
    3. If fails, use pure HRP
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
        geo_targets: Optional[Dict[str, float]] = None,
        ind_targets: Optional[Dict[str, float]] = None,
        min_cash_reserve: float = 500.0,
        dividend_bonuses: Optional[Dict[str, float]] = None,
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
            geo_targets: Geography allocation targets
            ind_targets: Industry allocation targets
            min_cash_reserve: Minimum cash to keep (not allocated)
            dividend_bonuses: Pending dividend bonuses per symbol

        Returns:
            OptimizationResult with target weights and diagnostics
        """
        timestamp = datetime.now()
        geo_targets = geo_targets or {}
        ind_targets = ind_targets or {}
        dividend_bonuses = dividend_bonuses or {}

        # Get symbols with active stocks
        symbols = [s.symbol for s in stocks if s.active]

        if not symbols:
            return self._error_result(timestamp, blend, "No active stocks")

        # Calculate expected returns
        expected_returns = await self._returns_calc.calculate_expected_returns(
            symbols,
            target_return=target_return,
            dividend_bonuses=dividend_bonuses,
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
        geo_constraints, ind_constraints = (
            self._constraints_manager.build_sector_constraints(
                valid_stocks, geo_targets, ind_targets
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
        )

        # Run HRP
        hrp_weights = self._run_hrp(returns_df, valid_symbols)

        # Blend weights
        if mv_weights and hrp_weights:
            target_weights = self._blend_weights(mv_weights, hrp_weights, blend)
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
            bounds, geo_constraints, ind_constraints
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
    ) -> Tuple[Optional[Dict[str, float]], Optional[str]]:
        """
        Run Mean-Variance optimization with fallback strategy.

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

        try:
            # Strategy 1: Target return
            ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
            ef.efficient_return(target_return=target_return)
            cleaned = ef.clean_weights()
            logger.info(
                f"MV optimization succeeded with target return {target_return:.1%}"
            )
            return dict(cleaned), None

        except OptimizationError as e:
            logger.warning(f"MV target return failed: {e}")

            try:
                # Strategy 2: Max Sharpe
                ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)
                ef.max_sharpe()
                cleaned = ef.clean_weights()
                logger.info("MV optimization succeeded with max_sharpe fallback")
                return dict(cleaned), "max_sharpe"

            except OptimizationError as e2:
                logger.warning(f"MV max_sharpe failed: {e2}")
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
            pos = positions.get(symbol)
            if pos and portfolio_value > 0:
                current = pos.market_value_eur / portfolio_value
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
