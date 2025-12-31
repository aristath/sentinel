"""
Expected Returns Calculator.

Calculates expected returns for each security by blending:
- Historical CAGR (70% default, 80% in bull, 70% in sideways)
- Score-adjusted target return (30% default, 20% in bull, 30% in sideways)
- Market regime adjustment (bear: reduce by 20-30%)
- Forward-looking market indicators (VIX, yield curve, market P/E)
- User preference multiplier (priority_multiplier)
- Pending dividend bonus (DRIP fallback)
"""

import logging
from typing import Dict, List, Optional

from app.infrastructure.external.yahoo import market_indicators
from app.modules.scoring.domain.constants import (
    EXPECTED_RETURN_MAX,
    EXPECTED_RETURN_MIN,
    EXPECTED_RETURNS_CAGR_WEIGHT,
    EXPECTED_RETURNS_SCORE_WEIGHT,
    OPTIMIZER_TARGET_RETURN,
    PE_ADJUSTMENT_MAX,
    PE_CHEAP,
    PE_EXPENSIVE,
    PE_FAIR,
    VIX_ADJUSTMENT_MAX,
    VIX_HIGH,
    VIX_LOW,
    YIELD_CURVE_ADJUSTMENT_MAX,
    YIELD_CURVE_INVERTED,
    YIELD_CURVE_NORMAL,
)
from app.modules.universe.database.security_repository import SecurityRepository
from app.repositories.calculations import CalculationsRepository
from app.repositories.score import ScoreRepository

logger = logging.getLogger(__name__)


