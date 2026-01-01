"""Recently traded filter.

Prevents over-trading by enforcing cooldown periods for both buys and sells.
"""

from datetime import datetime
from typing import Any, Dict, List

from app.modules.planning.domain.calculations.filters.base import (
    SequenceFilter,
    sequence_filter_registry,
)
from app.modules.planning.domain.models import ActionCandidate


class RecentlyTradedFilter(SequenceFilter):
    """
    Filters based on buy/sell cooldown periods.

    Prevents churning by enforcing minimum time between trades
    of the same security. This helps avoid:
    - Over-trading (excessive transaction costs)
    - Short-term emotional decisions
    - Tax inefficiency from frequent buying/selling
    - Round-trip trades (buy → sell → buy same symbol)

    Cooldown periods:
    - Buy cooldown: Minimum days between buy orders for same symbol
    - Sell cooldown: Minimum days between sell orders for same symbol

    This differs from EligibilityFilter which enforces minimum hold
    period after acquisition. This filter focuses purely on preventing
    repetitive trading.
    """

    @property
    def name(self) -> str:
        return "recently_traded"

    def default_params(self) -> Dict[str, Any]:
        return {
            "buy_cooldown_days": 30,  # Wait 30 days between buys of same symbol
            "sell_cooldown_days": 180,  # Wait 180 days between sells of same symbol
            "enforce_buy_cooldown": True,  # Enable/disable buy cooldown
            "enforce_sell_cooldown": True,  # Enable/disable sell cooldown
        }

    async def filter(
        self,
        sequences: List[List[ActionCandidate]],
        params: Dict[str, Any],
    ) -> List[List[ActionCandidate]]:
        """
        Filter sequences containing recently traded symbols.

        Removes sequences that would trade (buy or sell) a symbol
        that was recently traded within the cooldown period.

        Args:
            sequences: List of candidate sequences
            params: Filter parameters including trade history

        Returns:
            Filtered sequences respecting cooldown periods
        """
        buy_cooldown_days = params.get("buy_cooldown_days", 30)
        sell_cooldown_days = params.get("sell_cooldown_days", 180)
        enforce_buy_cooldown = params.get("enforce_buy_cooldown", True)
        enforce_sell_cooldown = params.get("enforce_sell_cooldown", True)

        # Get trade history from params
        # Format: {"AAPL": {"last_buy": "2024-01-15", "last_sell": "2023-12-01"}}
        trade_history = params.get("trade_history", {})

        from app.domain.value_objects.trade_side import TradeSide

        filtered_sequences: List[List[ActionCandidate]] = []

        for sequence in sequences:
            is_eligible = True

            for action in sequence:
                # Check buy cooldown
                if (
                    action.side == TradeSide.BUY
                    and enforce_buy_cooldown
                    and not self._check_buy_cooldown(
                        action, buy_cooldown_days, trade_history
                    )
                ):
                    is_eligible = False
                    break

                # Check sell cooldown
                if (
                    action.side == TradeSide.SELL
                    and enforce_sell_cooldown
                    and not self._check_sell_cooldown(
                        action, sell_cooldown_days, trade_history
                    )
                ):
                    is_eligible = False
                    break

            if is_eligible:
                filtered_sequences.append(sequence)

        return filtered_sequences

    def _check_buy_cooldown(
        self, action: ActionCandidate, buy_cooldown_days: int, trade_history: Dict
    ) -> bool:
        """Check if enough time has passed since last buy."""
        if action.symbol not in trade_history:
            return True  # No previous trades, eligible

        symbol_history = trade_history[action.symbol]

        if "last_buy" not in symbol_history:
            return True  # No previous buys, eligible

        last_buy_date = symbol_history["last_buy"]
        if isinstance(last_buy_date, str):
            last_buy_date = datetime.fromisoformat(last_buy_date)

        days_since_buy = (datetime.now() - last_buy_date).days

        return days_since_buy >= buy_cooldown_days

    def _check_sell_cooldown(
        self, action: ActionCandidate, sell_cooldown_days: int, trade_history: Dict
    ) -> bool:
        """Check if enough time has passed since last sell."""
        if action.symbol not in trade_history:
            return True  # No previous trades, eligible

        symbol_history = trade_history[action.symbol]

        if "last_sell" not in symbol_history:
            return True  # No previous sells, eligible

        last_sell_date = symbol_history["last_sell"]
        if isinstance(last_sell_date, str):
            last_sell_date = datetime.fromisoformat(last_sell_date)

        days_since_sell = (datetime.now() - last_sell_date).days

        return days_since_sell >= sell_cooldown_days


# Auto-register
_recently_traded_filter = RecentlyTradedFilter()
sequence_filter_registry.register(_recently_traded_filter.name, _recently_traded_filter)
