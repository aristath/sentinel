# Quantum Probability Models Implementation

**Date**: 2025-01-27
**Status**: ✅ Implemented
**Module**: `trader/internal/modules/quantum`

## Overview

This document describes the implementation of quantum probability models for asset returns in the arduino-trader system. The implementation uses a **quantum-inspired approach** (not full quantum mechanics) integrated with existing classical methods in an **ensemble approach** for autonomous operation.

## Architecture

### Module Structure

```
trader/internal/modules/quantum/
├── calculator.go      # Core quantum probability calculator
├── bubble.go          # Bubble detection using quantum states
├── value_trap.go      # Value trap detection using superposition
├── scoring.go         # Quantum-enhanced scoring metrics
├── models.go          # Quantum state models and types
└── calculator_test.go # Comprehensive unit tests
```

### Key Components

1. **QuantumProbabilityCalculator**: Core calculator with energy levels, interference, and normalization
2. **Bubble Detection**: Quantum-inspired bubble probability calculation
3. **Value Trap Detection**: Quantum superposition modeling for value/trap states
4. **Scoring Metrics**: Quantum-enhanced risk-adjusted metrics

## Mathematical Foundation

### Quantum Superposition Model

Based on Schrödinger-like trading equation approach ([arXiv:2401.05823](https://arxiv.org/abs/2401.05823)):

```
|security⟩ = α|value⟩ + β|bubble⟩
```

Where:
- `α = √(P_value) * exp(i·E_value·t)` - Value state amplitude
- `β = √(P_bubble) * exp(i·E_bubble·t)` - Bubble state amplitude
- `E_value`, `E_bubble` - Discrete energy levels (quantized to {-π, -π/2, 0, π/2, π})
- `t = 1.0` - Normalized time parameter

### Energy Levels

**Discrete Energy Quantization**:
- Value states: `E ∈ {-π, -π/2, 0}` (stable, neutral, transition)
- Bubble states: `E ∈ {0, π/2, π}` (transition, unstable, extreme)

**Energy Calculations**:
- `E_value = -k·(fundamentals + stability + sortino_bonus)`
- `E_bubble = k·(cagr - (1-sharpe) - volatility)`
- `k = π/2` (energy scale factor)

### Born Rule Probability

```
P(bubble) = |β|² + λ·interference + μ·multimodal_correction
```

Where:
- `|β|² = P_bubble` - Classical probability component
- `interference = 2√(P_value·P_bubble)·cos(ΔE·t)` - Quantum interference
- `multimodal_correction = f(volatility, kurtosis)` - Fat tail correction
- `λ` - Adaptive interference weight (0.2-0.4 based on regime)
- `μ = 0.15` - Multimodal correction weight

### Interference Effects

Quantum interference captures:
- **Phase transitions**: `cos(ΔE·t)` detects regime changes
- **Multimodal distributions**: Energy quantization models multiple return modes
- **Fat tails**: Multimodal correction accounts for extreme events

## Implementation Details

### Bubble Detection

**Function**: `CalculateBubbleProbability()`

**Inputs**:
- CAGR (raw)
- Sharpe ratio
- Sortino ratio
- Volatility
- Fundamentals score
- Regime score (for adaptive weighting)
- Kurtosis (optional, for multimodal correction)

**Algorithm**:
1. Normalize inputs to [0, 1] range
2. Calculate discrete energy levels (quantized)
3. Calculate probability amplitudes (normalized)
4. Calculate quantum amplitudes with energy-based phases
5. Calculate interference term
6. Calculate multimodal correction (if kurtosis available)
7. Apply Born rule with adaptive interference weight
8. Return probability [0, 1]

**Output**: Probability of bubble state

### Value Trap Detection

**Function**: `CalculateValueTrapProbability()`

**Inputs**:
- P/E vs market
- Fundamentals score
- Long-term score
- Momentum score
- Volatility
- Regime score

**Algorithm**:
1. Check if security is cheap (P/E < market - 20%)
2. Calculate energy levels for value and trap states
3. Calculate probability amplitudes
4. Calculate interference
5. Apply Born rule
6. Return probability [0, 1]

**Output**: Probability of value trap state

### Quantum Scoring Metrics

**Function**: `CalculateQuantumScore()`

**Outputs**:
- `quantum_risk_adjusted`: Quantum-inspired risk metric (combines traditional + interference)
- `quantum_interference`: Interference effect score (captures interactions)
- `quantum_multimodal`: Multimodal distribution indicator (fat tails)

## Ensemble Integration

### Tag System

**New Tags**:
- `quantum-bubble-risk`: P(bubble) > 0.7 (monitoring)
- `quantum-bubble-warning`: 0.5 < P(bubble) ≤ 0.7 (soft filter)
- `ensemble-bubble-risk`: Classical OR quantum > 0.7 (hard exclude)
- `quantum-value-trap`: P(trap) > 0.7 (monitoring)
- `quantum-value-warning`: 0.5 < P(trap) ≤ 0.7 (soft filter)
- `ensemble-value-trap`: Classical OR quantum > 0.7 (hard exclude)

**Existing Tags** (maintained for backward compatibility):
- `bubble-risk` (classical)
- `value-trap` (classical)

### Ensemble Decision Logic

**Bubble Detection**:
```go
if classicalBubble {
    tags = append(tags, "bubble-risk", "ensemble-bubble-risk")
} else if quantumProb > 0.7 {
    tags = append(tags, "quantum-bubble-risk", "ensemble-bubble-risk")
} else if quantumProb > 0.5 {
    tags = append(tags, "quantum-bubble-warning")
}
```

**Value Trap Detection**:
```go
if classicalTrap {
    tags = append(tags, "value-trap", "ensemble-value-trap")
} else if quantumProb > 0.7 {
    tags = append(tags, "quantum-value-trap", "ensemble-value-trap")
} else if quantumProb > 0.5 {
    tags = append(tags, "quantum-value-warning")
}
```

### Opportunity Calculator Integration

**Hard Filters** (exclude from buys):
- `bubble-risk` OR `ensemble-bubble-risk`
- `value-trap` OR `ensemble-value-trap`

**Soft Filters** (reduce priority by 30%):
- `quantum-bubble-warning`
- `quantum-value-warning`

**Updated Calculators**:
- `weight_based.go`
- `hybrid_opportunity_buys.go`
- `hybrid_averaging_down.go`

## Performance

**Benchmarks** (from tests):
- Bubble probability calculation: **~174ns** per operation
- Value trap probability calculation: **~200ns** per operation
- For 30 securities: **< 6 microseconds** total
- Memory: **~50 bytes** per security

**Conclusion**: Performance impact is **negligible** (< 0.01ms per security).

## Testing

### Unit Tests

Comprehensive tests in `calculator_test.go`:
- Energy level quantization
- State normalization
- Interference calculations
- Bubble probability (edge cases)
- Value trap probability (edge cases)
- Born rule
- Adaptive interference weight
- Performance benchmarks

### Integration Tests

Tests in `tag_assigner_test.go`:
- `TestTagAssigner_QuantumBubbleDetection`: Verifies quantum early warning
- `TestTagAssigner_QuantumValueTrapDetection`: Verifies ensemble value trap detection
- `TestTagAssigner_EnsembleBubbleDetection`: Verifies ensemble logic

**Test Results**: All tests pass ✅

## Usage

### In Tag Assigner

Quantum detection is automatically integrated into `tag_assigner.go`:
- Calculates quantum probabilities alongside classical detection
- Adds ensemble tags based on combined logic
- Maintains backward compatibility with existing tags

### In Scoring System

Quantum metrics are automatically added to `SubScores`:
- Available under `quantum` group
- Includes `risk_adjusted`, `interference`, `multimodal`
- Can be used for analysis and future enhancements

### In Opportunity Calculators

Ensemble tags are automatically checked:
- Hard filters exclude `ensemble-bubble-risk` and `ensemble-value-trap`
- Soft filters reduce priority for `quantum-bubble-warning` and `quantum-value-warning`

## Configuration

### Adaptive Weighting

Interference weight `λ` adapts based on market regime:
- **Bull market** (regimeScore > 0.5): `λ = 0.4` (favor quantum, earlier detection)
- **Bear market** (regimeScore < -0.5): `λ = 0.2` (favor classical, proven reliability)
- **Sideways** (otherwise): `λ = 0.3` (balanced)

### Parameters

- **Energy scale factor**: `k = π/2` (normalizes to [-π, π])
- **Time parameter**: `t = 1.0` (normalized, can be made adaptive)
- **Multimodal correction weight**: `μ = 0.15`
- **Bubble threshold**: `P(bubble) > 0.7` for hard filter
- **Warning threshold**: `0.5 < P(bubble) ≤ 0.7` for soft filter

## References

- [arXiv:2401.05823](https://arxiv.org/abs/2401.05823) - Quantum probability models for financial returns
- [MDPI Quantum Student's t-distribution](https://www.mdpi.com/2673-8392/5/2/48) - Quantum statistical distributions
- `docs/QUANTUM_PROBABILITY_FEASIBILITY.md` - Feasibility analysis
- `docs/FINANCIAL_ADVISOR_RECOMMENDATIONS.md` - Theory overview

## Status

✅ **Fully Implemented** - All features from plan are complete:
- ✅ Core quantum probability calculator
- ✅ Bubble detection with improved formulas
- ✅ Value trap detection
- ✅ Quantum scoring metrics
- ✅ Ensemble integration with tag assigner
- ✅ Ensemble integration with opportunity calculators
- ✅ Comprehensive unit tests
- ✅ Integration tests
- ✅ Documentation

**System is ready for autonomous operation.**
