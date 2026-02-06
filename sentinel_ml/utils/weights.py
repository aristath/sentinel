"""Weight blending helpers for ML scoring."""

from collections.abc import Mapping


def compute_weighted_blend(components: Mapping[str, float | None], weights: Mapping[str, float]) -> float | None:
    """Compute availability-aware weighted average.

    Only components with non-null value and positive weight are considered.
    Returns None if no valid component is available.
    """
    weighted_sum = 0.0
    total_weight = 0.0
    for key, component_value in components.items():
        if component_value is None:
            continue
        weight = float(weights.get(key, 0.0))
        if weight <= 0.0:
            continue
        weighted_sum += float(component_value) * weight
        total_weight += weight

    if total_weight <= 0.0:
        return None
    return weighted_sum / total_weight
