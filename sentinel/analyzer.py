"""
Analyzer - Multi-scale pattern analysis for securities.

Uses wavelet decomposition to analyze price movements at different time scales:
- Long-term trend (years)
- Medium-term cycles (months)
- Short-term fluctuations (weeks)

Usage:
    analyzer = Analyzer()
    motion = await analyzer.analyze('AAPL.US')
    print(motion.trend_direction)  # 'up', 'down', 'flat'
    print(motion.momentum)  # -1.0 to 1.0
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pywt
from scipy import stats

from sentinel.cache import Cache
from sentinel.database import Database
from sentinel.security import Security

# Module-level cache for Motion objects (24h TTL)
_motion_cache: Cache = Cache("motion", ttl_seconds=86400)


@dataclass
class Motion:
    """Represents the analyzed motion/behavior of a security."""

    symbol: str

    # Trend (long-term direction)
    trend_direction: str  # 'up', 'down', 'flat'
    trend_strength: float  # 0.0 to 1.0

    # Momentum (medium-term)
    momentum: float  # -1.0 (strong down) to 1.0 (strong up)

    # Cycle position (mean reversion signal)
    # Negative = below average (buy signal), Positive = above average (sell signal)
    cycle_position: float  # How far from moving average as % (-1 to +1 normalized)
    cycle_position_raw: float  # Actual % deviation from MA

    # Volatility
    volatility: float  # annualized volatility
    volatility_trend: str  # 'increasing', 'decreasing', 'stable'

    # Consistency
    consistency: float  # 0.0 to 1.0 (how smooth is the movement)

    # Multi-scale components
    long_term_component: np.ndarray  # ~years
    medium_term_component: np.ndarray  # ~months
    short_term_component: np.ndarray  # ~weeks
    noise_component: np.ndarray  # daily noise

    # Derived metrics
    cagr: float  # Compound Annual Growth Rate
    sharpe: float  # Sharpe ratio (annualized)
    max_drawdown: float  # Maximum drawdown

    # Expected return (the key metric for investment decisions)
    expected_return: float  # Combined quality + cycle + momentum


class Analyzer:
    """Analyzes securities using multi-scale wavelet decomposition."""

    def __init__(self, db=None):
        self._db = db if db is not None else Database()
        self._cache = _motion_cache

    async def analyze(self, symbol: str, years: int = 10, use_cache: bool = True) -> Optional[Motion]:
        """
        Perform multi-scale analysis on a security.

        Args:
            symbol: Security symbol
            years: Years of history to analyze
            use_cache: Whether to use cached results (default True)

        Returns:
            Motion object with analysis results, or None if insufficient data
        """
        # Check cache first
        if use_cache:
            cached = self._cache.get(symbol)
            if cached is not None:
                return cached

        # Get historical prices
        security = Security(symbol, db=self._db)
        prices = await security.get_historical_prices(days=years * 252)

        if len(prices) < 252:  # Need at least 1 year
            return None

        # Extract close prices (oldest first)
        closes = np.array([p["close"] for p in reversed(prices)])

        # Calculate log returns
        returns = np.diff(np.log(closes))

        # Perform wavelet decomposition
        components = self._decompose(closes)

        # Calculate metrics
        trend_dir, trend_str = self._analyze_trend(components["long_term"])
        momentum = self._calculate_momentum(components["medium_term"])
        cycle_pos, cycle_pos_raw = self._calculate_cycle_position(closes)
        vol, vol_trend = self._analyze_volatility(returns)
        consistency = self._calculate_consistency(closes, components)
        cagr = self._calculate_cagr(closes)
        sharpe = self._calculate_sharpe(returns)
        max_dd = self._calculate_max_drawdown(closes)

        # Calculate expected return (the main investment signal)
        expected_return = await self._calculate_expected_return(
            symbol=symbol,
            cagr=cagr,
            sharpe=sharpe,
            cycle_position=cycle_pos,
            momentum=momentum,
            consistency=consistency,
        )

        motion = Motion(
            symbol=symbol,
            trend_direction=trend_dir,
            trend_strength=trend_str,
            momentum=momentum,
            cycle_position=cycle_pos,
            cycle_position_raw=cycle_pos_raw,
            volatility=vol,
            volatility_trend=vol_trend,
            consistency=consistency,
            long_term_component=components["long_term"],
            medium_term_component=components["medium_term"],
            short_term_component=components["short_term"],
            noise_component=components["noise"],
            cagr=cagr,
            sharpe=sharpe,
            max_drawdown=max_dd,
            expected_return=expected_return,
        )

        # Store in cache
        if use_cache:
            self._cache.set(symbol, motion)

        return motion

    def _decompose(self, prices: np.ndarray) -> dict:
        """
        Decompose price series into multi-scale components using wavelets.

        Uses Daubechies wavelet (db4) with level 4 decomposition:
        - Level 4 approximation: Long-term trend (~years)
        - Level 3 details: Medium-term cycles (~quarters)
        - Level 2 details: Short-term movements (~months)
        - Level 1 details: Weekly fluctuations
        - Residual: Daily noise
        """
        # Pad to power of 2 for cleaner decomposition
        n = len(prices)
        next_pow2 = 2 ** int(np.ceil(np.log2(n)))
        padded = np.pad(prices, (0, next_pow2 - n), mode="edge")

        # Perform wavelet decomposition
        wavelet = "db4"
        level = 4
        coeffs = pywt.wavedec(padded, wavelet, level=level)

        # Reconstruct each component
        def reconstruct_level(coeffs, level_idx, total_levels):
            """Reconstruct signal from a specific decomposition level."""
            new_coeffs = [np.zeros_like(c) for c in coeffs]
            new_coeffs[level_idx] = coeffs[level_idx]
            return pywt.waverec(new_coeffs, wavelet)[:n]

        # Approximation (trend) + details at each level
        long_term = pywt.waverec([coeffs[0]] + [np.zeros_like(c) for c in coeffs[1:]], wavelet)[:n]
        medium_term = reconstruct_level(coeffs, 1, level)  # cD4
        short_term = reconstruct_level(coeffs, 2, level)  # cD3
        weekly = reconstruct_level(coeffs, 3, level)  # cD2
        noise = reconstruct_level(coeffs, 4, level)  # cD1

        return {
            "long_term": long_term,
            "medium_term": medium_term,
            "short_term": short_term + weekly,
            "noise": noise,
        }

    def _analyze_trend(self, long_term: np.ndarray) -> tuple[str, float]:
        """Analyze the long-term trend direction and strength."""
        # Linear regression on the trend component
        x = np.arange(len(long_term))
        regress_result = stats.linregress(x, long_term)
        slope = float(regress_result[0])  # type: ignore[arg-type]  # slope
        r_value = float(regress_result[2])  # type: ignore[arg-type]  # rvalue

        # Normalize slope by average value
        avg_val = float(np.mean(np.abs(long_term)))
        normalized_slope = 0.0
        if avg_val > 0:
            normalized_slope = slope / avg_val * 252  # Annualize

        # Determine direction
        if normalized_slope > 0.05:
            direction = "up"
        elif normalized_slope < -0.05:
            direction = "down"
        else:
            direction = "flat"

        # Strength is R-squared (how well the line fits)
        strength = r_value**2

        return direction, strength

    def _calculate_momentum(self, medium_term: np.ndarray) -> float:
        """
        Calculate momentum from medium-term component.
        Returns value from -1.0 to 1.0.
        """
        if len(medium_term) < 63:  # Need ~quarter
            return 0.0

        # Recent vs earlier medium-term movement
        recent = medium_term[-63:]  # Last quarter
        earlier = medium_term[-126:-63]  # Previous quarter

        recent_change = (recent[-1] - recent[0]) / (np.abs(recent[0]) + 1e-10)
        earlier_change = (earlier[-1] - earlier[0]) / (np.abs(earlier[0]) + 1e-10)

        # Combine with acceleration
        momentum = recent_change * 0.7 + (recent_change - earlier_change) * 0.3

        # Clip to [-1, 1]
        return np.clip(momentum, -1.0, 1.0)

    def _analyze_volatility(self, returns: np.ndarray) -> tuple[float, str]:
        """Analyze volatility level and trend."""
        # Annualized volatility
        vol = np.std(returns) * np.sqrt(252)

        # Compare recent vs historical volatility
        if len(returns) >= 126:
            recent_vol = np.std(returns[-63:]) * np.sqrt(252)
            historical_vol = np.std(returns[-126:-63]) * np.sqrt(252)

            ratio = recent_vol / (historical_vol + 1e-10)
            if ratio > 1.2:
                trend = "increasing"
            elif ratio < 0.8:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return vol, trend

    def _calculate_consistency(self, prices: np.ndarray, components: dict) -> float:
        """
        Calculate how consistently the security follows its trend.
        High consistency = smooth movement along trend.
        """
        trend = components["long_term"]

        # Ratio of trend variance to total variance
        trend_var = np.var(trend)
        total_var = np.var(prices)

        if total_var == 0:
            return 0.0

        consistency = trend_var / total_var
        return float(np.clip(consistency, 0.0, 1.0))

    def _calculate_cagr(self, prices: np.ndarray) -> float:
        """Calculate Compound Annual Growth Rate."""
        if len(prices) < 2 or prices[0] <= 0:
            return 0.0

        years = len(prices) / 252
        if years < 0.1:
            return 0.0

        total_return = prices[-1] / prices[0]
        if total_return <= 0:
            return 0.0

        cagr = (total_return ** (1 / years)) - 1
        return cagr

    def _calculate_sharpe(self, returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) < 20:
            return 0.0

        annual_return = np.mean(returns) * 252
        annual_vol = np.std(returns) * np.sqrt(252)

        if annual_vol < 1e-10:
            return 0.0

        return (annual_return - risk_free_rate) / annual_vol

    def _calculate_max_drawdown(self, prices: np.ndarray) -> float:
        """Calculate maximum drawdown."""
        peak = prices[0]
        max_dd = 0.0

        for price in prices:
            if price > peak:
                peak = price
            dd = (peak - price) / peak
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def _calculate_cycle_position(self, prices: np.ndarray) -> tuple[float, float]:
        """
        Advanced mean reversion oracle using multi-component analysis.

        This is the MEAN REVERSION signal:
        - Negative = price below average → expect price to go UP (buying opportunity)
        - Positive = price above average → expect price to come DOWN

        Uses sophisticated analysis:
        1. Volatility-adjusted Z-score (not raw deviation)
        2. Reversion velocity (is bounce starting?)
        3. Multi-timeframe alignment (do all MAs agree?)
        4. Historical mean reversion personality
        5. Half-life analysis (how fast does it revert?)

        Returns:
            (normalized_position, raw_position_pct)
            normalized: -1 to +1, sophisticated mean reversion signal
            raw: simple % deviation for backward compatibility
        """
        if len(prices) < 200:
            return 0.0, 0.0

        current_price = prices[-1]

        # Component 1: Volatility-adjusted Z-score (40% weight)
        z_score = self._calculate_z_score(prices)
        base_signal = -z_score  # Invert: negative Z = oversold = buy signal
        base_signal = np.clip(base_signal / 2.5, -1.0, 1.0)  # Normalize (Z=2.5 → signal=1.0)

        # Component 2: Reversion velocity (20% weight)
        velocity_boost = self._calculate_reversion_velocity(prices, z_score)

        # Component 3: Multi-timeframe alignment (15% weight)
        alignment_score = self._calculate_timeframe_alignment(prices)

        # Component 4: Mean reversion personality (15% weight)
        mr_personality = self._calculate_mr_personality(prices)

        # Component 5: Half-life time factor (10% weight)
        time_factor = self._calculate_time_factor(prices)

        # Combine all components
        sophisticated_signal = (
            0.40 * base_signal
            + 0.20 * velocity_boost
            + 0.15 * alignment_score
            + 0.15 * mr_personality
            + 0.10 * time_factor
        )

        sophisticated_signal = np.clip(sophisticated_signal, -1.0, 1.0)

        # Raw deviation for backward compatibility (simple MA deviation)
        ma_200 = np.mean(prices[-200:])
        raw_deviation = (current_price - ma_200) / ma_200

        return sophisticated_signal, raw_deviation * 100

    def _calculate_z_score(self, prices: np.ndarray) -> float:
        """
        Calculate volatility-adjusted Z-score.

        Z-score tells us how many standard deviations price is from its mean.
        This automatically adjusts for each security's volatility personality.

        Returns:
            Z-score (typically -3 to +3)
            Negative = below mean, Positive = above mean
        """
        if len(prices) < 50:
            return 0.0

        # Use exponential moving average (recent data weighted more)
        # Lookback adapts to available data
        lookback = min(200, len(prices))
        weights = np.exp(np.linspace(-1, 0, lookback))
        weights = weights / weights.sum()

        recent_prices = prices[-lookback:]
        ema = np.average(recent_prices, weights=weights)

        # Standard deviation over same period
        std_dev = np.std(recent_prices)

        if std_dev < 1e-10:
            return 0.0

        current_price = prices[-1]
        z_score = (current_price - ema) / std_dev

        return np.clip(z_score, -3.0, 3.0)

    def _calculate_reversion_velocity(self, prices: np.ndarray, z_score: float) -> float:
        """
        Calculate if mean reversion is already starting.

        Not just WHERE price is, but which DIRECTION it's moving.
        If oversold AND starting to rise → reversion beginning (strong signal)
        If oversold but still falling → reversion not started (weaker signal)

        Returns:
            Velocity boost: -1.0 to +1.0
        """
        if len(prices) < 10:
            return 0.0

        # Calculate price velocity (recent direction)
        lookback = min(5, len(prices) - 1)
        recent_change = (prices[-1] - prices[-(lookback + 1)]) / prices[-(lookback + 1)]

        # Normalize velocity (typically ±5% over 5 days)
        normalized_velocity = np.clip(recent_change / 0.05, -1.0, 1.0)

        # Check if reversion is starting
        # If Z < 0 (oversold) and velocity > 0 (rising) → reversion starting
        # If Z > 0 (overbought) and velocity < 0 (falling) → reversion starting
        if z_score < -0.5 and normalized_velocity > 0:
            # Oversold and bouncing
            return normalized_velocity * (abs(z_score) / 2.0)  # Stronger signal if more oversold
        elif z_score > 0.5 and normalized_velocity < 0:
            # Overbought and falling
            return normalized_velocity * (abs(z_score) / 2.0)
        else:
            # No clear reversion starting
            return normalized_velocity * 0.3  # Weak contribution

    def _calculate_timeframe_alignment(self, prices: np.ndarray) -> float:
        """
        Check if multiple timeframes agree on over/undervaluation.

        Stronger signal when price is below ALL moving averages (oversold across all timeframes)
        or above ALL moving averages (overbought across all timeframes).

        Returns:
            Alignment score: -1.0 (all agree overbought) to +1.0 (all agree oversold)
        """
        if len(prices) < 200:
            return 0.0

        current_price = prices[-1]

        # Multiple timeframes (adaptive to data availability)
        timeframes = [20, 50, 100, 200]
        timeframes = [tf for tf in timeframes if len(prices) >= tf]

        if not timeframes:
            return 0.0

        # Count how many MAs we're below
        below_count = 0
        for tf in timeframes:
            ma = np.mean(prices[-tf:])
            if current_price < ma:
                below_count += 1

        # Convert to score
        # All below (oversold) = +1.0, All above (overbought) = -1.0
        alignment_ratio = below_count / len(timeframes)
        alignment_score = (alignment_ratio - 0.5) * 2.0  # Map [0,1] → [-1,1]

        return alignment_score

    def _calculate_mr_personality(self, prices: np.ndarray) -> float:
        """
        Calculate this security's historical mean reversion tendency.

        Does THIS security actually exhibit mean reversion?
        Some securities are strong mean-reverters, others are momentum-driven.

        Returns:
            Personality score: -1.0 to +1.0
            High positive = strong mean reversion history
        """
        if len(prices) < 252:  # Need at least 1 year
            return 0.0

        # Calculate Z-scores over historical data
        lookback = min(252, len(prices))

        # Check multiple historical periods
        reversion_successes = 0
        total_tests = 0

        # Slide through history, check if oversold → rose, overbought → fell
        window = 50
        forward_period = 20  # Check 20 days ahead

        for i in range(lookback, len(prices) - forward_period, 10):  # Every 10 days
            if i < window:
                continue

            # Calculate Z-score at this point
            historical_window = prices[i - window : i]
            mean = np.mean(historical_window)
            std = np.std(historical_window)

            if std < 1e-10:
                continue

            z = (prices[i] - mean) / std

            # Check if reversion happened
            future_return = (prices[i + forward_period] - prices[i]) / prices[i]

            # If oversold (Z < -1), did it rise?
            if z < -1.0 and future_return > 0:
                reversion_successes += 1
                total_tests += 1
            # If overbought (Z > 1), did it fall?
            elif z > 1.0 and future_return < 0:
                reversion_successes += 1
                total_tests += 1
            # If extreme position taken, count even if no reversion
            elif abs(z) > 1.0:
                total_tests += 1

        if total_tests < 3:  # Need some data
            return 0.0

        # Success rate → personality score
        success_rate = reversion_successes / total_tests

        # Map [0, 1] → [-1, 1], with 0.5 (random) mapping to 0
        personality = (success_rate - 0.5) * 2.0

        return np.clip(personality, -1.0, 1.0)

    def _calculate_time_factor(self, prices: np.ndarray) -> float:
        """
        Calculate mean reversion speed (half-life).

        Fast-reverting securities (quick half-life) are better trading opportunities.
        Slow-reverting securities take too long to be actionable.

        Returns:
            Time factor: 0.0 (very slow) to 1.0 (very fast)
        """
        if len(prices) < 100:
            return 0.5  # Neutral if insufficient data

        # Calculate how quickly deviations from MA decay
        # Use autocorrelation of deviations
        lookback = min(200, len(prices))
        recent = prices[-lookback:]

        ma = np.mean(recent)
        deviations = recent - ma

        # Calculate autocorrelation at different lags
        # High autocorrelation at lag 20 = slow mean reversion
        # Low autocorrelation at lag 20 = fast mean reversion
        try:
            # Autocorrelation at 20-day lag
            if len(deviations) < 30:
                return 0.5

            acf_20 = np.corrcoef(deviations[:-20], deviations[20:])[0, 1]

            # High autocorrelation = slow reversion (low score)
            # Low autocorrelation = fast reversion (high score)
            # Map correlation [1.0, 0.0] → time_factor [0.0, 1.0]
            time_factor = 1.0 - max(0.0, acf_20)

            return np.clip(time_factor, 0.0, 1.0)
        except Exception:
            return 0.5  # Neutral if calculation fails

    async def _calculate_expected_return(
        self,
        symbol: str,
        cagr: float,
        sharpe: float,
        cycle_position: float,
        momentum: float,
        consistency: float,
    ) -> float:
        """
        Calculate expected return - THE primary investment signal.

        Model: expected_return = quality + mean_reversion + momentum

        Components:
        1. Quality (30%): Long-term CAGR adjusted by Sharpe
           - Good CAGR with good Sharpe = quality company

        2. Cycle Position (40%): Mean reversion opportunity
           - NEGATIVE cycle_position = price below average = expect it to go UP
           - This is INVERTED: cycle_position is how far ABOVE average we are
           - So: mean_reversion_signal = -cycle_position

        3. Momentum (20%): Recent price trend
           - Positive momentum = continuing upward
           - BUT: extreme positive momentum at high cycle position = overextended

        4. Consistency (10%): How smooth the movement is
           - Smoother = more predictable

        Returns:
            Expected return score, higher = better investment opportunity
        """
        # Quality score (long-term fundamental strength)
        # CAGR typically ranges -20% to +30%, normalize to roughly [-1, 1]
        cagr_score = np.clip(cagr / 0.15, -1.0, 1.0)

        # Sharpe typically ranges -1 to 3, normalize
        sharpe_score = np.clip(sharpe / 2.0, -0.5, 1.0)

        # Combined quality = CAGR weighted by Sharpe
        quality = 0.6 * cagr_score + 0.4 * sharpe_score

        # Mean reversion signal - INVERT cycle position
        # If price is BELOW average (cycle_position < 0), expect it to go UP
        # This creates the buying opportunity signal
        mean_reversion = -cycle_position

        # Momentum - but dampen when cycle position is extreme
        # If we're very high (cycle_position > 0.5) and momentum is positive,
        # that's overextension, not a good sign
        if cycle_position > 0.3 and momentum > 0:
            # Dampen positive momentum when we're already high
            adjusted_momentum = momentum * 0.5
        elif cycle_position < -0.3 and momentum < 0:
            # When we're low and momentum is negative,
            # the negative momentum matters less (mean reversion will help)
            adjusted_momentum = momentum * 0.5
        else:
            adjusted_momentum = momentum

        # Consistency bonus (smooth movers are more predictable)
        consistency_bonus = (consistency - 0.5) * 0.2  # ±0.1 contribution

        # Base expected return
        expected_return = (
            0.30 * quality
            + 0.40 * mean_reversion
            + 0.20 * adjusted_momentum
            + 0.10 * (consistency_bonus + 0.5)  # Shift to positive range
        )

        # Apply regime adjustment if enabled
        from sentinel.settings import Settings

        settings = Settings()
        use_regime = await settings.get("use_regime_adjustment", False)

        if use_regime:
            from sentinel.regime_hmm import RegimeDetector

            detector = RegimeDetector()
            regime_data = await detector.detect_current_regime(symbol)

            # Adjust component weights based on regime
            if regime_data["regime_name"] == "Bull":
                # Boost momentum, reduce mean reversion
                expected_return = (
                    0.30 * quality
                    + 0.30 * mean_reversion  # Reduce from 40%
                    + 0.30 * adjusted_momentum  # Increase from 20%
                    + 0.10 * (consistency_bonus + 0.5)
                )
            elif regime_data["regime_name"] == "Bear":
                # Boost quality, reduce momentum
                expected_return = (
                    0.40 * quality  # Increase from 30%
                    + 0.40 * mean_reversion
                    + 0.10 * adjusted_momentum  # Reduce from 20%
                    + 0.10 * (consistency_bonus + 0.5)
                )
            # Sideways: keep default weights

        return expected_return

    async def calculate_score(self, symbol: str) -> Optional[float]:
        """
        Calculate the investment opportunity score for a security.

        This is the EXPECTED RETURN - the primary signal for investment decisions.
        Higher = better opportunity to invest.

        The expected return incorporates:
        - Quality: Long-term CAGR and Sharpe ratio
        - Cycle Position: Mean reversion opportunity (buy low, sell high)
        - Momentum: Recent price trend
        - Consistency: Predictability of movements
        """
        motion = await self.analyze(symbol)
        if not motion:
            return None

        # The expected_return is already calculated in analyze()
        return motion.expected_return

    async def analyze_all(self) -> dict[str, Motion]:
        """Analyze all active securities in the universe."""
        securities = await self._db.get_all_securities(active_only=True)

        results = {}
        for sec in securities:
            motion = await self.analyze(sec["symbol"])
            if motion:
                results[sec["symbol"]] = motion

        return results

    async def update_scores(self, use_cache: bool = False) -> int:
        """
        Calculate and store scores for all securities.

        Args:
            use_cache: Whether to use cached analysis (default False for fresh calculations)
        """
        # Clear cache before recalculating to ensure fresh data
        if not use_cache:
            self._cache.clear()

        securities = await self._db.get_all_securities(active_only=True)

        count = 0
        for sec in securities:
            motion = await self.analyze(sec["symbol"], use_cache=use_cache)
            if motion is not None:
                security = Security(sec["symbol"], db=self._db)
                components = {
                    "trend": motion.trend_direction,
                    "trend_strength": motion.trend_strength,
                    "momentum": motion.momentum,
                    "cycle_position": motion.cycle_position,
                    "cycle_position_pct": motion.cycle_position_raw,
                    "expected_return": motion.expected_return,
                    "sharpe": motion.sharpe,
                    "cagr": motion.cagr,
                    "consistency": motion.consistency,
                    "max_drawdown": motion.max_drawdown,
                    "volatility": motion.volatility,
                }
                await security.set_score(motion.expected_return, components)
                count += 1

        return count

    def invalidate_cache(self, symbol: str | None = None) -> int:
        """
        Invalidate cached analysis results.

        Args:
            symbol: Specific symbol to invalidate, or None to clear all

        Returns:
            Number of entries removed
        """
        if symbol:
            return 1 if self._cache.invalidate(symbol) else 0
        return self._cache.clear()

    def cache_stats(self) -> dict:
        """Get cache statistics."""
        return self._cache.stats()
