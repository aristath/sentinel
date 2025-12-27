"""Settings value objects for application configuration."""

from dataclasses import dataclass
from typing import Dict, Union


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
    # Planner settings
    max_plan_depth: int = 5  # Maximum depth for holistic planner sequences (1-10)

    def _validate_non_negative(self, value: float, field_name: str) -> None:
        """Validate that a value is non-negative."""
        if value < 0:
            raise ValueError(f"{field_name} must be non-negative")

    def _validate_positive(self, value: float, field_name: str) -> None:
        """Validate that a value is positive."""
        if value <= 0:
            raise ValueError(f"{field_name} must be positive")

    def _validate_negative(self, value: float, field_name: str) -> None:
        """Validate that a value is negative."""
        if value >= 0:
            raise ValueError(f"{field_name} must be negative")

    def _validate_range(
        self, value: float, field_name: str, min_val: float, max_val: float
    ) -> None:
        """Validate that a value is within a range."""
        if not min_val <= value <= max_val:
            raise ValueError(f"{field_name} must be between {min_val} and {max_val}")

    def __post_init__(self):
        """Validate settings values."""
        self._validate_non_negative(self.min_hold_days, "min_hold_days")
        self._validate_non_negative(self.sell_cooldown_days, "sell_cooldown_days")
        self._validate_negative(self.max_loss_threshold, "max_loss_threshold")
        self._validate_positive(self.target_annual_return, "target_annual_return")
        self._validate_range(self.min_stock_score, "min_stock_score", 0, 1)
        self._validate_range(self.optimizer_blend, "optimizer_blend", 0, 1)
        self._validate_positive(self.optimizer_target_return, "optimizer_target_return")
        self._validate_non_negative(
            self.transaction_cost_fixed, "transaction_cost_fixed"
        )
        self._validate_non_negative(
            self.transaction_cost_percent, "transaction_cost_percent"
        )
        self._validate_non_negative(self.min_cash_reserve, "min_cash_reserve")
        self._validate_range(self.max_plan_depth, "max_plan_depth", 1, 10)

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
            max_plan_depth=get_int("max_plan_depth", 5),
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
            "max_plan_depth": self.max_plan_depth,
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
