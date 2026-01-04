"""Core service logic for PyPortfolioOpt wrapper."""

from pypfopt import EfficientFrontier, HRPOpt, risk_models, exceptions
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class PyPortfolioOptService:
    """Wrapper around PyPortfolioOpt library.

    Provides minimal interface for portfolio optimization operations
    used by arduino-trader system.
    """

    def mean_variance_optimize(
        self,
        mu: pd.Series,
        cov_matrix: pd.DataFrame,
        weight_bounds: List[Tuple[float, float]],
        sector_constraints: List[Dict],
        strategy: str,
        target_return: Optional[float] = None,
        target_volatility: Optional[float] = None
    ) -> Dict[str, float]:
        """Run mean-variance optimization using EfficientFrontier.

        Args:
            mu: Expected returns as pandas Series (symbol -> return)
            cov_matrix: Covariance matrix as pandas DataFrame
            weight_bounds: List of (min, max) tuples for each symbol
            sector_constraints: List of sector constraint dicts
            strategy: Optimization strategy to use
            target_return: Target return for efficient_return strategy
            target_volatility: Target volatility for efficient_risk strategy

        Returns:
            Dict mapping symbols to optimized weights

        Raises:
            ValueError: If strategy is invalid or required params missing
            exceptions.OptimizationError: If optimization fails
        """
        try:
            ef = EfficientFrontier(mu, cov_matrix, weight_bounds=weight_bounds)

            # Apply sector constraints
            for constraint in sector_constraints:
                ef.add_sector_constraints(
                    constraint["sector_mapper"],
                    constraint["sector_lower"],
                    constraint["sector_upper"]
                )

            # Run strategy
            if strategy == "efficient_return":
                if target_return is None:
                    raise ValueError("target_return required for efficient_return strategy")
                ef.efficient_return(target_return=target_return)
            elif strategy == "min_volatility":
                ef.min_volatility()
            elif strategy == "efficient_risk":
                if target_volatility is None:
                    raise ValueError("target_volatility required for efficient_risk strategy")
                ef.efficient_risk(target_volatility=target_volatility)
            elif strategy == "max_sharpe":
                ef.max_sharpe()
            else:
                raise ValueError(f"Unknown strategy: {strategy}")

            # Clean and return weights
            cleaned = ef.clean_weights()

            # Get performance metrics
            perf = ef.portfolio_performance(verbose=False)
            achieved_return = perf[0]  # Expected annual return
            achieved_volatility = perf[1]  # Annual volatility

            return {
                "weights": dict(cleaned),
                "achieved_return": achieved_return,
                "achieved_volatility": achieved_volatility
            }

        except exceptions.OptimizationError as e:
            logger.error(f"Optimization failed with strategy {strategy}: {e}")
            raise

    def hrp_optimize(self, returns_df: pd.DataFrame) -> Dict[str, float]:
        """Run Hierarchical Risk Parity optimization.

        Args:
            returns_df: DataFrame of returns with dates as index, symbols as columns

        Returns:
            Dict mapping symbols to optimized weights

        Raises:
            Exception: If HRP optimization fails
        """
        try:
            hrp = HRPOpt(returns_df)
            hrp.optimize()
            cleaned = hrp.clean_weights()
            return dict(cleaned)
        except Exception as e:
            logger.error(f"HRP optimization failed: {e}")
            raise

    def calculate_covariance(self, prices_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate covariance matrix using Ledoit-Wolf shrinkage.

        Args:
            prices_df: DataFrame of prices with dates as index, symbols as columns

        Returns:
            Covariance matrix as pandas DataFrame

        Raises:
            Exception: If covariance calculation fails
        """
        try:
            cov_matrix = risk_models.CovarianceShrinkage(prices_df).ledoit_wolf()
            return cov_matrix
        except Exception as e:
            logger.error(f"Covariance calculation failed: {e}")
            raise

    def progressive_optimize(
        self,
        mu: pd.Series,
        cov_matrix: pd.DataFrame,
        weight_bounds: List[Tuple[float, float]],
        sector_constraints: List[Dict],
        target_return: float
    ) -> Dict:
        """Progressive optimization with fallback strategies.

        Mirrors the portfolio_optimizer.py logic:
        1. Try each strategy with full constraints
        2. If all fail, relax sector constraints by 50%
        3. If all fail again, remove sector constraints entirely
        4. Return first success or raise error

        Args:
            mu: Expected returns as pandas Series
            cov_matrix: Covariance matrix as pandas DataFrame
            weight_bounds: List of (min, max) tuples for each symbol
            sector_constraints: List of sector constraint dicts
            target_return: Target annual return

        Returns:
            Dict with keys:
                - weights: Dict mapping symbols to weights
                - strategy_used: Strategy that succeeded
                - constraint_level: 'full', 'relaxed', or 'none'
                - attempts: Number of attempts made
                - achieved_return: Expected annual return achieved
                - achieved_volatility: Expected volatility achieved

        Raises:
            exceptions.OptimizationError: If all strategies fail at all constraint levels
        """
        strategies = ["efficient_return", "min_volatility", "efficient_risk", "max_sharpe"]
        constraint_levels = ["full", "relaxed", "none"]

        attempts = 0

        for constraint_level in constraint_levels:
            # Adjust constraints based on level
            if constraint_level == "relaxed":
                adjusted_constraints = self._relax_constraints(sector_constraints, 0.5)
                logger.info("Relaxing sector constraints by 50%")
            elif constraint_level == "none":
                adjusted_constraints = []
                logger.info("Removing all sector constraints")
            else:
                adjusted_constraints = sector_constraints

            for strategy in strategies:
                attempts += 1
                try:
                    logger.info(f"Attempt {attempts}: {strategy} with {constraint_level} constraints")

                    result = self.mean_variance_optimize(
                        mu, cov_matrix, weight_bounds,
                        adjusted_constraints, strategy,
                        target_return=target_return,
                        target_volatility=0.15  # Default target volatility for efficient_risk
                    )

                    logger.info(f"Success with {strategy} at {constraint_level} constraint level")

                    return {
                        "weights": result["weights"],
                        "strategy_used": strategy,
                        "constraint_level": constraint_level,
                        "attempts": attempts,
                        "achieved_return": result["achieved_return"],
                        "achieved_volatility": result["achieved_volatility"]
                    }
                except (exceptions.OptimizationError, ValueError) as e:
                    logger.debug(f"Strategy {strategy} failed at {constraint_level} level: {e}")
                    continue

        error_msg = f"All optimization strategies failed after {attempts} attempts"
        logger.error(error_msg)
        raise exceptions.OptimizationError(error_msg)

    def _relax_constraints(self, constraints: List[Dict], factor: float) -> List[Dict]:
        """Scale down constraint minimums by factor, keep maximums unchanged.

        Args:
            constraints: List of sector constraint dicts
            factor: Multiplier for lower bounds (e.g., 0.5 = 50% relaxation)

        Returns:
            List of relaxed constraint dicts
        """
        relaxed = []
        for c in constraints:
            relaxed.append({
                "sector_mapper": c["sector_mapper"],
                "sector_lower": {k: v * factor for k, v in c["sector_lower"].items()},
                "sector_upper": c["sector_upper"]
            })
        return relaxed
