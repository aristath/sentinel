# Rolling contribution history

`sentinel/planner/deposit_history.py` provides the six-month contribution rates
used by planning and portfolio projections. `DepositHistoryHelper` accepts
injected database/currency services or uses their shared instances.

## Window

The window ends on today or an explicit `as_of_date` and starts 180 days
earlier. It deliberately uses six 30-day months rather than calendar-month
boundaries. Each amount is converted to EUR using the rate for its cash-flow
date.

## Deposit rate

```python
average = await helper.get_rolling_6m_avg_deposit(as_of_date=None)
```

This includes only `card` deposits and returns:

```text
EUR deposits in trailing window / 6
```

The unit is EUR per month, not average transaction size. No deposits returns
zero.

## Net contribution rate

```python
average = await helper.get_rolling_6m_avg_net_deposit(as_of_date=None)
```

This adds `card` deposits and subtracts the absolute value of `card_payout`
withdrawals, then divides by six. Dividends, fees, taxes, blocks, and unblocks
are excluded because they are not external contribution capital.

The planner and `/api/portfolio/value-projection` use this net rate. An API
projection override changes the scenario but does not rewrite cash-flow
history. In the Portfolio value UI, select the displayed `6M net/mo` amount to
edit the projection assumption; `Reset` restores the live rolling rate.

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
