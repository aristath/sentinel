"""
Planning Domain - Holistic end-state optimized recommendation planning.

This module provides the holistic planner for multi-step recommendations.
The planner automatically tests sequences at configurable depths (default 1-5,
controlled via max_plan_depth setting) and returns the sequence with the
best end-state portfolio score.
"""

# Holistic planner - End-state optimized planning
from app.modules.planning.domain.holistic_planner import (
    ActionCandidate,
    HolisticPlan,
    HolisticStep,
    create_holistic_plan,
    generate_action_sequences,
    identify_opportunities,
    identify_opportunities_from_weights,
)

# Narrative generator - Human-readable explanations
from app.modules.planning.domain.narrative import (
    format_action_summary,
    generate_plan_narrative,
    generate_step_narrative,
    generate_tradeoff_explanation,
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
