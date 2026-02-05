# Portfolio / Planner / ML Logic Audit Findings (2026-02-05)

Scope: logic flaws and bug risks found during a codebase review, focusing on portfolio handling, planning/rebalancing, trading execution, FX, and ML feature/prediction flow.

> Note: This document started as descriptive only (planning mode). The cash double-counting issues below have since been fixed in code.

## Status snapshot

- Tests: `pytest` passes (666).
- Lint: `ruff check .` passes.
- Typecheck: `pyright` emits warnings (many in scripts/tests; a few in runtime modules).

## Completion Summary (2026-02-05)

### ✅ Fully Completed:
- **#1**: Allocations now use invested-only denominator (cash excluded)
- **#3**: Backtest/as-of-date sizing honored (uses `get_invested_value_eur(as_of_date)`)
- **#6**: Deficit sells use historical prices when `as_of_date` is provided

### 🔧 Partially Addressed:
- **#4**: Planner cash constraint - Funding sells feature now generates explicit sells to fund buys before scaling, reducing cash constraint issues
- **#23**: Unified endpoint allocation math - Now consistent with planner (both use invested-only denominators)

## Key findings (prioritized)

### A) Accounting / portfolio correctness

~~1) **Allocations are calculated as % of (positions + cash)**~~ ✅ COMPLETED (2026-02-05)
   - `PortfolioAnalyzer.get_current_allocations()` divides each position EUR value by `Portfolio.total_value()`.
   - This makes allocations shrink when cash increases, potentially triggering buys even if invested mix is fine.
   - Location: `sentinel/planner/analyzer.py:43-65`, `sentinel/portfolio.py:74-89`
   - **Fixed**: Now uses `invested_value_eur` (positions only) as denominator.

~~3) **Backtest/as-of-date is not fully honored across planner sizing**~~ ✅ COMPLETED (2026-02-05)
   - `Planner.get_recommendations(as_of_date=...)` passes `as_of_date` into `RebalanceEngine`, but still computes `total_value` using live portfolio (`Portfolio.total_value()` has no as-of-date).
   - Impact: backtest recommendations can be sized against today’s value/cash/positions.
   - Location: `sentinel/planner/planner.py:102-112`, `sentinel/portfolio.py:74-89`

### B) Cash / FX / execution feasibility

4) **Planner cash constraint is EUR-only (but execution does auto-FX)**
   - `_apply_cash_constraint` treats current cash + sell proceeds as fungible EUR budget.
   - Execution uses `Security.buy(auto_convert=True)` which can convert EUR to target currency (and sometimes other currencies to EUR).
   - Risk remains if conversion fills/settlement timing differs or broker requires per-currency cash with constraints.
   - Locations:
     - `sentinel/planner/rebalance.py:487-683`
     - `sentinel/security.py:189-296`

5) **Cool-off logic uses wall-clock time, not as-of-date**
   - `RebalanceEngine._check_cooloff_violation()` uses `datetime.now()`; so does `Security._has_recent_trade()`.
   - Backtests and simulations can be blocked/allowed incorrectly.
   - Locations:
     - `sentinel/planner/rebalance.py:409-443`
     - `sentinel/security.py:147-155`

~~6) **Deficit sells (negative balances) use live position prices even when as-of-date is provided**~~ ✅ COMPLETED (2026-02-05)
   - `_generate_deficit_sells(..., as_of_date)` uses positions table `current_price`.
   - Scores may be as-of-date, but prices are not.
   - Location: `sentinel/planner/rebalance.py:724-835`
   - **Fixed**: Now uses historical close prices when `as_of_date` is provided.

### C) ML feature/prediction flow

7) **Feature extraction ignores the `date` argument (implicit “use last row”)**
   - `FeatureExtractor.extract_features(symbol, date, price_data, ...)` does not slice to `<= date`; it computes using `.iloc[-1]` and rolling stats over full DF.
   - If DB price series is stale, caching under `features:{symbol}:{today}` can store yesterday’s features labeled as today.
   - Locations:
     - `sentinel/planner/rebalance.py:147-158`, `:232-268`
     - `sentinel/ml_features.py:187-216` (and subsequent indicators)

