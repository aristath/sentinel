"""Tests for Settings value object."""

import pytest

from app.domain.value_objects.settings import Settings, TradingSettings


class TestSettings:
    """Test Settings value object."""

    def test_create_default_settings(self):
        """Test creating settings with default values."""
        settings = Settings()

        assert settings.min_hold_days == 90
        assert settings.sell_cooldown_days == 180
        assert settings.max_loss_threshold == -0.20
        assert settings.target_annual_return == 0.11
        assert settings.min_stock_score == 0.5
        assert settings.optimizer_blend == 0.5
        assert settings.optimizer_target_return == 0.11
        assert settings.transaction_cost_fixed == 2.0
        assert settings.transaction_cost_percent == 0.002
        assert settings.min_cash_reserve == 500.0

    def test_create_custom_settings(self):
        """Test creating settings with custom values."""
        settings = Settings(
            min_hold_days=120,
            sell_cooldown_days=365,
            max_loss_threshold=-0.15,
            target_annual_return=0.12,
            min_stock_score=0.6,
            optimizer_blend=0.7,
            optimizer_target_return=0.12,
            transaction_cost_fixed=3.0,
            transaction_cost_percent=0.003,
            min_cash_reserve=1000.0,
        )

        assert settings.min_hold_days == 120
        assert settings.sell_cooldown_days == 365
        assert settings.max_loss_threshold == -0.15
        assert settings.target_annual_return == 0.12
        assert settings.min_stock_score == 0.6
        assert settings.optimizer_blend == 0.7
        assert settings.optimizer_target_return == 0.12
        assert settings.transaction_cost_fixed == 3.0
        assert settings.transaction_cost_percent == 0.003
        assert settings.min_cash_reserve == 1000.0

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

    def test_settings_validation_min_stock_score(self):
        """Test that min_stock_score must be between 0 and 1."""
        with pytest.raises(ValueError, match="min_stock_score must be between 0 and 1"):
            Settings(min_stock_score=-0.1)

        with pytest.raises(ValueError, match="min_stock_score must be between 0 and 1"):
            Settings(min_stock_score=1.1)

    def test_settings_validation_optimizer_blend(self):
        """Test that optimizer_blend must be between 0 and 1."""
        with pytest.raises(ValueError, match="optimizer_blend must be between 0 and 1"):
            Settings(optimizer_blend=-0.1)

        with pytest.raises(ValueError, match="optimizer_blend must be between 0 and 1"):
            Settings(optimizer_blend=1.1)

    def test_settings_validation_optimizer_target_return(self):
        """Test that optimizer_target_return must be positive."""
        with pytest.raises(
            ValueError, match="optimizer_target_return must be positive"
        ):
            Settings(optimizer_target_return=-0.1)

        with pytest.raises(
            ValueError, match="optimizer_target_return must be positive"
        ):
            Settings(optimizer_target_return=0.0)

    def test_settings_validation_transaction_cost_fixed(self):
        """Test that transaction_cost_fixed must be non-negative."""
        with pytest.raises(
            ValueError, match="transaction_cost_fixed must be non-negative"
        ):
            Settings(transaction_cost_fixed=-1.0)

    def test_settings_validation_transaction_cost_percent(self):
        """Test that transaction_cost_percent must be non-negative."""
        with pytest.raises(
            ValueError, match="transaction_cost_percent must be non-negative"
        ):
            Settings(transaction_cost_percent=-0.001)

    def test_settings_validation_min_cash_reserve(self):
        """Test that min_cash_reserve must be non-negative."""
        with pytest.raises(ValueError, match="min_cash_reserve must be non-negative"):
            Settings(min_cash_reserve=-100.0)

    def test_settings_validation_max_plan_depth(self):
        """Test that max_plan_depth must be between 1 and 10."""
        with pytest.raises(ValueError, match="max_plan_depth must be between 1 and 10"):
            Settings(max_plan_depth=0)

        with pytest.raises(ValueError, match="max_plan_depth must be between 1 and 10"):
            Settings(max_plan_depth=11)

        # Valid values should not raise
        Settings(max_plan_depth=1)
        Settings(max_plan_depth=10)

    def test_settings_from_dict(self):
        """Test creating settings from dictionary."""
        data = {
            "min_hold_days": "120",
            "sell_cooldown_days": "365",
            "max_loss_threshold": "-0.15",
            "target_annual_return": "0.12",
            "min_stock_score": "0.6",
            "optimizer_blend": "0.7",
            "optimizer_target_return": "0.12",
            "transaction_cost_fixed": "3.0",
            "transaction_cost_percent": "0.003",
            "min_cash_reserve": "1000.0",
            "max_plan_depth": "7",
        }

        settings = Settings.from_dict(data)

        assert settings.min_hold_days == 120
        assert settings.sell_cooldown_days == 365
        assert settings.max_loss_threshold == -0.15
        assert settings.target_annual_return == 0.12
        assert settings.min_stock_score == 0.6
        assert settings.optimizer_blend == 0.7
        assert settings.optimizer_target_return == 0.12
        assert settings.transaction_cost_fixed == 3.0
        assert settings.transaction_cost_percent == 0.003
        assert settings.min_cash_reserve == 1000.0
        assert settings.max_plan_depth == 7

    def test_settings_from_dict_with_missing_keys(self):
        """Test that from_dict uses defaults for missing keys."""
        data = {
            "min_hold_days": "120",
        }

        settings = Settings.from_dict(data)

        assert settings.min_hold_days == 120
        assert settings.sell_cooldown_days == 180  # Default
        assert settings.optimizer_blend == 0.5  # Default
        assert settings.max_plan_depth == 5  # Default

    def test_settings_to_dict(self):
        """Test converting settings to dictionary."""
        settings = Settings(
            min_hold_days=120,
            optimizer_blend=0.7,
            max_plan_depth=8,
        )

        data = settings.to_dict()

        assert data["min_hold_days"] == 120
        assert data["optimizer_blend"] == 0.7
        assert data["sell_cooldown_days"] == 180  # Default
        assert data["max_loss_threshold"] == -0.20  # Default
        assert data["max_plan_depth"] == 8

    def test_trading_settings_subset(self):
        """Test TradingSettings provides trading-related settings."""
        settings = Settings(
            min_hold_days=120,
            sell_cooldown_days=365,
            max_loss_threshold=-0.15,
            target_annual_return=0.12,
            transaction_cost_fixed=3.0,
            transaction_cost_percent=0.003,
            min_cash_reserve=1000.0,
        )

        trading = TradingSettings.from_settings(settings)

        assert trading.min_hold_days == 120
        assert trading.sell_cooldown_days == 365
        assert trading.max_loss_threshold == -0.15
        assert trading.target_annual_return == 0.12
        assert trading.transaction_cost_fixed == 3.0
        assert trading.transaction_cost_percent == 0.003
        assert trading.min_cash_reserve == 1000.0
