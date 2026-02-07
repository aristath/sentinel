# Deterministic Contrarian Strategy

This document describes the current production strategy used by Sentinel.

## Objective

- Stay fully invested across a curated universe.
- Buy quality names more aggressively when they are temporarily discounted.
- Keep risk bounded with lot-aware sizing, sleeve caps, and execution guards.

## Core Signal

For each symbol, Sentinel computes a deterministic `opp_score` from price history:

- `dip_score`: discount vs recent highs.
- `capitulation_score`: recent drawdown intensity.
- `cycle_turn`: confirmation that downside momentum is flattening or turning.
- `freefall_block`: guard that suppresses buying during unresolved freefall.

These components are implemented in `sentinel/strategy/contrarian.py`.

## Allocation Model

- Universe is split into sleeves (`core` and `opportunity`).
- Core sleeve is a stable baseline allocation.
- Opportunity sleeve tilts capital toward highest `opp_score` names.
- Per-symbol target is then constrained by lot-aware trade feasibility and portfolio limits.

Allocation logic lives in `sentinel/planner/allocation.py`.

## Execution Model

Rebalance recommendations in `sentinel/planner/rebalance.py` apply:

- Conviction multiplier from user settings.
- Price anomaly blocking (`sentinel/price_validator.py`).
- Lot-size class constraints for high-ticket symbols.
- Minimum trade value and fee-aware practicality checks.

## Data Requirements

- OHLCV history from TraderNet.
- Live quotes and current positions.
- No machine-learning models, wavelet transforms, or regime detectors.

## Operational Notes

- Scheduler drives sync and trading jobs.
- Settings remain runtime-configurable through the UI.
- Backtests run point-in-time pricing via `as_of_date` paths.
