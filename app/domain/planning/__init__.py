"""
Planning Domain - Strategic goal-driven recommendation planning.

This module provides strategy-based planning for multi-step recommendations.
Each strategy analyzes the portfolio from a different perspective and creates
goal-driven action plans.

Includes:
- Standard goal planner: Strategy-based sequential planning
- Holistic planner: End-state optimized planning with narrative generation
"""

from app.domain.planning.strategies import (
    get_strategy,
    list_strategies,
    RecommendationStrategy,
)
from app.domain.planning.goal_planner import (
    create_strategic_plan,
    StrategicPlan,
    PlanStep,
)
from app.domain.planning.strategies.base import StrategicGoal

# Holistic planner - End-state optimized planning
from app.domain.planning.holistic_planner import (
    create_holistic_plan,
    HolisticPlan,
    HolisticStep,
    identify_opportunities,
    generate_action_sequences,
)

# Narrative generator - Human-readable explanations
from app.domain.planning.narrative import (
    generate_step_narrative,
    generate_plan_narrative,
    generate_tradeoff_explanation,
    format_action_summary,
)

__all__ = [
    # Standard goal planner
    "get_strategy",
    "list_strategies",
    "RecommendationStrategy",
    "create_strategic_plan",
    "StrategicPlan",
    "PlanStep",
    "StrategicGoal",
    # Holistic planner
    "create_holistic_plan",
    "HolisticPlan",
    "HolisticStep",
    "identify_opportunities",
    "generate_action_sequences",
    # Narrative generator
    "generate_step_narrative",
    "generate_plan_narrative",
    "generate_tradeoff_explanation",
    "format_action_summary",
]

