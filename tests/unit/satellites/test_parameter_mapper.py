"""Unit tests for parameter mapper."""

import pytest

from app.modules.satellites.domain.models import SatelliteSettings
from app.modules.satellites.domain.parameter_mapper import (
    describe_parameters,
    get_max_positions,
    get_position_size_pct,
    get_stop_loss_pct,
    get_take_profit_threshold,
    get_target_hold_days,
    is_breakout_buyer,
    is_dip_buyer,
    map_settings_to_parameters,
)


class TestMapSettingsToParameters:
    """Test mapping satellite settings to trading parameters."""

    def test_maps_minimum_risk_appetite(self):
        """Test risk_appetite=0.0 maps to minimum values."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.0,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=0.5,
        )

        params = map_settings_to_parameters(settings)

        # position_size_max = 0.15 + (0.25 * 0.0) = 0.15
        assert params.position_size_max == pytest.approx(0.15)

        # stop_loss_pct = 0.05 + (0.15 * 0.0) = 0.05
        assert params.stop_loss_pct == pytest.approx(0.05)

    def test_maps_maximum_risk_appetite(self):
        """Test risk_appetite=1.0 maps to maximum values."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=1.0,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=0.5,
        )

        params = map_settings_to_parameters(settings)

        # position_size_max = 0.15 + (0.25 * 1.0) = 0.40
        assert params.position_size_max == pytest.approx(0.40)

        # stop_loss_pct = 0.05 + (0.15 * 1.0) = 0.20
        assert params.stop_loss_pct == pytest.approx(0.20)

    def test_maps_minimum_hold_duration(self):
        """Test hold_duration=0.0 maps to 1 day."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.0,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=0.5,
        )

        params = map_settings_to_parameters(settings)

        # target_hold_days = int(1 + (180 * 0.0)) = 1
        assert params.target_hold_days == 1
        assert params.patience_factor == pytest.approx(0.0)

    def test_maps_maximum_hold_duration(self):
        """Test hold_duration=1.0 maps to 181 days."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=1.0,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=0.5,
        )

        params = map_settings_to_parameters(settings)

        # target_hold_days = int(1 + (180 * 1.0)) = 181
        assert params.target_hold_days == 181
        assert params.patience_factor == pytest.approx(1.0)

    def test_maps_dip_buyer_entry_style(self):
        """Test entry_style=0.0 maps to pure dip buyer."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.0,  # Pure dip buyer
            position_spread=0.5,
            profit_taking=0.5,
        )

        params = map_settings_to_parameters(settings)

        # buy_dip_threshold = 1.0 - 0.0 = 1.0
        assert params.buy_dip_threshold == pytest.approx(1.0)

        # breakout_threshold = 0.0
        assert params.breakout_threshold == pytest.approx(0.0)

    def test_maps_breakout_buyer_entry_style(self):
        """Test entry_style=1.0 maps to pure breakout buyer."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=1.0,  # Pure breakout buyer
            position_spread=0.5,
            profit_taking=0.5,
        )

        params = map_settings_to_parameters(settings)

        # buy_dip_threshold = 1.0 - 1.0 = 0.0
        assert params.buy_dip_threshold == pytest.approx(0.0)

        # breakout_threshold = 1.0
        assert params.breakout_threshold == pytest.approx(1.0)

    def test_maps_minimum_position_spread(self):
        """Test position_spread=0.0 maps to 3 positions."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=0.0,
            profit_taking=0.5,
        )

        params = map_settings_to_parameters(settings)

        # max_positions = int(3 + (20 * 0.0)) = 3
        assert params.max_positions == 3
        assert params.diversification_factor == pytest.approx(0.0)

    def test_maps_maximum_position_spread(self):
        """Test position_spread=1.0 maps to 23 positions."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=1.0,
            profit_taking=0.5,
        )

        params = map_settings_to_parameters(settings)

        # max_positions = int(3 + (20 * 1.0)) = 23
        assert params.max_positions == 23
        assert params.diversification_factor == pytest.approx(1.0)

    def test_maps_minimum_profit_taking(self):
        """Test profit_taking=0.0 maps to 5% take profit, 10% trailing."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=0.0,
        )

        params = map_settings_to_parameters(settings)

        # take_profit_threshold = 0.05 + (0.25 * 0.0) = 0.05
        assert params.take_profit_threshold == pytest.approx(0.05)

        # trailing_stop_distance = 0.10 * (1.0 - 0.0) = 0.10
        assert params.trailing_stop_distance == pytest.approx(0.10)

    def test_maps_maximum_profit_taking(self):
        """Test profit_taking=1.0 maps to 30% take profit, 0% trailing."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=1.0,
        )

        params = map_settings_to_parameters(settings)

        # take_profit_threshold = 0.05 + (0.25 * 1.0) = 0.30
        assert params.take_profit_threshold == pytest.approx(0.30)

        # trailing_stop_distance = 0.10 * (1.0 - 1.0) = 0.0
        assert params.trailing_stop_distance == pytest.approx(0.0)

    def test_maps_toggles_correctly(self):
        """Test toggle settings are passed through."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=0.5,
            trailing_stops=True,
            follow_regime=True,
            auto_harvest=True,
            pause_high_volatility=True,
        )

        params = map_settings_to_parameters(settings)

        assert params.trailing_stops is True
        assert params.follow_regime is True
        assert params.auto_harvest is True
        assert params.pause_high_volatility is True

    def test_maps_dividend_handling(self):
        """Test dividend handling is passed through."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=0.5,
            dividend_handling="accumulate_cash",
        )

        params = map_settings_to_parameters(settings)

        assert params.dividend_handling == "accumulate_cash"