class ExpectedReturnsCalculator:
    """Calculate expected returns for portfolio optimization."""

    def __init__(
        self,
        calc_repo: Optional[CalculationsRepository] = None,
        score_repo: Optional[ScoreRepository] = None,
        security_repo: Optional[SecurityRepository] = None,
    ):
        self._calc_repo = calc_repo or CalculationsRepository()
        self._score_repo = score_repo or ScoreRepository()
        self._stock_repo = security_repo or SecurityRepository()

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
            symbols: List of security symbols
            target_return: Target annual return (default 11%)
            dividend_bonuses: Optional dict of pending dividend bonuses per symbol
            regime: Market regime ("bull", "bear", "sideways", or None for default)

        Returns:
            Dict mapping symbol to expected annual return (as decimal, e.g., 0.11 = 11%)
        """
        dividend_bonuses = dividend_bonuses or {}
        expected_returns = {}

        # Calculate forward-looking market indicator adjustments (once for all symbols)
        forward_adjustment = await self._calculate_forward_looking_adjustment()

        for symbol in symbols:
            try:
                exp_return = await self._calculate_single(
                    symbol,
                    target_return,
                    dividend_bonuses.get(symbol, 0.0),
                    regime=regime,
                    forward_adjustment=forward_adjustment,
                )
                if exp_return is not None:
                    expected_returns[symbol] = exp_return
            except Exception as e:
                logger.warning(f"Error calculating expected return for {symbol}: {e}")

        logger.info(
            f"Calculated expected returns for {len(expected_returns)} symbols "
            f"(regime: {regime or 'default'}, forward adjustment: {forward_adjustment*100:+.1f}%)"
        )
        return expected_returns

    async def _calculate_forward_looking_adjustment(self) -> float:
        """
        Calculate forward-looking market indicator adjustment.

        Combines adjustments from:
        - VIX (volatility/fear): High VIX = reduce expectations
        - Yield curve slope: Inverted = reduce expectations
        - Market P/E: High P/E = reduce expectations

        Returns:
            Adjustment factor (e.g., -0.05 = reduce by 5%, +0.05 = increase by 5%)
        """
        try:
            # Get market indicators
            vix = await market_indicators.get_vix()
            yields = await market_indicators.get_treasury_yields()
            yield_slope = market_indicators.calculate_yield_curve_slope(yields)
            market_pe = await market_indicators.get_market_pe()

            total_adjustment = 0.0

            # VIX adjustment (high VIX = pessimistic)
            if vix is not None:
                if vix >= VIX_HIGH:
                    # Very high volatility: reduce by up to 10%
                    vix_adj = -VIX_ADJUSTMENT_MAX * min(1.0, (vix - VIX_HIGH) / 20.0)
                elif vix <= VIX_LOW:
                    # Low volatility: increase by up to 5%
                    vix_adj = VIX_ADJUSTMENT_MAX * 0.5 * (1.0 - (vix / VIX_LOW))
                else:
                    # Normal range: no adjustment
                    vix_adj = 0.0
                total_adjustment += vix_adj
                logger.debug(f"VIX adjustment: {vix_adj*100:+.1f}% (VIX={vix:.1f})")

            # Yield curve adjustment (inverted = recession signal)
            if yield_slope is not None:
                if yield_slope <= YIELD_CURVE_INVERTED:
                    # Inverted curve: reduce by up to 15%
                    curve_adj = -YIELD_CURVE_ADJUSTMENT_MAX * min(
                        1.0, abs(yield_slope) / 0.02
                    )
                elif yield_slope >= YIELD_CURVE_NORMAL:
                    # Normal/steep curve: slight increase
                    curve_adj = (
                        YIELD_CURVE_ADJUSTMENT_MAX
                        * 0.3
                        * min(1.0, (yield_slope - YIELD_CURVE_NORMAL) / 0.02)
                    )
                else:
                    # Flat curve: no adjustment
                    curve_adj = 0.0
                total_adjustment += curve_adj
                logger.debug(
                    f"Yield curve adjustment: {curve_adj*100:+.1f}% (slope={yield_slope*100:.2f}%)"
                )

            # Market P/E adjustment (high P/E = expensive market)
            if market_pe is not None:
                if market_pe >= PE_EXPENSIVE:
                    # Expensive market: reduce by up to 10%
                    pe_adj = -PE_ADJUSTMENT_MAX * min(
                        1.0, (market_pe - PE_EXPENSIVE) / (PE_EXPENSIVE * 0.5)
                    )
                elif market_pe <= PE_CHEAP:
                    # Cheap market: increase by up to 5%
                    pe_adj = (
                        PE_ADJUSTMENT_MAX
                        * 0.5
                        * (1.0 - (market_pe - PE_CHEAP) / (PE_FAIR - PE_CHEAP))
                    )
                else:
                    # Fair value: no adjustment
                    pe_adj = 0.0
                total_adjustment += pe_adj
                logger.debug(
                    f"Market P/E adjustment: {pe_adj*100:+.1f}% (P/E={market_pe:.1f})"
                )

            # Cap total adjustment at ±20% to avoid extreme adjustments
            total_adjustment = max(-0.20, min(0.20, total_adjustment))

            if total_adjustment != 0.0:
                vix_str = f"{vix:.1f}" if vix else "N/A"
                slope_str = f"{yield_slope*100:.2f}%" if yield_slope else "N/A"
                pe_str = f"{market_pe:.1f}" if market_pe else "N/A"
                logger.info(
                    f"Forward-looking adjustment: {total_adjustment*100:+.1f}% "
                    f"(VIX={vix_str}, slope={slope_str}, P/E={pe_str})"
                )

            return total_adjustment

        except Exception as e:
            logger.warning(f"Error calculating forward-looking adjustment: {e}")
            return 0.0

    async def _calculate_single(
        self,
        symbol: str,
        target_return: float,
        dividend_bonus: float,
        regime: Optional[str] = None,
        forward_adjustment: float = 0.0,
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

        # Get security score (0-1 range)
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

        # Apply forward-looking market indicator adjustment
        base_return = base_return * (1.0 + forward_adjustment)

        # Apply user preference multiplier
        security = await self._stock_repo.get_by_symbol(symbol)
        multiplier = security.priority_multiplier if security else 1.0
        adjusted_return = base_return * multiplier

        # Add pending dividend bonus (DRIP fallback)
        final_return = adjusted_return + dividend_bonus

        # Clamp to reasonable range
        clamped = max(EXPECTED_RETURN_MIN, min(EXPECTED_RETURN_MAX, final_return))

        logger.debug(
            f"{symbol}: CAGR={cagr:.2%}, div={dividend_yield:.2%}, "
            f"score={stock_score:.2f}, mult={multiplier:.2f}, "
            f"regime={regime or 'default'}, reduction={regime_reduction:.2f}, "
            f"forward={forward_adjustment*100:+.1f}%, "
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
