# Deposit History Helper

**File**: `sentinel/planner/deposit_history.py`

## Overview

This module provides helpers for calculating rolling averages of contribution cashflows. It's used by the planner to determine how quickly the portfolio can self-correct allocation drifts through regular deposits.

## Key Concept: Self-Correction Time

The planner uses deposit history to answer:
> "If we skip trading this cycle, how many months until regular deposits naturally bring allocations back to target?"

This is the core of the **"Patience"** principle in Sentinel's rebalancing philosophy:

- Don't trade just because allocations drifted
- Let monthly deposits handle the drift
- Only trade when there's a clear contrarian opportunity

## Data Structures

### `DepositHistoryHelper`

Main class for cashflow analytics:

```python
from sentinel.planner.deposit_history import DepositHistoryHelper

helper = DepositHistoryHelper(db, currency)
avg_deposit = await helper.get_rolling_6m_avg_deposit()
```

## Key Methods

### `get_rolling_6m_avg_deposit(as_of_date: Optional[str] = None) -> float`

Calculates average **monthly** deposit rate over trailing 6 months.

**Important**: This is a **deposit rate** (EUR/month), not average deposit size.

**Calculation**:

```
total_deposits_6m / 6 = avg_monthly_deposit_rate
```

**Usage**:

```python
# How many months to self-correct a 500 EUR excess?
excess_eur = 500
avg_deposit = await helper.get_rolling_6m_avg_deposit()
months_to_self_correct = excess_eur / avg_deposit  # e.g., 500 / 100 = 5 months
```

**Parameters**:

- `as_of_date`: Optional date string (YYYY-MM-DD or ISO datetime)
  - Used for backtesting/simulation
  - Defaults to current date if None

**Returns**:

- `float`: Average monthly deposit in EUR
- `0.0`: If no deposits found in window

### `get_rolling_6m_avg_net_deposit(as_of_date: Optional[str] = None) -> float`

Calculates average monthly **net** contribution (deposits minus withdrawals).

**What's included**:

- `card`: Credit card deposits (ADD to account)
- `card_payout`: Credit card withdrawals (REMOVE from account)

**What's excluded**:

- Dividends (already reflected in portfolio value)
- Fees/taxes (already reflected in portfolio value)

**Calculation**:

```
(total_deposits - total_withdrawals) / 6 = avg_net_deposit_rate
```

## Database Dependencies

### Cashflow Types

Sentinel tracks multiple cashflow types in the `cashflows` table:

| Type | Description | Included in Net? |
|---|---|---|
| `card` | Credit card deposit | ✅ Yes (+) |
| `card_payout` | Credit card withdrawal | ✅ Yes (-) |
| `dividend` | Dividend payment | ❌ No |
| `fee` | Broker fee | ❌ No |
| `tax` | Tax payment | ❌ No |

### Currency Conversion

All amounts are converted to EUR using historical FX rates:

```python
amount_eur = await currency.to_eur_for_date(
    amount=cashflow["amount"],
    currency=cashflow["currency"],
    date=cashflow["date"]
)
```

## Usage in Planner

### Example: Patience Check

```python
from sentinel.planner.deposit_history import DepositHistoryHelper
from sentinel.currency import Currency
from sentinel.database import Database

db = Database()
currency = Currency()
helper = DepositHistoryHelper(db, currency)

# Get current allocation drift
excess_above_target = 500.0  # EUR

# Calculate self-correction time
avg_deposit = await helper.get_rolling_6m_avg_deposit()
months_to_self_correct = excess_above_target / avg_deposit

# Patience rule: don't trade if < 3 months to self-correct
if months_to_self_correct < 3:
    print("Skip trade - deposits will handle it")
else:
    print("Consider trade - significant drift")
```

### Example: Backtesting with Historical Date

```python
# Simulate as of 2025-01-01
as_of = "2025-01-01"
avg_deposit = await helper.get_rolling_6m_avg_deposit(as_of)

# This looks at cashflows from 2024-07-01 to 2025-01-01
```

## Implementation Details

### Window Resolution

```python
def _resolve_window(as_of_date: Optional[str]) -> tuple[date, date]:
    if as_of_date is None:
        end_date = date.today()
    elif len(as_of_date) > 10:  # ISO datetime
        end_date = datetime.fromisoformat(as_of_date).date()
    else:  # YYYY-MM-DD
        end_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()

    return end_date - timedelta(days=30 * 6), end_date  # 6 months back
```

### Date Range Calculation

Uses **30-day months** for simplicity:

- 6 months = 180 days
- Not calendar months (avoids edge cases with varying month lengths)

## Testing

Tests located in `tests/test_planner_deposit_history.py`

Key test scenarios:

- Empty cashflow history (returns 0.0)
- Single deposit in window
- Multiple deposits across window
- Withdrawals reduce net deposit
- Currency conversion for non-EUR deposits
- Date parsing (ISO vs YYYY-MM-DD)
- Backtesting with historical dates

## Common Pitfalls

### 1. Deposit Rate vs Deposit Size

```python
# WRONG: Confusing rate with average deposit
avg_deposit = await helper.get_rolling_6m_avg_deposit()  # EUR/month
# This is NOT the average size of individual deposits!

# Example:
# 3 deposits of 100 EUR in 6 months = 300 EUR total
# avg_deposit = 300 / 6 = 50 EUR/month (deposit RATE)
# NOT 100 EUR (average deposit SIZE)
```

### 2. Zero Division

```python
avg_deposit = await helper.get_rolling_6m_avg_deposit()
if avg_deposit > 0:
    months = excess / avg_deposit
else:
    # Handle case: no deposits in window
    months = float('inf')
```

### 3. Cashflow Type Filtering

Only `card` and `card_payout` are included in net deposit calculation. Other types like `dividend`, `fee`, `tax` are intentionally excluded.

## Related Documentation

- [Rebalance Philosophy](../AGENTS.md#rebalance-philosophy-shift) - Patience principle
- [Planner: Rebalance](../sentinel/planner/rebalance.py) - Uses deposit history for patience checks
- [Cashflows API](../sentinel/api/routers/trading.py#cashflows_router) - Cashflow management
