"""Strategy presets for satellite buckets.

Defines 4 pre-configured trading strategies that users can apply to satellites:
1. Momentum Hunter - Aggressive breakout trading with trailing stops
2. Steady Eddy - Conservative buy-and-hold approach
3. Dip Buyer - Opportunistic value investing
4. Dividend Catcher - Income-focused with cash accumulation

Each preset is a complete SatelliteSettings configuration.
"""

from typing import Dict

# Strategy preset definitions matching planning document
MOMENTUM_HUNTER = {
    "risk_appetite": 0.7,
    "hold_duration": 0.3,
    "entry_style": 0.8,
    "position_spread": 0.4,
    "profit_taking": 0.6,
    "trailing_stops": True,
    "follow_regime": True,
    "auto_harvest": False,
    "pause_high_volatility": False,
    "dividend_handling": "reinvest_same",  # Default
}

STEADY_EDDY = {
    "risk_appetite": 0.3,
    "hold_duration": 0.8,
    "entry_style": 0.3,
    "position_spread": 0.7,
    "profit_taking": 0.3,
    "trailing_stops": False,
    "follow_regime": False,
    "auto_harvest": False,  # Default
    "pause_high_volatility": False,  # Default
    "dividend_handling": "reinvest_same",  # Default
}

DIP_BUYER = {
    "risk_appetite": 0.5,
    "hold_duration": 0.7,
    "entry_style": 0.2,
    "position_spread": 0.6,
    "profit_taking": 0.4,
    "trailing_stops": False,  # Default
    "follow_regime": False,  # Default
    "auto_harvest": False,  # Default
    "pause_high_volatility": False,  # Default
    "dividend_handling": "reinvest_same",  # Default
}

DIVIDEND_CATCHER = {
    "risk_appetite": 0.4,
    "hold_duration": 0.2,
    "entry_style": 0.5,
    "position_spread": 0.8,
    "profit_taking": 0.8,
    "trailing_stops": False,  # Default
    "follow_regime": False,  # Default
    "auto_harvest": False,  # Default
    "pause_high_volatility": False,  # Default
    "dividend_handling": "accumulate_cash",
}

# Registry of all available presets
STRATEGY_PRESETS: Dict[str, Dict] = {
    "momentum_hunter": MOMENTUM_HUNTER,
    "steady_eddy": STEADY_EDDY,
    "dip_buyer": DIP_BUYER,
    "dividend_catcher": DIVIDEND_CATCHER,
}


def get_preset(preset_name: str) -> Dict:
    """Get a strategy preset by name.

    Args:
        preset_name: Name of the preset (momentum_hunter, steady_eddy, dip_buyer, dividend_catcher)

    Returns:
        Dictionary of satellite settings

    Raises:
        ValueError: If preset_name is not recognized
    """
    if preset_name not in STRATEGY_PRESETS:
        raise ValueError(
            f"Unknown preset '{preset_name}'. Available: {list(STRATEGY_PRESETS.keys())}"
        )

    return STRATEGY_PRESETS[preset_name].copy()


def list_presets() -> list[str]:
    """List all available strategy preset names.

    Returns:
        List of preset names
    """
    return list(STRATEGY_PRESETS.keys())


def get_preset_description(preset_name: str) -> str:
    """Get a human-readable description of a preset.

    Args:
        preset_name: Name of the preset

    Returns:
        Description string

    Raises:
        ValueError: If preset_name is not recognized
    """
    descriptions = {
        "momentum_hunter": (
            "Aggressive breakout trading with trailing stops. "
            "Targets high-momentum stocks, follows market regime, "
            "moderate hold duration (30% = ~54 days average). "
            "Best for bull markets and growth stocks."
        ),
        "steady_eddy": (
            "Conservative buy-and-hold approach. "
            "Low risk (30%), long hold duration (80% = ~144 days), "
            "wide diversification. No trailing stops. "
            "Best for stable dividend payers and blue chips."
        ),
        "dip_buyer": (
            "Opportunistic value investing. "
            "Buys pullbacks and dips (entry_style=0.2), "
            "holds for recovery (70% = ~126 days), "
            "moderate profit taking. "
            "Best for oversold quality stocks."
        ),
        "dividend_catcher": (
            "Income-focused with cash accumulation. "
            "Accumulates dividends as cash instead of reinvesting. "
            "Short hold duration (20% = ~36 days) for ex-div plays, "
            "wide diversification, aggressive profit taking. "
            "Best for high-yield dividend strategies."
        ),
    }

    if preset_name not in descriptions:
        raise ValueError(
            f"Unknown preset '{preset_name}'. Available: {list(descriptions.keys())}"
        )

    return descriptions[preset_name]
