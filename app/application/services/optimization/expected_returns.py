"""
Expected Returns Calculator.

Calculates expected returns for each stock by blending:
- Historical CAGR (70% default, 80% in bull, 70% in sideways)
- Score-adjusted target return (30% default, 20% in bull, 30% in sideways)
- Market regime adjustment (bear: reduce by 20-30%)
- User preference multiplier (priority_multiplier)
- Pending dividend bonus (DRIP fallback)
"""

import logging
from typing import Dict, List, Optional

from app.domain.scoring.constants import (
    EXPECTED_RETURN_MAX,
    EXPECTED_RETURN_MIN,
    EXPECTED_RETURNS_CAGR_WEIGHT,
    EXPECTED_RETURNS_SCORE_WEIGHT,
    OPTIMIZER_TARGET_RETURN,
)
from app.repositories.calculations import CalculationsRepository
from app.repositories.score import ScoreRepository
from app.repositories.stock import StockRepository

logger = logging.getLogger(__name__)


class ExpectedReturnsCalculator:
    """Calculate expected returns for portfolio optimization."""

    def __init__(
        self,
        calc_repo: Optional[CalculationsRepository] = None,
        score_repo: Optional[ScoreRepository] = None,
        stock_repo: Optional[StockRepository] = None,
    ):
        self._calc_repo = calc_repo or CalculationsRepository()
        self._score_repo = score_repo or ScoreRepository()
        self._stock_repo = stock_repo or StockRepository()

    async def calculate_expected_returns(
        self,
        symbols: List[str],
        target_return: float = OPTIMIZER_TARGET_RETURN,
        dividend_bonuses: Optional[Dict[str, float]] = None,
        regime: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Calculate expected returns for a list of symbols.

        Args:
            symbols: List of stock symbols
            target_return: Target annual return (default 11%)
            dividend_bonuses: Optional dict of pending dividend bonuses per symbol
            regime: Market regime ("bull", "bear", "sideways", or None for default)

        Returns:
            Dict mapping symbol to expected annual return (as decimal, e.g., 0.11 = 11%)
        """
        dividend_bonuses = dividend_bonuses or {}
        expected_returns = {}

        for symbol in symbols:
            try:
                exp_return = await self._calculate_single(
                    symbol,
                    target_return,
                    dividend_bonuses.get(symbol, 0.0),
                    regime=regime,
                )
                if exp_return is not None:
                    expected_returns[symbol] = exp_return
            except Exception as e:
                logger.warning(f"Error calculating expected return for {symbol}: {e}")

        logger.info(
            f"Calculated expected returns for {len(expected_returns)} symbols "
            f"(regime: {regime or 'default'})"
        )
        return expected_returns

    async def _calculate_single(
        self,
        symbol: str,
        target_return: float,
        dividend_bonus: float,
        regime: Optional[str] = None,
    ) -> Optional[float]:
        """
        Calculate expected return for a single symbol.

        Formula (default/sideways):
            base_return = (cagr * 0.70) + (target * score_factor * 0.30)

        Formula (bull):
            base_return = (cagr * 0.80) + (target * score_factor * 0.20)

        Formula (bear):
            base_return = (cagr * 0.70) + (target * score_factor * 0.30)
            base_return = base_return * 0.75  # Reduce by 25% (20-30% range)

        Then:
            adjusted = base_return * priority_multiplier
            final = adjusted + dividend_bonus
            return clamp(final, -0.10, 0.30)
        """
        # Get CAGR (prefer 5Y, fallback to 10Y)
        metrics = await self._calc_repo.get_metrics(
            symbol, ["CAGR_5Y", "CAGR_10Y", "DIVIDEND_YIELD"]
        )
        cagr = metrics.get("CAGR_5Y") or metrics.get("CAGR_10Y")
        dividend_yield = metrics.get("DIVIDEND_YIELD") or 0.0

        if cagr is None:
            logger.debug(f"No CAGR data for {symbol}, skipping")
            return None

        # Add dividend yield to CAGR for total return
        total_return_cagr = cagr + dividend_yield

        # Get stock score (0-1 range)
        score = await self._score_repo.get_by_symbol(symbol)
        stock_score = score.total_score if score else 0.5

        # Score factor: score=0.5 means neutral, higher means boost
        # score=1.0 → factor=2.0 (double the target contribution)
        # score=0.5 → factor=1.0 (neutral)
        # score=0.0 → factor=0.0 (no target contribution)
        if stock_score is None or stock_score <= 0:
            score_factor = 0.0
        else:
            score_factor = stock_score / 0.5

        # Adjust weights based on market regime
        if regime == "bull":
            # Bull market: 80% CAGR, 20% score-adjusted (more optimistic)
            cagr_weight = 0.80
            score_weight = 0.20
            regime_reduction = 1.0  # No reduction
        elif regime == "bear":
            # Bear market: 70% CAGR, 30% score-adjusted, then reduce by 25%
            cagr_weight = EXPECTED_RETURNS_CAGR_WEIGHT  # 0.70
            score_weight = EXPECTED_RETURNS_SCORE_WEIGHT  # 0.30
            regime_reduction = 0.75  # Reduce by 25% (middle of 20-30% range)
        else:
            # Sideways or default: 70% CAGR, 30% score-adjusted
            cagr_weight = EXPECTED_RETURNS_CAGR_WEIGHT  # 0.70
            score_weight = EXPECTED_RETURNS_SCORE_WEIGHT  # 0.30
            regime_reduction = 1.0  # No reduction

        # Calculate base expected return
        base_return = (
            total_return_cagr * cagr_weight
            + target_return * score_factor * score_weight
        )

        # Apply regime reduction (for bear markets)
        base_return = base_return * regime_reduction

        # Apply user preference multiplier
        stock = await self._stock_repo.get_by_symbol(symbol)
        multiplier = stock.priority_multiplier if stock else 1.0
        adjusted_return = base_return * multiplier

        # Add pending dividend bonus (DRIP fallback)
        final_return = adjusted_return + dividend_bonus

        # Clamp to reasonable range
        clamped = max(EXPECTED_RETURN_MIN, min(EXPECTED_RETURN_MAX, final_return))

        logger.debug(
            f"{symbol}: CAGR={cagr:.2%}, div={dividend_yield:.2%}, "
            f"score={stock_score:.2f}, mult={multiplier:.2f}, "
            f"regime={regime or 'default'}, reduction={regime_reduction:.2f}, "
            f"bonus={dividend_bonus:.2%}, expected={clamped:.2%}"
        )

        return clamped

    async def get_symbols_with_data(self, symbols: List[str]) -> List[str]:
        """
        Filter symbols to only those with sufficient data for optimization.

        Returns:
            List of symbols that have CAGR data available
        """
        valid_symbols = []

        for symbol in symbols:
            metrics = await self._calc_repo.get_metrics(symbol, ["CAGR_5Y", "CAGR_10Y"])
            if (
                metrics.get("CAGR_5Y") is not None
                or metrics.get("CAGR_10Y") is not None
            ):
                valid_symbols.append(symbol)

        logger.info(f"Found {len(valid_symbols)}/{len(symbols)} symbols with CAGR data")
        return valid_symbols