class TestHelperFunctions:
    """Test helper functions for quick parameter access."""

    def test_get_position_size_pct(self):
        """Test get_position_size_pct calculation."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=0.5,
        )

        # 0.15 + (0.25 * 0.5) = 0.275
        assert get_position_size_pct(settings) == pytest.approx(0.275)

    def test_get_stop_loss_pct(self):
        """Test get_stop_loss_pct calculation."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=0.5,
        )

        # 0.05 + (0.15 * 0.5) = 0.125
        assert get_stop_loss_pct(settings) == pytest.approx(0.125)

    def test_get_target_hold_days(self):
        """Test get_target_hold_days calculation."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.3,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=0.5,
        )

        # int(1 + (180 * 0.3)) = 55
        assert get_target_hold_days(settings) == 55

    def test_get_max_positions(self):
        """Test get_max_positions calculation."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=0.4,
            profit_taking=0.5,
        )

        # int(3 + (20 * 0.4)) = 11
        assert get_max_positions(settings) == 11

    def test_get_take_profit_threshold(self):
        """Test get_take_profit_threshold calculation."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=0.6,
        )

        # 0.05 + (0.25 * 0.6) = 0.20
        assert get_take_profit_threshold(settings) == pytest.approx(0.20)

    def test_is_dip_buyer(self):
        """Test is_dip_buyer classification."""
        dip_buyer = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.2,  # < 0.5
            position_spread=0.5,
            profit_taking=0.5,
        )

        assert is_dip_buyer(dip_buyer) is True

    def test_is_breakout_buyer(self):
        """Test is_breakout_buyer classification."""
        breakout_buyer = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.8,  # >= 0.5
            position_spread=0.5,
            profit_taking=0.5,
        )

        assert is_breakout_buyer(breakout_buyer) is True


class TestDescribeParameters:
    """Test describe_parameters function."""

    def test_describe_parameters_returns_string(self):
        """Test describe_parameters returns formatted string."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.5,
            position_spread=0.5,
            profit_taking=0.5,
        )

        params = map_settings_to_parameters(settings)
        desc = describe_parameters(params)

        assert isinstance(desc, str)
        assert "Position Sizing" in desc
        assert "Hold Duration" in desc
        assert "Entry Style" in desc
        assert "Profit Taking" in desc
        assert "Features" in desc

    def test_describe_identifies_dip_buyer(self):
        """Test description identifies dip buyer strategy."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.2,  # Dip buyer
            position_spread=0.5,
            profit_taking=0.5,
        )

        params = map_settings_to_parameters(settings)
        desc = describe_parameters(params)

        assert "dip buyer" in desc.lower()

    def test_describe_identifies_breakout_buyer(self):
        """Test description identifies breakout buyer strategy."""
        settings = SatelliteSettings(
            satellite_id="test",
            risk_appetite=0.5,
            hold_duration=0.5,
            entry_style=0.8,  # Breakout buyer
            position_spread=0.5,
            profit_taking=0.5,
        )

        params = map_settings_to_parameters(settings)
        desc = describe_parameters(params)

        assert "breakout buyer" in desc.lower()
