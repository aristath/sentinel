"""Eligibility filter for trading rules.

Enforces important trading constraints:
- Minimum holding period before selling
- Cooldown periods between sells
- Maximum loss threshold (don't sell at steep losses)
"""

from datetime import datetime
from typing import Any, Dict, List

from app.modules.planning.domain.calculations.filters.base import (
    SequenceFilter,
    sequence_filter_registry,
)
from app.modules.planning.domain.holistic_planner import ActionCandidate


class EligibilityFilter(SequenceFilter):
    """
    Filters based on eligibility rules.

    Enforces critical trading discipline rules:
    1. Minimum holding period: Don't sell positions held < N days
    2. Sell cooldown: Don't sell same symbol too frequently
    3. Maximum loss threshold: Don't sell at catastrophic losses

    These rules prevent:
    - Panic selling of recent positions
    - Tax inefficiency from short-term gains
    - Realizing deep losses (better to hold for recovery)
    - Over-trading the same security
    """

    @property
    def name(self) -> str:
        return "eligibility"

    def default_params(self) -> Dict[str, Any]:
        return {
            "min_hold_days": 90,  # Minimum days before allowing sell
            "sell_cooldown_days": 180,  # Days between sells of same symbol
            "max_loss_threshold": -0.20,  # Never sell if down more than 20%
            "enforce_min_hold": True,  # Enable/disable min hold check
            "enforce_cooldown": True,  # Enable/disable cooldown check
            "enforce_max_loss": True,  # Enable/disable max loss check
        }

    async def filter(
        self,
        sequences: List[List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Filter sequences by eligibility rules.

        Removes sequences containing ineligible sell actions.

        Args:
            sequences: List of candidate sequences
            params: Filter parameters

        Returns:
            Filtered sequences with only eligible actions
        """
        min_hold_days = params.get("min_hold_days", 90)
        sell_cooldown_days = params.get("sell_cooldown_days", 180)
        max_loss_threshold = params.get("max_loss_threshold", -0.20)
        enforce_min_hold = params.get("enforce_min_hold", True)
        enforce_cooldown = params.get("enforce_cooldown", True)
        enforce_max_loss = params.get("enforce_max_loss", True)

        from app.domain.value_objects.trade_side import TradeSide

        filtered_sequences: List[List[ActionCandidate]] = []

        for sequence in sequences:
            # Check if sequence contains any ineligible sells
            is_eligible = True

            for action in sequence:
                if action.side != TradeSide.SELL:
                    continue  # Only filter sells

                # Check 1: Minimum holding period
                if enforce_min_hold and not self._check_min_hold(
                    action, min_hold_days, params
                ):
                    is_eligible = False
                    break

                # Check 2: Sell cooldown period
                if enforce_cooldown and not self._check_cooldown(
                    action, sell_cooldown_days, params
                ):
                    is_eligible = False
                    break

                # Check 3: Maximum loss threshold
                if enforce_max_loss and not self._check_max_loss(
                    action, max_loss_threshold, params
                ):
                    is_eligible = False
                    break

            if is_eligible:
                filtered_sequences.append(sequence)

        return filtered_sequences

    def _check_min_hold(
        self, action: ActionCandidate, min_hold_days: int, params: Dict[str, Any]
    ) -> bool:
        """
        Check if position has been held long enough.

        In production, this would query the position acquisition date.
        For now, we'll need to receive this info via params.
        """
        # Check if position_acquired_dates provided in params
        position_acquired_dates = params.get("position_acquired_dates", {})

        if action.symbol not in position_acquired_dates:
            # If we don't have acquisition date, assume it's eligible
            # (Conservative: better to allow than block incorrectly)
            return True

        acquired_date = position_acquired_dates[action.symbol]
        if isinstance(acquired_date, str):
            acquired_date = datetime.fromisoformat(acquired_date)

        days_held = (datetime.now() - acquired_date).days

        return days_held >= min_hold_days

    def _check_cooldown(
        self, action: ActionCandidate, sell_cooldown_days: int, params: Dict[str, Any]
    ) -> bool:
        """
        Check if enough time has passed since last sell.

        In production, this would query trade history.
        For now, we'll need to receive this info via params.
        """
        # Check if last_sell_dates provided in params
        last_sell_dates = params.get("last_sell_dates", {})

        if action.symbol not in last_sell_dates:
            # No recent sell found, eligible
            return True

        last_sell_date = last_sell_dates[action.symbol]
        if isinstance(last_sell_date, str):
            last_sell_date = datetime.fromisoformat(last_sell_date)

        days_since_sell = (datetime.now() - last_sell_date).days

        return days_since_sell >= sell_cooldown_days

    def _check_max_loss(
        self, action: ActionCandidate, max_loss_threshold: float, params: Dict[str, Any]
    ) -> bool:
        """
        Check if position loss is within acceptable range.

        Don't sell positions with catastrophic losses - better to hold
        for potential recovery.

        In production, this would calculate unrealized gain/loss.
        For now, we'll need to receive this info via params.
        """
        # Check if position_returns provided in params
        position_returns = params.get("position_returns", {})

        if action.symbol not in position_returns:
            # If we don't have return data, assume it's eligible
            return True

        current_return = position_returns[action.symbol]

        # If loss exceeds threshold, reject
        # e.g., max_loss_threshold = -0.20 (20% loss)
        #       current_return = -0.25 (25% loss)
        #       -0.25 < -0.20 → True → Reject
        if current_return < max_loss_threshold:
            return False

        return True


# Auto-register
_eligibility_filter = EligibilityFilter()
sequence_filter_registry.register(_eligibility_filter.name, _eligibility_filter)