8) **Backtest uses recommendations-cache skip but not ML prediction cache skip**
   - `RebalanceEngine` skips planner cache when `as_of_date` is set.
   - It does not pass `skip_cache=True` to `MLPredictor.predict_and_blend()`.
   - Impact: backtest runs can reuse stale cached predictions for the same `symbol:date`.
   - Locations:
     - `sentinel/planner/rebalance.py:85-91`, `:164-171`
     - `sentinel/ml_predictor.py:74-81`, `:152-154`

9) **ML prediction writes to DB during “planning” reads**
   - `MLPredictor.predict_and_blend()` stores predictions in `ml_predictions` every call (unless an exception).
   - Polling recommendations can bloat DB and mix “decision support” calls with “tracking”.
   - Location: `sentinel/ml_predictor.py:125-154`, `:210-257`

### D) Ideal allocation algorithm

10) **Diversification scoring doesn’t align with current allocation’s “Unknown” behavior**
   - `Portfolio.get_allocations()` maps missing geo/industry to `"Unknown"`.
   - `AllocationCalculator._calculate_diversification_score()` does not; empty lists => no deviations => 0 score.
   - Location: `sentinel/portfolio.py:191-204`, `sentinel/planner/allocation.py:58-86`

11) **Min-position constraint can be violated after renormalization**
   - Values are clamped to `[min_position, max_position]` then rescaled to sum to allocable.
   - Rescaling can push positions below `min_position`.
   - Location: `sentinel/planner/allocation.py:219-229`

12) **Conviction adjustment is additive and unclamped**
   - `(user_multiplier - 1.0) * 0.3` can push scores beyond expected bounds.
   - Designed to allow overriding signals, but it’s a fixed absolute delta.
   - Location: `sentinel/utils/scoring.py:9-33`

## Execution sequencing

- SELL-before-BUY is implemented both in planner ordering and in job execution (intended to fund buys).
- Locations:
  - Planner sort: `sentinel/planner/rebalance.py:209-211`
  - Job execution: `sentinel/jobs/tasks.py:407-429`

## Recommendations (design-level, not code)

1) Define the system’s canonical notion of “portfolio value” (with or without cash) and use it consistently across:
   - allocation %,
   - rebalance sizing,
   - reported profit metrics.

2) Make `as_of_date` a first-class parameter through the whole planning stack (prices, cash, positions, scores, cool-off time).

3) Decide the FX model explicitly:
   - if auto-FX is assumed, incorporate expected FX fees/spreads and execution timing,
   - if not, planner should emit explicit FX steps or enforce per-currency budgets.

4) Fix ML temporal consistency:
   - slice features “as of date”,
   - ensure backtests skip prediction caches,
   - avoid writing prediction rows for read-only planning calls (or gate behind a setting).

5) Align planner fee model with broker commissions:
   - optionally compute a rolling average commission by market/symbol to estimate feasibility more accurately.

## Snapshots & PnL history (API `/portfolio/pnl-history`)

13) **Request-path snapshot backfill can be expensive and surprising**
   - `GET /portfolio/pnl-history` calls `db.get_portfolio_snapshots(days + 44)` first.
   - It then checks `db.get_latest_snapshot_date()` and, if missing or stale vs `date.today()`, runs `SnapshotService.backfill()` inside the request path.
   - Impact:
     - slow responses/timeouts when the DB is behind (especially on first call),
     - competing with other startup/background tasks,
     - “read” API endpoint triggers heavy writes and broker fetches.
   - Location: `sentinel/api/routers/portfolio.py:69-78`

14) **`pnl_pct` denominator heuristic changes when net deposits increase**
   - The endpoint computes `pnl_eur` as `unrealized_pnl_eur` (if present) else `total_value - net_deposits`.
   - It then uses `denominator = net_deposits` except when deposits increased vs the previous snapshot, where it uses the *previous* net deposits.
   - Impact:
     - discontinuous percentage series around deposit events,
     - can mislead the UI into showing “better” or “worse” returns depending on deposit timing.
   - Location: `sentinel/api/routers/portfolio.py:85-96`

