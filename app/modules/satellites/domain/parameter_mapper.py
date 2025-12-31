"""Parameter mapping for satellite strategy settings.

Maps slider values (0.0-1.0) from SatelliteSettings to concrete trading parameters
used by the planning and execution systems.

This is the bridge between user-friendly UI controls and the actual trading logic.
"""

from dataclasses import dataclass

from app.modules.satellites.domain.models import SatelliteSettings


@dataclass
class TradingParameters:
    """Concrete trading parameters derived from satellite settings.

    These parameters are used by the planner and execution systems.
    """

    # Position sizing
    position_size_max: float  # Maximum position size as % of bucket (0.15-0.40)
    stop_loss_pct: float  # Stop loss percentage (0.05-0.20)

    # Hold duration
    target_hold_days: int  # Target holding period in days (1-180)
    patience_factor: float  # Patience factor for entry timing (0.0-1.0)

    # Entry style
    buy_dip_threshold: float  # Buy dip threshold: RSI < this (0.0-1.0)
    breakout_threshold: float  # Breakout threshold: momentum > this (0.0-1.0)

    # Diversification
    max_positions: int  # Maximum number of positions (3-23)
    diversification_factor: float  # Diversification preference (0.0-1.0)

    # Profit taking
    take_profit_threshold: float  # Take profit at gain % (0.05-0.30)
    trailing_stop_distance: float  # Trailing stop distance % (0.0-0.10)

    # Toggles
    trailing_stops: bool  # Enable trailing stops
    follow_regime: bool  # Follow market regime signals
    auto_harvest: bool  # Auto-harvest gains above threshold
    pause_high_volatility: bool  # Pause trading during high volatility

    # Dividend handling
    dividend_handling: str  # reinvest_same | send_to_core | accumulate_cash


def map_settings_to_parameters(settings: SatelliteSettings) -> TradingParameters:
    """Map satellite settings to concrete trading parameters.

    Implements the formulas from the planning document:
    - risk_appetite → position_size_max, stop_loss_pct
    - hold_duration → target_hold_days, patience_factor
    - entry_style → buy_dip_threshold, breakout_threshold (0.0=dip buyer, 1.0=breakout)
    - position_spread → max_positions, diversification_factor
    - profit_taking → take_profit_threshold, trailing_stop_distance

    Args:
        settings: Satellite settings with slider values (0.0-1.0)

    Returns:
        TradingParameters with concrete values for trading logic
    """
    # Position sizing from risk_appetite
    position_size_max = 0.15 + (0.25 * settings.risk_appetite)  # 15-40%
    stop_loss_pct = 0.05 + (0.15 * settings.risk_appetite)  # 5-20%

    # Hold duration mapping
    target_hold_days = int(1 + (180 * settings.hold_duration))  # 1-180 days
    patience_factor = settings.hold_duration  # 0.0-1.0

    # Entry style mapping (0.0 = pure dip buyer, 1.0 = pure breakout)
    buy_dip_threshold = 1.0 - settings.entry_style
    breakout_threshold = settings.entry_style

    # Diversification from position_spread
    max_positions = int(3 + (20 * settings.position_spread))  # 3-23 positions
    diversification_factor = settings.position_spread  # 0.0-1.0

    # Profit taking parameters
    take_profit_threshold = 0.05 + (0.25 * settings.profit_taking)  # 5-30%
    trailing_stop_distance = 0.10 * (1.0 - settings.profit_taking)  # 10-0%

    return TradingParameters(
        position_size_max=position_size_max,
        stop_loss_pct=stop_loss_pct,
        target_hold_days=target_hold_days,
        patience_factor=patience_factor,
        buy_dip_threshold=buy_dip_threshold,
        breakout_threshold=breakout_threshold,
        max_positions=max_positions,
        diversification_factor=diversification_factor,
        take_profit_threshold=take_profit_threshold,
        trailing_stop_distance=trailing_stop_distance,
        trailing_stops=settings.trailing_stops,
        follow_regime=settings.follow_regime,
        auto_harvest=settings.auto_harvest,
        pause_high_volatility=settings.pause_high_volatility,
        dividend_handling=settings.dividend_handling,
    )


def get_position_size_pct(settings: SatelliteSettings) -> float:
    """Get maximum position size percentage from settings.

    Args:
        settings: Satellite settings

    Returns:
        Position size as decimal (0.15-0.40)
    """
    return 0.15 + (0.25 * settings.risk_appetite)


def get_stop_loss_pct(settings: SatelliteSettings) -> float:
    """Get stop loss percentage from settings.

    Args:
        settings: Satellite settings

    Returns:
        Stop loss percentage as decimal (0.05-0.20)
    """
    return 0.05 + (0.15 * settings.risk_appetite)


def get_target_hold_days(settings: SatelliteSettings) -> int:
    """Get target holding period in days from settings.

    Args:
        settings: Satellite settings

    Returns:
        Days (1-180)
    """
    return int(1 + (180 * settings.hold_duration))


def get_max_positions(settings: SatelliteSettings) -> int:
    """Get maximum number of positions from settings.

    Args:
        settings: Satellite settings

    Returns:
        Max positions (3-23)
    """
    return int(3 + (20 * settings.position_spread))


def get_take_profit_threshold(settings: SatelliteSettings) -> float:
    """Get take profit threshold from settings.

    Args:
        settings: Satellite settings

    Returns:
        Take profit gain percentage as decimal (0.05-0.30)
    """
    return 0.05 + (0.25 * settings.profit_taking)


def is_dip_buyer(settings: SatelliteSettings) -> bool:
    """Check if strategy is dip buyer oriented.

    Args:
        settings: Satellite settings

    Returns:
        True if entry_style < 0.5 (prefers buying dips)
    """
    return settings.entry_style < 0.5


def is_breakout_buyer(settings: SatelliteSettings) -> bool:
    """Check if strategy is breakout buyer oriented.

    Args:
        settings: Satellite settings

    Returns:
        True if entry_style >= 0.5 (prefers buying breakouts)
    """
    return settings.entry_style >= 0.5


def describe_parameters(params: TradingParameters) -> str:
    """Generate human-readable description of trading parameters.

    Args:
        params: Trading parameters

    Returns:
        Multi-line description string
    """
    entry_bias = (
        "dip buyer"
        if params.buy_dip_threshold > params.breakout_threshold
        else "breakout buyer"
    )

    return f"""Trading Parameters:
  Position Sizing:
    - Max position size: {params.position_size_max*100:.1f}% of bucket
    - Stop loss: {params.stop_loss_pct*100:.1f}%
    - Max positions: {params.max_positions}

  Hold Duration:
    - Target: {params.target_hold_days} days
    - Patience factor: {params.patience_factor:.2f}

  Entry Style: {entry_bias}
    - Buy dip threshold: {params.buy_dip_threshold:.2f}
    - Breakout threshold: {params.breakout_threshold:.2f}

  Profit Taking:
    - Take profit at: +{params.take_profit_threshold*100:.1f}%
    - Trailing stop distance: {params.trailing_stop_distance*100:.1f}%

  Features:
    - Trailing stops: {'enabled' if params.trailing_stops else 'disabled'}
    - Follow regime: {'enabled' if params.follow_regime else 'disabled'}
    - Auto harvest: {'enabled' if params.auto_harvest else 'disabled'}
    - Pause on volatility: {'enabled' if params.pause_high_volatility else 'disabled'}
    - Dividend handling: {params.dividend_handling}
"""
