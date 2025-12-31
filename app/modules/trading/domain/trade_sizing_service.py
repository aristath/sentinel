"""
Trade Sizing Service - Lot-aware quantity calculations.

Single source of truth for all trade quantity calculations that respect:
- Minimum lot sizes (e.g., 5, 10, 100 shares)
- Currency exchange rates
- Base trade amounts
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SizedTrade:
    """Result of trade sizing calculation."""

    quantity: int  # Number of shares
    value_native: float  # Value in security's currency
    value_eur: float  # Value in EUR
    num_lots: int  # Number of lots (quantity / min_lot)


class TradeSizingService:
    """Calculate trade quantities respecting lot sizes and currency conversion."""

    @staticmethod
    def calculate_buy_quantity(
        target_value_eur: float,
        price: float,
        min_lot: int = 1,
        exchange_rate: float = 1.0,
    ) -> SizedTrade:
        """
        Calculate buy quantity respecting min_lot constraints.

        Args:
            target_value_eur: Desired trade value in EUR
            price: Security price in native currency
            min_lot: Minimum lot size (default 1)
            exchange_rate: Native currency per 1 EUR (e.g., HKD/EUR ≈ 8.4)

        Returns:
            SizedTrade with actual quantity and values

        Example:
            target_value_eur=150, price=90 DKK, min_lot=5, exchange_rate=7.46 (DKK per EUR)
            -> lot_cost_native = 5 * 90 = 450 DKK
            -> lot_cost_eur = 450 / 7.46 = 60.32 EUR
            -> num_lots = floor((150 * 7.46) / 450) = floor(2.49) = 2
            -> quantity = 2 * 5 = 10 shares
            -> value_eur = (10 * 90) / 7.46 = 120.64 EUR
        """
        min_lot = max(1, min_lot)  # Ensure at least 1
        exchange_rate = exchange_rate if exchange_rate > 0 else 1.0

        # Calculate cost of one lot in EUR
        # exchange_rate = native currency per 1 EUR (e.g., HKD/EUR ≈ 8.4)
        # Native → EUR: divide by exchange_rate
        # EUR → Native: multiply by exchange_rate
        lot_cost_native = min_lot * price
        lot_cost_eur = lot_cost_native / exchange_rate

        if lot_cost_eur > target_value_eur:
            # Minimum lot costs more than target - buy exactly min_lot
            quantity = min_lot
            num_lots = 1
        else:
            # Can afford multiple lots
            target_native = target_value_eur * exchange_rate
            num_lots = max(1, int(target_native / lot_cost_native))
            quantity = num_lots * min_lot

        value_native = quantity * price
        value_eur = value_native / exchange_rate

        return SizedTrade(
            quantity=quantity,
            value_native=value_native,
            value_eur=value_eur,
            num_lots=num_lots,
        )

    @staticmethod
    def calculate_sell_quantity(
        target_quantity: float,
        min_lot: int = 1,
        current_holdings: int = 0,
    ) -> int:
        """
        Round sell quantity down to nearest lot boundary.

        Args:
            target_quantity: Raw desired quantity to sell
            min_lot: Minimum lot size
            current_holdings: Current position size (to cap sell)

        Returns:
            Valid sell quantity (multiple of min_lot)
        """
        min_lot = max(1, min_lot)

        # Round down to lot boundary
        if min_lot > 1:
            quantity = int(target_quantity // min_lot) * min_lot
        else:
            quantity = int(target_quantity)

        # Cap at current holdings
        if current_holdings > 0:
            quantity = min(quantity, current_holdings)

        return quantity

    @staticmethod
    def round_to_lots(quantity: float, min_lot: int = 1) -> int:
        """Round quantity down to nearest lot boundary."""
        min_lot = max(1, min_lot)
        if min_lot > 1:
            return int(quantity // min_lot) * min_lot
        return int(quantity)