15) **Misleading naming: `actual_ann_return` is not annualized**
   - Docstring says “annualized”, variable name includes `_ann_`, but the calculation is `(cumulative - 1) * 100` over a 30-day rolling TWR window.
   - Comment explicitly says “No annualization”.
   - Impact: UI/consumers may interpret this as annual return when it’s actually ~30-day rolling return %.
   - Location: `sentinel/api/routers/portfolio.py:132-157`, `sentinel/api/routers/portfolio.py:118-119`

16) **Ad-hoc mapping from wavelet score → “return %”**
   - `wavelet_ann_return` is derived from an average wavelet score using:
     - `((avg_w - 0.05) / 1.5) / 12.0 * 100`
   - This is a brittle calibration baked into the API route.
   - Impact:
     - mixing of “signal score” units with return units,
     - unclear calibration and hard to validate, easy to break if analyzer score scaling changes.
   - Location: `sentinel/api/routers/portfolio.py:158-176`

17) **Mixed horizons/semantics in one chart series**
   - `actual_ann_return`: 30-day rolling TWR (%).
   - `ml_ann_return`: averages `return_20d` and shows as %.
   - `wavelet_ann_return`: score mapped to “monthly %” via heuristic.
   - Impact: plotted lines are not strictly comparable (different horizons, units, and calibration).
   - Location: `sentinel/api/routers/portfolio.py:132-189`

## Frontend consumption notes (web)

- Unified UI calls both:
  - `GET /cashflows` (query key `cashflows`) via `getCashFlows()`
  - `GET /portfolio/pnl-history` (query key `portfolio-pnl`) via `getPortfolioPnLHistory()`
  - Location: `web/src/pages/UnifiedPage.jsx:109-119`, `web/src/api/client.js:187-192`

19) **Cashflow endpoint profit bug is user-visible in Unified UI**
   - Unified UI displays `cashFlows.total_profit` directly as “Total Profit”.
   - Since `/cashflows` currently double-counts cash, the displayed “Total Profit” is overstated by current cash balance.
   - Location:
     - UI: `web/src/pages/UnifiedPage.jsx:411-429`
     - API: `sentinel/api/routers/trading.py:116-130`

20) **Chart/UI naming mismatch reinforces confusion**
   - `PortfolioPnLChart` is documented as “annualized return %”, but the API currently returns 30-day rolling returns (%) and mixes horizons/units across actual/wavelet/ML series.
   - Impact: the UI likely labels/interprets the plotted values as annualized even when they are not.
   - Location: `web/src/components/PortfolioPnLChart.jsx:1-9`, `sentinel/api/routers/portfolio.py:118-119`, `:132-157`

21) **Portfolio value is double-counted end-to-end in the UI status bar**
   - Backend `/portfolio`:
     - `Portfolio.total_value()` already includes cash.
     - `PortfolioService.get_portfolio_state()` then sets `total_value_eur = total + total_cash_eur`.
   - Frontend Unified UI:
     - Displays “Portfolio:” as `portfolio.total_value_eur`.
     - Displays “Cash:” as `portfolio.total_cash_eur`.
   - Impact:
     - Top-line “Portfolio” number is overstated by cash, and the UI effectively presents (positions+cash) + cash.
   - Location:
     - API: `sentinel/services/portfolio.py:41-82`, `sentinel/portfolio.py:74-89`
     - UI: `web/src/pages/UnifiedPage.jsx:339-371`

22) **Total-value semantics vary by endpoint (cash included vs excluded)**
   - `Portfolio.total_value()` includes cash.
   - Unified endpoint (`/unified`) computes `total_value` from positions only (no cash) for internal calculations.
   - Snapshot backfill (`SnapshotService`) defines `total_value_eur = positions_value_eur + running_cash_eur`.
   - Impact: callers may compare or combine “total value” numbers that are not measuring the same thing.
   - Location:
     - `sentinel/portfolio.py:74-89`
     - `sentinel/api/routers/securities.py:315-327`
     - `sentinel/snapshot_service.py:321-334`

