"""
Price Validator - Validates and interpolates abnormal price data.

Ported from sentinel2's internal/repositories/price_validator.go.

The validator:
1. Detects spikes (>1000% change) and crashes (<-90% change)
2. Checks if prices are >10x or <0.1x the rolling average
3. Validates OHLC consistency (High >= Low, etc.)
4. Interpolates invalid values using linear interpolation
5. Checks live prices for trade-blocking anomalies
"""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# Validation thresholds
MAX_PRICE_MULTIPLIER = 10.0  # Price > 10x average is abnormal
MIN_PRICE_MULTIPLIER = 0.1  # Price < 0.1x average is abnormal
MAX_PRICE_CHANGE_PCT = 1000.0  # >1000% change is a spike
MIN_PRICE_CHANGE_PCT = -90.0  # <-90% change is a crash
CONTEXT_WINDOW_DAYS = 30  # Use last 30 days for context


@dataclass
class OHLCValidation:
    """Tracks validity of each OHLC component."""

    open_valid: bool = True
    high_valid: bool = True
    low_valid: bool = True
    close_valid: bool = True
    reason: str = ""

    def needs_full_interpolation(self) -> bool:
        """Returns True when Close is invalid (Close is the anchor)."""
        return not self.close_valid

    def needs_interpolation(self) -> bool:
        """Returns True when any component is invalid."""
        return not (self.open_valid and self.high_valid and self.low_valid and self.close_valid)

    def all_valid(self) -> bool:
        """Returns True when all components are valid."""
        return self.open_valid and self.high_valid and self.low_valid and self.close_valid


