# Rolling contribution history

`sentinel/planner/deposit_history.py` provides configurable rolling contribution
rates used by planning and portfolio projections. `DepositHistoryHelper`
accepts injected database, currency, and settings services or uses their shared
instances.

## Window

The window ends on today or an explicit `as_of_date`. Its length comes from
`strategy_deposit_history_months`, which accepts whole numbers from 1 through
36 and defaults to 12. Each configured month represents 30 days rather than a
calendar-month boundary. Each amount is converted to EUR using the rate for its
cash-flow date.

## Deposit rate

```python
average = await helper.get_rolling_avg_deposit(as_of_date=None)
```

This includes only `card` deposits and returns:

```text
EUR deposits in trailing window / configured months
```

The unit is EUR per month, not average transaction size. No deposits returns
zero.

## Net contribution rate

```python
average = await helper.get_rolling_avg_net_deposit(as_of_date=None)
```

This adds `card` deposits and subtracts the absolute value of `card_payout`
withdrawals, then divides by the configured number of months. Dividends, fees,
taxes, blocks, and unblocks are excluded because they are not external
contribution capital.

The planner and `/api/portfolio/value-projection` use this net rate. An API
projection override changes the scenario but does not rewrite cash-flow
history. In the Portfolio value UI, the label reflects the configured window
(for example, `12M net/mo`). Select the amount to edit the projection
assumption; `Reset` restores the live rolling rate.

## FIRE panel

The `FIRE (Financial Independence, Retire Early)` panel combines the portfolio
projection with the `fire_monthly_expenses_eur` database setting for estimated
monthly household expenses on retirement. Its F.U. Money target is 25 times
annual expenses:

```text
F.U. Money = monthly expenses × 12 × 25
```

The panel identifies the first month that reaches the target and reports its
year plus whole years remaining, rounded up from the projected month count.
Monthly expenses are entered in today's prices, then compounded by the editable
expected annual inflation rate to every candidate retirement month. The
portfolio must reach 25 times those inflation-adjusted annual expenses.
The default `2.11%` rate is the arithmetic mean of Eurostat's Greece all-items
HICP annual inflation rates for 2016 through 2025
([dataset `prc_hicp_aind`](https://ec.europa.eu/eurostat/en/web/products-datasets/-/PRC_HICP_AIND),
`geo=EL`, `coicop=CP00`, `unit=RCH_A_AVG`).

The table remains a 25-year view; when necessary, the FIRE date continues the
same historical money-weighted return, `Net/mo`, and inflation recurrence
beyond that display window. If fixed assumptions cannot reach the moving
inflation-adjusted target, the panel says so instead of inventing a date. The
corresponding 4% withdrawal rate is an annual rate paid in monthly installments;
it is not a 4% monthly withdrawal. After retirement, that withdrawal amount
must continue rising with inflation to preserve the entered purchasing power.
Changing the `Net/mo` or inflation assumption also updates the projected FIRE
year.

## Planner meaning

The rebalance engine uses expected near-term contributions when translating
ideal percentages into EUR targets and when estimating how long deposits could
correct a gap. If the net rate is zero or negative, a positive gap has no finite
deposit-only correction time.

The helper supplies a rate; it does not itself decide whether to trade. Timing,
funding, minimum trade value, and opportunity rules remain in the rebalance
engine.

## Historical calculations

`as_of_date` accepts `YYYY-MM-DD` or an ISO datetime. This is used for
point-in-time tests/backtests so future cash flows are excluded.

## Tests

```bash
source .venv/bin/activate
pytest tests/test_planner_deposit_history.py -v
```

See [Strategy](strategy_contrarian.md) and [Portfolio API](api/portfolio.md#get-apiportfoliovalue-projection).