23) **Unified endpoint “post_plan_allocation” math ignores cash entirely**
   - `/unified` computes `post_plan_total_value` from positions only and adjusts it by the net effect of recommendations.
   - It then computes `post_plan_allocation = post_plan_value / post_plan_total_value`.
   - Because cash is excluded, “allocation” here is effectively “% of invested positions”, not “% of total portfolio (positions+cash)”.
   - Impact:
     - UI allocation numbers can’t be compared directly to planner allocations if the planner treats cash as part of total portfolio value.
     - Post-plan allocation can look “too high” when the plan leaves large cash balances.
   - Location: `sentinel/api/routers/securities.py:315-327`, `:386-391`

24) **Planner current allocations include cash in denominator, but not in numerator**
   - `PortfolioAnalyzer.get_current_allocations()` divides each position EUR value by `Portfolio.total_value()`.
   - Since `Portfolio.total_value()` includes cash, the resulting allocations are “% of (positions+cash)”.
   - Meanwhile the numerator is positions only.
   - Impact:
     - As cash increases, every position’s allocation shrinks even if the invested mix is unchanged.
     - This can amplify buy recommendations in cash-heavy periods and is inconsistent with `/unified` allocation math (positions-only denominator).
   - Location: `sentinel/planner/analyzer.py:43-65`, `sentinel/portfolio.py:74-89`

25) **Potential FX conversion bug pattern in planner allocations: `value_local * rate`**
   - In `PortfolioAnalyzer.get_current_allocations()`, position EUR value is computed as `value_local * rate` where `rate = Currency.get_rate(pos_currency)`.
   - In `Currency`, `get_rate(curr)` returns “1 curr = X EUR” (because Tradernet rates are inverted at ingestion), so `to_eur(amount, curr)` correctly uses `amount * rate`.
   - This appears consistent *if* `rate` is indeed “to EUR”. However, elsewhere conversions use `Currency.to_eur(...)` directly, and having one-off manual conversion code increases the risk of inversion mistakes if semantics ever change.
   - Recommendation: use `await self._currency.to_eur(value_local, pos_currency)` for clarity and single-source-of-truth.
   - Location: `sentinel/planner/analyzer.py:59-65`, `sentinel/currency.py:97-103`

26) **Planner allocation cache is only written by the same method (limited value + staleness risk)**
   - `sentinel.database.Database` does resolve to `sentinel/database/main.py:Database` (so `cache_set` exists).
   - However, the key `planner:current_allocations` is only written inside `PortfolioAnalyzer.get_current_allocations()` itself.
   - If positions/cash/prices change, the cache may serve stale allocations for up to 5 minutes unless something explicitly clears it.
   - Location: `sentinel/planner/analyzer.py:38-71`, `sentinel/database/main.py:251-277`, `sentinel/database/__init__.py:7-9`

27) **`/cashflows` redundantly converts cash again, increasing drift risk**
   - The endpoint calls `Portfolio.total_value()` which already includes cash (via `total_cash_eur()`).
   - It then separately fetches cash balances and re-converts to EUR for `total_cash_eur`.
   - This not only double-counts, it can diverge if FX rates used in `deps.currency` vs `Portfolio._currency` differ or are out-of-sync.
   - Location: `sentinel/api/routers/trading.py:116-130`, `sentinel/portfolio.py:74-89`

## Next audit targets

- Verify snapshot schema semantics:
  - `SnapshotService` writes `total_value_eur = positions_value_eur + running_cash_eur` (cash included) and `unrealized_pnl_eur = total_value_eur - cumulative_net_deposits_eur`.
  - Location: `sentinel/snapshot_service.py:321-334`
- Decide canonical return/return-label semantics and align both:
  - backend endpoint field names/docstrings
  - frontend chart legend/labels
