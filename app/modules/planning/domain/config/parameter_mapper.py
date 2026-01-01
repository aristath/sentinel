"""Parameter mapper for UI sliders to technical parameters.

Maps user-friendly slider values (0.0-1.0) to concrete technical parameters
used by calculators, patterns, and other modules.
"""

from typing import Dict

from app.modules.planning.domain.config.models import PlannerConfiguration


class ParameterMapper:
    """
    Maps UI slider values (0.0-1.0) to technical parameters.

    This is where the "magic" happens - user-friendly sliders
    get translated into concrete calculation parameters that
    control planner behavior.

    Each mapper takes a float value in range [0.0, 1.0] and
    returns a dictionary of related technical parameters.
    """

    @staticmethod
    def map_risk_appetite(value: float) -> Dict[str, float]:
        """
        Map risk appetite slider to parameters.

        Args:
            value: 0.0 (conservative) to 1.0 (aggressive)

        Returns:
            Dict of risk-related parameters
        """
        return {
            # Lower threshold = more opportunities considered (aggressive)
            "priority_threshold": 0.5 - (value * 0.3),  # 0.5→0.2
            # Lower cost penalty = less concerned with costs (aggressive)
            "cost_penalty_factor": 0.2 - (value * 0.15),  # 0.2→0.05
            # Higher concentration = fewer, larger positions (aggressive)
            "max_position_concentration": 0.10 + (value * 0.10),  # 10%→20%
        }

    @staticmethod
    def map_hold_duration(value: float) -> Dict[str, float]:
        """
        Map hold duration slider to parameters.

        Args:
            value: 0.0 (quick flips) to 1.0 (patient holds)

        Returns:
            Dict of time-related parameters
        """
        return {
            # Longer hold = higher minimum hold period
            "min_hold_days": int(30 + (value * 150)),  # 30→180 days
            # Longer hold = higher profit threshold before selling
            "profit_taking_threshold": 0.10 + (value * 0.30),  # 10%→40%
        }

    @staticmethod
    def map_entry_style(value: float) -> Dict[str, float]:
        """
        Map entry style slider to parameters.

        Args:
            value: 0.0 (buy dips) to 1.0 (buy breakouts)

        Returns:
            Dict of entry-related parameters
        """
        return {
            # Low value = prefer dips, high value = prefer breakouts
            "dip_weight": 1.0 - value,  # 1.0→0.0
            "breakout_weight": value,  # 0.0→1.0
            # Higher momentum threshold for breakout preference
            "momentum_threshold": 0.3 + (value * 0.6),  # 0.3→0.9
        }

    @staticmethod
    def map_position_spread(value: float) -> Dict[str, float]:
        """
        Map position spread slider to parameters.

        Args:
            value: 0.0 (concentrated) to 1.0 (diversified)

        Returns:
            Dict of diversification-related parameters
        """
        return {
            # More spread = more opportunities per category
            "max_opportunities_per_category": int(2 + (value * 8)),  # 2→10
            # More spread = higher diversity weight
            "diversity_weight": value * 0.5,  # 0.0→0.5
            # More spread = smaller max position size
            "max_position_size": 0.20 - (value * 0.10),  # 20%→10%
        }

    @staticmethod
    def map_profit_taking_aggressiveness(value: float) -> Dict[str, float]:
        """
        Map profit taking slider to parameters.

        Args:
            value: 0.0 (let winners run) to 1.0 (take profits early)

        Returns:
            Dict of profit-taking parameters
        """
        return {
            # Lower threshold = sell at smaller gains (aggressive)
            "windfall_threshold": 0.40 - (value * 0.25),  # 40%→15%
            # Higher percentage = sell more of position (aggressive)
            "windfall_sell_pct": 0.20 + (value * 0.30),  # 20%→50%
            # Tighter trailing stop = lock in gains sooner (aggressive)
            "trailing_stop_distance": 0.15 - (value * 0.10),  # 15%→5%
        }

    @staticmethod
    def apply_sliders_to_config(config: PlannerConfiguration) -> PlannerConfiguration:
        """
        Apply slider values to configuration by updating module parameters.

        This is called when config is created from sliders to ensure
        all technical parameters reflect the slider positions.

        Args:
            config: Configuration with slider values set

        Returns:
            Updated configuration with technical parameters mapped
        """
        # Check if config has slider attributes (it may not if using pure TOML config)
        risk_appetite = getattr(config, "risk_appetite", None)
        hold_duration = getattr(config, "hold_duration", None)
        position_spread = getattr(config, "position_spread", None)
        profit_taking = getattr(config, "profit_taking_aggressiveness", None)

        # Map each slider if present
        if risk_appetite is not None:
            risk_params = ParameterMapper.map_risk_appetite(risk_appetite)
            config.priority_threshold = risk_params["priority_threshold"]
            # cost_penalty_factor is evaluation setting, not in current config model
            # Would be added if we expand PlannerConfiguration

        if hold_duration is not None:
            hold_params = ParameterMapper.map_hold_duration(hold_duration)
            # Apply to filter params
            if config.filters.eligibility.enabled:
                config.filters.eligibility.params["min_hold_days"] = int(
                    hold_params["min_hold_days"]
                )

        # entry_style mapping would be applied to opportunity calculator params
        # Currently not directly mapped in config model

        if position_spread is not None:
            spread_params = ParameterMapper.map_position_spread(position_spread)
            config.max_opportunities_per_category = int(
                spread_params["max_opportunities_per_category"]
            )
            if config.filters.correlation_aware.enabled:
                config.filters.correlation_aware.params["diversity_weight"] = (
                    spread_params["diversity_weight"]
                )

        if profit_taking is not None:
            profit_params = ParameterMapper.map_profit_taking_aggressiveness(
                profit_taking
            )
            # Apply to profit_taking calculator
            if config.opportunity_calculators.profit_taking.enabled:
                config.opportunity_calculators.profit_taking.params.update(
                    {
                        "windfall_threshold": profit_params["windfall_threshold"],
                        # windfall_sell_pct not currently in our model
                    }
                )

        return config

    @staticmethod
    def get_slider_recommendations(
        strategy_type: str,
    ) -> Dict[str, float]:
        """
        Get recommended slider values for common strategies.

        Args:
            strategy_type: One of 'conservative', 'balanced', 'aggressive',
                          'momentum', 'dip_buyer', 'value'

        Returns:
            Dict of slider name to recommended value (0.0-1.0)
        """
        recommendations = {
            "conservative": {
                "risk_appetite": 0.2,
                "hold_duration": 0.9,
                "entry_style": 0.3,
                "position_spread": 0.9,
                "profit_taking_aggressiveness": 0.4,
            },
            "balanced": {
                "risk_appetite": 0.5,
                "hold_duration": 0.6,
                "entry_style": 0.5,
                "position_spread": 0.6,
                "profit_taking_aggressiveness": 0.5,
            },
            "aggressive": {
                "risk_appetite": 0.8,
                "hold_duration": 0.3,
                "entry_style": 0.7,
                "position_spread": 0.4,
                "profit_taking_aggressiveness": 0.7,
            },
            "momentum": {
                "risk_appetite": 0.8,
                "hold_duration": 0.2,
                "entry_style": 0.9,  # Prefer breakouts
                "position_spread": 0.4,
                "profit_taking_aggressiveness": 0.7,
            },
            "dip_buyer": {
                "risk_appetite": 0.5,
                "hold_duration": 0.7,
                "entry_style": 0.1,  # Strong dip preference
                "position_spread": 0.6,
                "profit_taking_aggressiveness": 0.3,
            },
            "value": {
                "risk_appetite": 0.3,
                "hold_duration": 0.8,
                "entry_style": 0.2,
                "position_spread": 0.7,
                "profit_taking_aggressiveness": 0.2,
            },
        }

        return recommendations.get(
            strategy_type,
            recommendations["balanced"],  # Default to balanced
        )
