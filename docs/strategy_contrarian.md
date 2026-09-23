# Portfolio strategy and execution

Sentinel separates the long-term destination from short-term timing:

- AI research ratings determine which buyable securities belong in the ideal
  portfolio and their relative target weights.
- Deterministic price signals determine when a target gap is attractive to buy.
- Optional forecasts may make a bounded adjustment to timing; they do not set
  target weights.
- Planner constraints determine whether the idea is executable.

## Ideal allocation

Each active security has an `ai_research_multiplier` from 0 through 1. A value
of 0.5 is neutral. Securities below `strategy_ideal_qualifying_threshold`, or
with buying disabled, receive no ideal weight. Qualifying ratings are converted
to positive tilts with `ai_research_multiplier_strength`, normalized, and
water-filled under `max_position_pct`.

`target_cash_pct` reserves the configured portfolio fraction; with the default
zero target Sentinel aims to deploy all feasible capital. If the position cap
and eligible-universe size make full investment impossible, the remainder is
represented as cash rather than violating the cap.

Stored ratings are the effective values. The fixed
`decay:ai_research_multipliers` job periodically moves stale ratings toward 0.5;
there is no second read-time fade.

## Deterministic timing signal

`compute_contrarian_signal()` uses at least 130 daily closes and calculates:

| Field | Meaning |
|---|---|
| `dd252` | Current drawdown from the trailing high (up to 252 closes) |
| `rsi14` | Fourteen-period relative strength index |
| `mom20`, `mom60`, `mom120` | Price momentum over those lookbacks |
| `vol20`, `vol_ratio` | Recent volatility and its ratio to the longer window |
| `dip_score` | Normalized depth of drawdown |
| `capitulation_score` | Normalized oversold RSI contribution |
| `cycle_turn` | Short momentum has improved enough to indicate a turn |
| `freefall_block` | Severe falling momentum with elevated volatility |
| `opp_score` | Weighted dip/capitulation/turn score, zeroed during freefall |

The raw opportunity score is:

```text
0.5 * dip_score + 0.3 * capitulation_score + 0.2 * cycle_turn
```

A recent deep drawdown may retain a bounded entry-memory boost after the price
turns, controlled by the entry thresholds, memory window, and maximum boost.
The boost never applies during freefall or before a detected turn.

When enabled and fresh, the forecast score adjusts this timing score by
`forecasting_timing_weight`. Backtests/as-of calculations do not read today's
forecast state.

## Core and opportunity labels

`core` and `opportunity` are dynamic execution labels, not fixed pools of
capital. An ideal holding is labeled opportunity when its current timing score
meets `strategy_min_opp_score`; otherwise it is core. The label controls entry,
cool-off, tranche, and exit rules but does not alter the long-term AI-derived
target percentage.

Opportunity entries ladder through configured drawdown stages. A deeper stage
may add another tranche even during the ordinary same-side cool-off. Coarse
lots are restricted; a jumbo minimum ticket cannot open a new position.
Opportunity holdings also have staged profit-taking, momentum-rollover, and
time-stop rotation rules.

Core target gaps remain candidates. Timing decides their rank, and a fallback
path can eventually converge toward the ideal instead of waiting forever for a
perfect dip.

## Recommendation construction

The rebalance engine:

1. values current positions and cash in EUR;
2. projects near-term capital using the configured rolling net contribution;
3. compares projected target value with current value;
4. filters unavailable, blocked, anomalous, disallowed, cooling-down, sub-lot,
   and sub-minimum trades;
5. caps buys at the maximum position value;
6. ranks executable buys by opportunity timing, target gap, research rating,
   and EUR gap; and
7. adds only the funding sells needed for the selected buy, subject to turnover
   and sell-count limits.

An ordinary overweight is a funding source, not a standalone sell instruction.
Lifecycle exits and explicit research downgrades are separate sell reasons.
Never-rated neutral securities are not treated as explicit downgrades.

Price anomaly detection can block a trade even when every strategy condition
passes. All quantities respect broker lot sizes and configured fee/minimum-value
economics.

## Execution safety

- `research` mode produces plans but submits no broker trades.
- `live` mode permits the trading job to submit the selected executable action.
- `allow_buy` and `allow_sell` are hard gates.
- Broker/market availability, quote validity, cash, lots, caps, and fees remain
  authoritative.
- A later planning cycle uses broker-confirmed state; the planner does not assume
  an order filled merely because it was submitted.

See [Configuration](configuration.md) for every strategy setting, [Planner API](api/planner.md)
for returned data, and [Forecasting](forecasting.md) for the optional timing
input.

## Tests

```bash
source .venv/bin/activate
pytest tests/test_strategy_contrarian.py tests/test_planner.py tests/test_planner_new_philosophy.py -v
```
