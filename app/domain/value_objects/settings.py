"""Settings value objects for application configuration."""

from dataclasses import dataclass, field
from typing import Dict, Optional, Union


@dataclass(frozen=True)
class Settings:
    """Application settings value object.

    Encapsulates all application settings with validation and type safety.
    """
    min_trade_size: float = 150.0
    min_hold_days: int = 90
    sell_cooldown_days: int = 180
    max_loss_threshold: float = -0.20
    target_annual_return: float = 0.10
    recommendation_depth: int = 1
    min_stock_score: float = 0.5
    
    def __post_init__(self):
        """Validate settings values."""
        if self.min_trade_size <= 0:
            raise ValueError("min_trade_size must be positive")
        
        if self.min_hold_days < 0:
            raise ValueError("min_hold_days must be non-negative")
        
        if self.sell_cooldown_days < 0:
            raise ValueError("sell_cooldown_days must be non-negative")
        
        if self.max_loss_threshold >= 0:
            raise ValueError("max_loss_threshold must be negative")
        
        if self.target_annual_return <= 0:
            raise ValueError("target_annual_return must be positive")
        
        if self.recommendation_depth <= 0:
            raise ValueError("recommendation_depth must be positive")

        if not 0 <= self.min_stock_score <= 1:
            raise ValueError("min_stock_score must be between 0 and 1")
    
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
            min_trade_size=get_float("min_trade_size", 150.0),
            min_hold_days=get_int("min_hold_days", 90),
            sell_cooldown_days=get_int("sell_cooldown_days", 180),
            max_loss_threshold=get_float("max_loss_threshold", -0.20),
            target_annual_return=get_float("target_annual_return", 0.10),
            recommendation_depth=get_int("recommendation_depth", 1),
            min_stock_score=get_float("min_stock_score", 0.5),
        )
    
    def to_dict(self) -> Dict[str, Union[float, int]]:
        """Convert Settings to dictionary.
        
        Returns:
            Dictionary with setting keys and typed values
        """
        return {
            "min_trade_size": self.min_trade_size,
            "min_hold_days": self.min_hold_days,
            "sell_cooldown_days": self.sell_cooldown_days,
            "max_loss_threshold": self.max_loss_threshold,
            "target_annual_return": self.target_annual_return,
            "recommendation_depth": self.recommendation_depth,
            "min_stock_score": self.min_stock_score,
        }


@dataclass(frozen=True)
class TradingSettings:
    """Trading-specific settings subset.
    
    Used when only trading-related settings are needed.
    """
    min_trade_size: float
    min_hold_days: int
    sell_cooldown_days: int
    max_loss_threshold: float
    target_annual_return: float
    
    @classmethod
    def from_settings(cls, settings: Settings) -> "TradingSettings":
        """Create TradingSettings from full Settings object.
        
        Args:
            settings: Full Settings instance
            
        Returns:
            TradingSettings with trading-related fields
        """
        return cls(
            min_trade_size=settings.min_trade_size,
            min_hold_days=settings.min_hold_days,
            sell_cooldown_days=settings.sell_cooldown_days,
            max_loss_threshold=settings.max_loss_threshold,
            target_annual_return=settings.target_annual_return,
        )