class PriceValidator:
    """Validates and interpolates abnormal prices."""

    def validate_price(self, price: dict, previous_price: Optional[dict], context: list[dict]) -> OHLCValidation:
        """
        Validate each OHLC component independently.
        Returns OHLCValidation with per-component validity status.
        """
        result = OHLCValidation()
        close = price.get("close", 0)

        # Zero/negative Close indicates missing or invalid data
        if close <= 0:
            return OHLCValidation(
                open_valid=False, high_valid=False, low_valid=False, close_valid=False, reason="close_zero_or_negative"
            )

        high = price.get("high", close)
        low = price.get("low", close)
        open_price = price.get("open", close)

        # 1. OHLC consistency checks
        if high < low:
            result.high_valid = False
            result.low_valid = False
            result.reason = "high_below_low"
        if high < open_price:
            result.high_valid = False
            if not result.reason:
                result.reason = "high_below_open"
        if high < close:
            result.high_valid = False
            if not result.reason:
                result.reason = "high_below_close"
        if low > open_price:
            result.low_valid = False
            if not result.reason:
                result.reason = "low_above_open"
        if low > close:
            result.low_valid = False
            if not result.reason:
                result.reason = "low_above_close"

        # 2. Day-over-day change detection (spike/crash affects all components)
        if previous_price and previous_price.get("close", 0) > 0:
            prev_close = previous_price["close"]
            change_pct = ((close - prev_close) / prev_close) * 100.0

            if change_pct > MAX_PRICE_CHANGE_PCT:
                return OHLCValidation(
                    open_valid=False, high_valid=False, low_valid=False, close_valid=False, reason="spike_detected"
                )
            if change_pct < MIN_PRICE_CHANGE_PCT:
                return OHLCValidation(
                    open_valid=False, high_valid=False, low_valid=False, close_valid=False, reason="crash_detected"
                )

        # 3. Average-based validation (requires context)
        if context and result.close_valid:
            context_size = min(len(context), CONTEXT_WINDOW_DAYS)
            avg_price = sum(p["close"] for p in context[:context_size]) / context_size

            if close > avg_price * MAX_PRICE_MULTIPLIER:
                return OHLCValidation(
                    open_valid=False, high_valid=False, low_valid=False, close_valid=False, reason="price_too_high"
                )
            if close < avg_price * MIN_PRICE_MULTIPLIER:
                return OHLCValidation(
                    open_valid=False, high_valid=False, low_valid=False, close_valid=False, reason="price_too_low"
                )

        return result

    def interpolate_price(
        self, price: dict, validation: OHLCValidation, before: list[dict], after: list[dict]
    ) -> tuple[dict, str]:
        """
        Interpolate invalid components of a price.
        Returns (interpolated_price, method).
        """
        interpolated = price.copy()

        # If Close is invalid, we need full interpolation
        if not validation.close_valid:
            return self._interpolate_full(price, before, after)

        # Selective interpolation - only fix invalid components
        method = "selective"

        if not validation.high_valid:
            ratio = self._get_typical_high_close_ratio(before, after)
            interpolated["high"] = interpolated["close"] * ratio

        if not validation.low_valid:
            ratio = self._get_typical_low_close_ratio(before, after)
            interpolated["low"] = interpolated["close"] * ratio

        if not validation.open_valid:
            if before:
                interpolated["open"] = before[0]["close"]
            elif after:
                interpolated["open"] = after[0].get("open", after[0]["close"])
            else:
                interpolated["open"] = interpolated["close"]

        self._ensure_ohlc_consistency(interpolated)
        return interpolated, method

    def _interpolate_full(self, price: dict, before: list[dict], after: list[dict]) -> tuple[dict, str]:
        """Perform full interpolation when Close is invalid."""
        interpolated = price.copy()

        # Linear interpolation if both before and after available
        if before and after:
            before_close = before[0]["close"]
            after_close = after[0]["close"]
            # Simple midpoint interpolation
            interpolated["close"] = (before_close + after_close) / 2.0

            # Use ratios for other components
            open_ratio = (
                before[0].get("open", before_close) / before_close + after[0].get("open", after_close) / after_close
            ) / 2.0
            high_ratio = (
                before[0].get("high", before_close) / before_close + after[0].get("high", after_close) / after_close
            ) / 2.0
            low_ratio = (
                before[0].get("low", before_close) / before_close + after[0].get("low", after_close) / after_close
            ) / 2.0

            interpolated["open"] = interpolated["close"] * open_ratio
            interpolated["high"] = interpolated["close"] * high_ratio
            interpolated["low"] = interpolated["close"] * low_ratio

            self._ensure_ohlc_consistency(interpolated)
            return interpolated, "linear"

        # Forward fill
        if before:
            interpolated["close"] = before[0]["close"]
            interpolated["open"] = before[0].get("open", before[0]["close"])
            interpolated["high"] = before[0].get("high", before[0]["close"])
            interpolated["low"] = before[0].get("low", before[0]["close"])
            return interpolated, "forward_fill"

        # Backward fill
        if after:
            interpolated["close"] = after[0]["close"]
            interpolated["open"] = after[0].get("open", after[0]["close"])
            interpolated["high"] = after[0].get("high", after[0]["close"])
            interpolated["low"] = after[0].get("low", after[0]["close"])
            return interpolated, "backward_fill"

        self._ensure_ohlc_consistency(interpolated)
        return interpolated, "no_interpolation"

    def _get_typical_high_close_ratio(self, before: list[dict], after: list[dict]) -> float:
        """Get typical High/Close ratio from surrounding prices."""
        ratios = []

        if before and before[0].get("close", 0) > 0:
            ratios.append(before[0].get("high", before[0]["close"]) / before[0]["close"])
        if after and after[0].get("close", 0) > 0:
            ratios.append(after[0].get("high", after[0]["close"]) / after[0]["close"])

        if not ratios:
            return 1.02  # Default: High is 2% above Close

        return sum(ratios) / len(ratios)

    def _get_typical_low_close_ratio(self, before: list[dict], after: list[dict]) -> float:
        """Get typical Low/Close ratio from surrounding prices."""
        ratios = []

        if before and before[0].get("close", 0) > 0:
            ratios.append(before[0].get("low", before[0]["close"]) / before[0]["close"])
        if after and after[0].get("close", 0) > 0:
            ratios.append(after[0].get("low", after[0]["close"]) / after[0]["close"])

        if not ratios:
            return 0.98  # Default: Low is 2% below Close

        return sum(ratios) / len(ratios)

    def _ensure_ohlc_consistency(self, price: dict) -> None:
        """Ensure OHLC consistency."""
        close = price.get("close", 0)
        open_price = price.get("open", close)
        high = price.get("high", close)
        low = price.get("low", close)

        # Ensure High >= all
        price["high"] = max(high, open_price, close)

        # Ensure Low <= all
        price["low"] = min(low, open_price, close)

        # Ensure High >= Low
        if price["high"] < price["low"]:
            price["high"] = price["low"]

    def validate_and_interpolate(self, prices: list[dict]) -> list[dict]:
        """
        Validate all prices and interpolate abnormal ones.
        Input prices should be in chronological order (oldest first).
        Returns validated price list.
        """
        if not prices:
            return prices

        result = []
        interpolation_count = 0

        for i, price in enumerate(prices):
            # Get previous price from result (already validated prices)
            previous_price = result[-1] if result else None

            # Build context from already-validated prices (last 30 days)
            context = list(reversed(result[-CONTEXT_WINDOW_DAYS:])) if result else []

            validation = self.validate_price(price, previous_price, context)

            if validation.all_valid():
                result.append(price)
                continue

            # Find before/after prices for interpolation
            before, after = self._find_interpolation_context(i, prices, result)

            interpolated, method = self.interpolate_price(price, validation, before, after)
            interpolation_count += 1

            result.append(interpolated)

        # Log warning if too many prices were interpolated
        if prices and interpolation_count / len(prices) > 0.5:
            logger.warning(f"More than 50% of prices flagged invalid ({interpolation_count}/{len(prices)})")

        return result

    def validate_price_series_desc(self, prices: list[dict]) -> list[dict]:
        """Validate a price series in descending order (newest first).

        Handles the reverse-validate-reverse pattern: reverses to chronological order,
        validates, and returns in the original descending order.

        Args:
            prices: Price list in descending order (newest first)

        Returns:
            Validated price list in descending order
        """
        if not prices:
            return prices
        return list(reversed(self.validate_and_interpolate(list(reversed(prices)))))

    def _find_interpolation_context(
        self, index: int, prices: list[dict], result: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """Find valid before/after prices for interpolation."""
        before = []
        after = []

        # Look for "before" price in validated results
        if result:
            before = [result[-1]]

        # Look for "after" price in remaining prices
        for j in range(index + 1, len(prices)):
            next_validation = self.validate_price(prices[j], None, result)
            if next_validation.all_valid():
                after = [prices[j]]
                break

        return before, after


def check_trade_blocking(current_price: float, historical_prices: list[float], symbol: str = "") -> Tuple[bool, str]:
    """
    Check if trades should be blocked due to price anomaly.

    Ported from sentinel2's scoring.CheckTradeBlocking.

    Logic:
    - High anomaly (price > 10x avg): BLOCK TRADES (prevents buying at inflated API error prices)
    - Low anomaly (price < 0.1x avg): ALLOW TRADES (may be genuine crash/opportunity)
    - No anomaly: ALLOW TRADES

    Args:
        current_price: The current live price from the API
        historical_prices: List of recent closing prices (last 30+ days)
        symbol: Symbol for logging (optional)

    Returns:
        Tuple of (allow_trade, reason)
        - allow_trade: True if trades are allowed
        - reason: Explanation if trades are blocked, empty string if allowed
    """
    if len(historical_prices) < 30:
        # Insufficient data for anomaly detection - allow trades
        return True, ""

    if current_price <= 0:
        return False, "invalid current price (zero or negative)"

    # Use last 30 days for context (excluding current price which isn't in historical)
    context_prices = historical_prices[-30:]

    if not context_prices:
        return True, ""

    avg_price = sum(context_prices) / len(context_prices)

    if avg_price <= 0:
        return True, ""

    ratio = current_price / avg_price

    # BLOCK on high anomaly only (likely API error)
    if ratio >= MAX_PRICE_MULTIPLIER:
        return False, f"high price anomaly: current {current_price:.2f} is {ratio:.1f}x the 30-day avg {avg_price:.2f}"

    # ALLOW on low anomaly (may be genuine crash/opportunity)
    # ALLOW on normal prices
    return True, ""


def get_price_anomaly_warning(current_price: float, historical_prices: list[float], symbol: str = "") -> Optional[str]:
    """
    Get a warning message if the current price appears anomalous.

    Unlike check_trade_blocking, this returns warnings for BOTH high and low anomalies
    so users can see when something unusual is happening.

    Returns:
        Warning message string, or None if price appears normal
    """
    if len(historical_prices) < 30:
        return None

    if current_price <= 0:
        return "Current price is zero or negative"

    context_prices = historical_prices[-30:]

    if not context_prices:
        return None

    avg_price = sum(context_prices) / len(context_prices)

    if avg_price <= 0:
        return None

    ratio = current_price / avg_price

    if ratio >= MAX_PRICE_MULTIPLIER:
        return (
            f"Price spike detected: {current_price:.2f} is {ratio:.1f}x the 30-day average"
            f" ({avg_price:.2f}). Trades blocked."
        )

    if ratio <= MIN_PRICE_MULTIPLIER:
        return (
            f"Price crash detected: {current_price:.2f} is {ratio:.1f}x the 30-day average"
            f" ({avg_price:.2f}). Verify before trading."
        )

    return None
