"""Settings value objects for application configuration."""

from dataclasses import dataclass, field
from typing import Dict, Optional, Union


@dataclass(frozen=True)
class Settings:
    """Application settings value object.

    Encapsulates all application settings with validation and type safety.

    Note: min_trade_size, recommendation_depth, and max_balance_worsening have been
    removed. The portfolio optimizer now handles allocation decisions. Transaction
    costs (transaction_cost_fixed, transaction_cost_percent) replace min_trade_size.
    """

    min_hold_days: int = 90
    sell_cooldown_days: int = 180
    max_loss_threshold: float = -0.20
    target_annual_return: float = 0.11
    min_stock_score: float = 0.5
    # Optimizer settings
    optimizer_blend: float = 0.5
    optimizer_target_return: float = 0.11
    # Transaction costs (Freedom24)
    transaction_cost_fixed: float = 2.0
    transaction_cost_percent: float = 0.002
    # Cash management
    min_cash_reserve: float = 500.0

    def __post_init__(self):
        """Validate settings values."""
        if self.min_hold_days < 0:
            raise ValueError("min_hold_days must be non-negative")

        if self.sell_cooldown_days < 0:
            raise ValueError("sell_cooldown_days must be non-negative")

        if self.max_loss_threshold >= 0:
            raise ValueError("max_loss_threshold must be negative")

        if self.target_annual_return <= 0:
            raise ValueError("target_annual_return must be positive")

        if not 0 <= self.min_stock_score <= 1:
            raise ValueError("min_stock_score must be between 0 and 1")

        if not 0 <= self.optimizer_blend <= 1:
            raise ValueError("optimizer_blend must be between 0 and 1")

        if self.optimizer_target_return <= 0:
            raise ValueError("optimizer_target_return must be positive")

        if self.transaction_cost_fixed < 0:
            raise ValueError("transaction_cost_fixed must be non-negative")

        if self.transaction_cost_percent < 0:
            raise ValueError("transaction_cost_percent must be non-negative")

        if self.min_cash_reserve < 0:
            raise ValueError("min_cash_reserve must be non-negative")

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "Settings":
        """Create Settings from dictionary (e.g., from repository).

        Args:
            data: Dictionary with setting keys and string values

        Returns:
            Settings instance with parsed values
        """

        def get_float(key: str, default: float) -> float:
            value = data.get(key)
            if value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        def get_int(key: str, default: int) -> int:
            value = data.get(key)
            if value is None:
                return default
            try:
                # Parse via float first to handle "12.0" strings from database
                return int(float(value))
            except (ValueError, TypeError):
                return default

        return cls(
            min_hold_days=get_int("min_hold_days", 90),
            sell_cooldown_days=get_int("sell_cooldown_days", 180),
            max_loss_threshold=get_float("max_loss_threshold", -0.20),
            target_annual_return=get_float("target_annual_return", 0.11),
            min_stock_score=get_float("min_stock_score", 0.5),
            optimizer_blend=get_float("optimizer_blend", 0.5),
            optimizer_target_return=get_float("optimizer_target_return", 0.11),
            transaction_cost_fixed=get_float("transaction_cost_fixed", 2.0),
            transaction_cost_percent=get_float("transaction_cost_percent", 0.002),
            min_cash_reserve=get_float("min_cash_reserve", 500.0),
        )

    def to_dict(self) -> Dict[str, Union[float, int]]:
        """Convert Settings to dictionary.

        Returns:
            Dictionary with setting keys and typed values
        """
        return {
            "min_hold_days": self.min_hold_days,
            "sell_cooldown_days": self.sell_cooldown_days,
            "max_loss_threshold": self.max_loss_threshold,
            "target_annual_return": self.target_annual_return,
            "min_stock_score": self.min_stock_score,
            "optimizer_blend": self.optimizer_blend,
            "optimizer_target_return": self.optimizer_target_return,
            "transaction_cost_fixed": self.transaction_cost_fixed,
            "transaction_cost_percent": self.transaction_cost_percent,
            "min_cash_reserve": self.min_cash_reserve,
        }


@dataclass(frozen=True)
class TradingSettings:
    """Trading-specific settings subset.

    Used when only trading-related settings are needed.
    """

    min_hold_days: int
    sell_cooldown_days: int
    max_loss_threshold: float
    target_annual_return: float
    transaction_cost_fixed: float
    transaction_cost_percent: float
    min_cash_reserve: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "TradingSettings":
        """Create TradingSettings from full Settings object.

        Args:
            settings: Full Settings instance

        Returns:
            TradingSettings with trading-related fields
        """
        return cls(
            min_hold_days=settings.min_hold_days,
            sell_cooldown_days=settings.sell_cooldown_days,
            max_loss_threshold=settings.max_loss_threshold,
            target_annual_return=settings.target_annual_return,
            transaction_cost_fixed=settings.transaction_cost_fixed,
            transaction_cost_percent=settings.transaction_cost_percent,
            min_cash_reserve=settings.min_cash_reserve,
        )
