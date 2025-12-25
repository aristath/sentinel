"""Tests for Settings value object."""

import pytest
from app.domain.value_objects.settings import Settings, TradingSettings


class TestSettings:
    """Test Settings value object."""

    def test_create_default_settings(self):
        """Test creating settings with default values."""
        settings = Settings()
        
        assert settings.min_trade_size == 150.0
        assert settings.min_hold_days == 90
        assert settings.sell_cooldown_days == 180
        assert settings.max_loss_threshold == -0.20
        assert settings.target_annual_return == 0.10
        assert settings.recommendation_depth == 1

    def test_create_custom_settings(self):
        """Test creating settings with custom values."""
        settings = Settings(
            min_trade_size=200.0,
            min_hold_days=120,
            sell_cooldown_days=365,
            max_loss_threshold=-0.15,
            target_annual_return=0.12,
            recommendation_depth=2,
        )
        
        assert settings.min_trade_size == 200.0
        assert settings.min_hold_days == 120
        assert settings.sell_cooldown_days == 365
        assert settings.max_loss_threshold == -0.15
        assert settings.target_annual_return == 0.12
        assert settings.recommendation_depth == 2

    def test_settings_validation_min_trade_size(self):
        """Test that min_trade_size must be positive."""
        with pytest.raises(ValueError, match="min_trade_size must be positive"):
            Settings(min_trade_size=-10.0)
        
        with pytest.raises(ValueError, match="min_trade_size must be positive"):
            Settings(min_trade_size=0.0)

    def test_settings_validation_min_hold_days(self):
        """Test that min_hold_days must be non-negative."""
        with pytest.raises(ValueError, match="min_hold_days must be non-negative"):
            Settings(min_hold_days=-1)

    def test_settings_validation_sell_cooldown_days(self):
        """Test that sell_cooldown_days must be non-negative."""
        with pytest.raises(ValueError, match="sell_cooldown_days must be non-negative"):
            Settings(sell_cooldown_days=-1)

    def test_settings_validation_max_loss_threshold(self):
        """Test that max_loss_threshold must be negative."""
        with pytest.raises(ValueError, match="max_loss_threshold must be negative"):
            Settings(max_loss_threshold=0.0)
        
        with pytest.raises(ValueError, match="max_loss_threshold must be negative"):
            Settings(max_loss_threshold=0.1)

    def test_settings_validation_target_annual_return(self):
        """Test that target_annual_return must be positive."""
        with pytest.raises(ValueError, match="target_annual_return must be positive"):
            Settings(target_annual_return=-0.1)
        
        with pytest.raises(ValueError, match="target_annual_return must be positive"):
            Settings(target_annual_return=0.0)

    def test_settings_validation_recommendation_depth(self):
        """Test that recommendation_depth must be positive."""
        with pytest.raises(ValueError, match="recommendation_depth must be positive"):
            Settings(recommendation_depth=0)
        
        with pytest.raises(ValueError, match="recommendation_depth must be positive"):
            Settings(recommendation_depth=-1)

    def test_settings_from_dict(self):
        """Test creating settings from dictionary."""
        data = {
            "min_trade_size": "200.0",
            "min_hold_days": "120",
            "sell_cooldown_days": "365",
            "max_loss_threshold": "-0.15",
            "target_annual_return": "0.12",
            "recommendation_depth": "2",
        }
        
        settings = Settings.from_dict(data)
        
        assert settings.min_trade_size == 200.0
        assert settings.min_hold_days == 120
        assert settings.sell_cooldown_days == 365
        assert settings.max_loss_threshold == -0.15
        assert settings.target_annual_return == 0.12
        assert settings.recommendation_depth == 2

    def test_settings_from_dict_with_missing_keys(self):
        """Test that from_dict uses defaults for missing keys."""
        data = {
            "min_trade_size": "200.0",
        }
        
        settings = Settings.from_dict(data)
        
        assert settings.min_trade_size == 200.0
        assert settings.min_hold_days == 90  # Default
        assert settings.sell_cooldown_days == 180  # Default

    def test_settings_to_dict(self):
        """Test converting settings to dictionary."""
        settings = Settings(
            min_trade_size=200.0,
            min_hold_days=120,
        )
        
        data = settings.to_dict()
        
        assert data["min_trade_size"] == 200.0
        assert data["min_hold_days"] == 120
        assert data["sell_cooldown_days"] == 180  # Default
        assert data["max_loss_threshold"] == -0.20  # Default

    def test_trading_settings_subset(self):
        """Test TradingSettings provides trading-related settings."""
        settings = Settings(
            min_trade_size=200.0,
            min_hold_days=120,
            sell_cooldown_days=365,
            max_loss_threshold=-0.15,
            target_annual_return=0.12,
        )
        
        trading = TradingSettings.from_settings(settings)
        
        assert trading.min_trade_size == 200.0
        assert trading.min_hold_days == 120
        assert trading.sell_cooldown_days == 365
        assert trading.max_loss_threshold == -0.15
        assert trading.target_annual_return == 0.12

