"""
Planning Domain - Holistic end-state optimized recommendation planning.

This module provides the holistic planner for multi-step recommendations.
The planner automatically tests sequences at all depths (1-5) and returns
the sequence with the best end-state portfolio score.
"""

# Holistic planner - End-state optimized planning
from app.domain.planning.holistic_planner import (
    create_holistic_plan,
    HolisticPlan,
    HolisticStep,
    ActionCandidate,
    identify_opportunities,
    identify_opportunities_from_weights,
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
    # Holistic planner
    "create_holistic_plan",
    "HolisticPlan",
    "HolisticStep",
    "ActionCandidate",
    "identify_opportunities",
    "identify_opportunities_from_weights",
    "generate_action_sequences",
    # Narrative generator
    "generate_step_narrative",
    "generate_plan_narrative",
    "generate_tradeoff_explanation",
    "format_action_summary",
]
