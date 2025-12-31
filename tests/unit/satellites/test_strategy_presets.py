"""Unit tests for strategy presets."""

import pytest

from app.modules.satellites.domain.strategy_presets import (
    DIP_BUYER,
    DIVIDEND_CATCHER,
    MOMENTUM_HUNTER,
    STEADY_EDDY,
    STRATEGY_PRESETS,
    get_preset,
    get_preset_description,
    list_presets,
)


class TestStrategyPresets:
    """Test strategy preset definitions."""

    def test_momentum_hunter_values(self):
        """Test Momentum Hunter preset has correct values."""
        assert MOMENTUM_HUNTER["risk_appetite"] == 0.7
        assert MOMENTUM_HUNTER["hold_duration"] == 0.3
        assert MOMENTUM_HUNTER["entry_style"] == 0.8
        assert MOMENTUM_HUNTER["position_spread"] == 0.4
        assert MOMENTUM_HUNTER["profit_taking"] == 0.6
        assert MOMENTUM_HUNTER["trailing_stops"] is True
        assert MOMENTUM_HUNTER["follow_regime"] is True

    def test_steady_eddy_values(self):
        """Test Steady Eddy preset has correct values."""
        assert STEADY_EDDY["risk_appetite"] == 0.3
        assert STEADY_EDDY["hold_duration"] == 0.8
        assert STEADY_EDDY["entry_style"] == 0.3
        assert STEADY_EDDY["position_spread"] == 0.7
        assert STEADY_EDDY["profit_taking"] == 0.3
        assert STEADY_EDDY["trailing_stops"] is False
        assert STEADY_EDDY["follow_regime"] is False

    def test_dip_buyer_values(self):
        """Test Dip Buyer preset has correct values."""
        assert DIP_BUYER["risk_appetite"] == 0.5
        assert DIP_BUYER["hold_duration"] == 0.7
        assert DIP_BUYER["entry_style"] == 0.2  # Low = dip buyer
        assert DIP_BUYER["position_spread"] == 0.6
        assert DIP_BUYER["profit_taking"] == 0.4

    def test_dividend_catcher_values(self):
        """Test Dividend Catcher preset has correct values."""
        assert DIVIDEND_CATCHER["risk_appetite"] == 0.4
        assert DIVIDEND_CATCHER["hold_duration"] == 0.2  # Short hold for ex-div
        assert DIVIDEND_CATCHER["entry_style"] == 0.5
        assert DIVIDEND_CATCHER["position_spread"] == 0.8  # Wide diversification
        assert DIVIDEND_CATCHER["profit_taking"] == 0.8  # Aggressive profit taking
        assert DIVIDEND_CATCHER["dividend_handling"] == "accumulate_cash"

    def test_all_presets_registered(self):
        """Test all 4 presets are registered."""
        assert len(STRATEGY_PRESETS) == 4
        assert "momentum_hunter" in STRATEGY_PRESETS
        assert "steady_eddy" in STRATEGY_PRESETS
        assert "dip_buyer" in STRATEGY_PRESETS
        assert "dividend_catcher" in STRATEGY_PRESETS

    def test_all_sliders_in_range(self):
        """Test all slider values are in valid range (0.0-1.0)."""
        sliders = [
            "risk_appetite",
            "hold_duration",
            "entry_style",
            "position_spread",
            "profit_taking",
        ]

        for preset_name, preset in STRATEGY_PRESETS.items():
            for slider in sliders:
                value = preset[slider]
                assert (
                    0.0 <= value <= 1.0
                ), f"{preset_name}.{slider} = {value} (out of range)"


class TestGetPreset:
    """Test get_preset function."""

    def test_get_preset_returns_copy(self):
        """Test get_preset returns a copy, not the original."""
        preset1 = get_preset("momentum_hunter")
        preset2 = get_preset("momentum_hunter")

        # Modify first
        preset1["risk_appetite"] = 0.99

        # Second should be unchanged
        assert preset2["risk_appetite"] == 0.7

    def test_get_preset_unknown_raises(self):
        """Test get_preset raises ValueError for unknown preset."""
        with pytest.raises(ValueError, match="Unknown preset"):
            get_preset("nonexistent")

    def test_get_preset_all_valid(self):
        """Test get_preset works for all registered presets."""
        for preset_name in list_presets():
            preset = get_preset(preset_name)
            assert isinstance(preset, dict)
            assert "risk_appetite" in preset


class TestListPresets:
    """Test list_presets function."""

    def test_list_presets_returns_all(self):
        """Test list_presets returns all 4 preset names."""
        presets = list_presets()
        assert len(presets) == 4
        assert "momentum_hunter" in presets
        assert "steady_eddy" in presets
        assert "dip_buyer" in presets
        assert "dividend_catcher" in presets


class TestGetPresetDescription:
    """Test get_preset_description function."""

    def test_get_description_all_presets(self):
        """Test get_preset_description works for all presets."""
        for preset_name in list_presets():
            desc = get_preset_description(preset_name)
            assert isinstance(desc, str)
            assert len(desc) > 50  # Should be descriptive

    def test_get_description_momentum_hunter(self):
        """Test Momentum Hunter description mentions key features."""
        desc = get_preset_description("momentum_hunter")
        assert "aggressive" in desc.lower()
        assert "breakout" in desc.lower()
        assert "trailing stops" in desc.lower()

    def test_get_description_steady_eddy(self):
        """Test Steady Eddy description mentions key features."""
        desc = get_preset_description("steady_eddy")
        assert "conservative" in desc.lower()
        assert "buy-and-hold" in desc.lower()

    def test_get_description_dip_buyer(self):
        """Test Dip Buyer description mentions key features."""
        desc = get_preset_description("dip_buyer")
        assert "dip" in desc.lower()
        assert "value" in desc.lower()

    def test_get_description_dividend_catcher(self):
        """Test Dividend Catcher description mentions key features."""
        desc = get_preset_description("dividend_catcher")
        assert "dividend" in desc.lower()
        assert "cash accumulation" in desc.lower()

    def test_get_description_unknown_raises(self):
        """Test get_preset_description raises ValueError for unknown preset."""
        with pytest.raises(ValueError, match="Unknown preset"):
            get_preset_description("nonexistent")
