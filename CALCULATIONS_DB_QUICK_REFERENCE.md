# Calculations Database - Quick Reference Guide

## Quick Start

### Using CalculationsRepository

```python
from app.repositories.calculations import CalculationsRepository

calc_repo = CalculationsRepository()

# Get a cached metric
rsi = await calc_repo.get_metric("AAPL", "RSI_14")
if rsi is None:
    # Calculate and cache
    rsi = calculate_rsi(closes)
    await calc_repo.set_metric("AAPL", "RSI_14", rsi)

# Batch operations
metrics = await calc_repo.get_metrics("AAPL", ["RSI_14", "EMA_200", "SHARPE"])
await calc_repo.set_metrics("AAPL", {
    "RSI_14": 45.2,
    "EMA_200": 150.5,
    "SHARPE": 1.8
})
```

### Using Technical Indicator Functions

All technical indicator functions now check cache automatically:

```python
from app.domain.scoring.technical import get_rsi, get_ema, get_sharpe_ratio

# These functions check cache first, calculate if needed
rsi = await get_rsi(symbol, closes_array)
ema = await get_ema(symbol, closes_array, length=200)
sharpe = await get_sharpe_ratio(symbol, closes_array)
```

## Metric Names

### Technical Indicators
- `RSI_14`, `RSI_30` - Relative Strength Index
- `EMA_50`, `EMA_200` - Exponential Moving Average
- `BB_LOWER`, `BB_MIDDLE`, `BB_UPPER` - Bollinger Bands
- `BB_POSITION` - Position within Bollinger Bands (0-1)
- `DISTANCE_FROM_EMA_200` - Percentage distance from EMA

### Performance Metrics
- `CAGR_5Y`, `CAGR_10Y` - Compound Annual Growth Rate
- `SHARPE` - Sharpe Ratio
- `SORTINO` - Sortino Ratio
- `MAX_DRAWDOWN` - Maximum drawdown
- `CURRENT_DRAWDOWN` - Current drawdown
- `VOLATILITY_30D`, `VOLATILITY_ANNUAL` - Volatility

### Momentum & Price
- `MOMENTUM_30D`, `MOMENTUM_90D` - Price momentum
- `HIGH_52W`, `LOW_52W` - 52-week high/low
- `DISTANCE_FROM_52W_HIGH` - Distance from 52W high

### Fundamentals
- `PE_RATIO`, `FORWARD_PE` - Price-to-Earnings ratios
- `PROFIT_MARGIN` - Profit margin
- `DEBT_TO_EQUITY` - Debt-to-equity ratio
- `CURRENT_RATIO` - Current ratio
- `FINANCIAL_STRENGTH` - Aggregate financial strength score

### Dividends
- `DIVIDEND_YIELD` - Dividend yield
- `PAYOUT_RATIO` - Payout ratio
- `DIVIDEND_CONSISTENCY` - Dividend consistency score

### Opinion
- `ANALYST_RECOMMENDATION` - Analyst recommendation score (0-1)
- `PRICE_TARGET_UPSIDE` - Price target upside percentage

## TTL Reference

| Metric Category | TTL | Examples |
|----------------|-----|----------|
| Real-time | 24 hours | RSI, EMA, Bollinger, Momentum, 52W High/Low |
| Daily | 7 days | Sharpe, Sortino |
| Weekly | 7 days | CAGR_5Y, CAGR_10Y, Consistency Score |
| Quarterly | 30 days | P/E, Profit Margin, Debt/Equity, Dividend Yield |
| On-demand | 24 hours | Analyst Recommendation, Price Target |

## Common Patterns

### Pattern 1: Check Cache, Calculate if Needed

```python
calc_repo = CalculationsRepository()
metric = await calc_repo.get_metric(symbol, "RSI_14")
if metric is None:
    metric = calculate_rsi(closes)  # Expensive calculation
    await calc_repo.set_metric(symbol, "RSI_14", metric)
```

### Pattern 2: Using Async Wrappers (Recommended)

```python
from app.domain.scoring.technical import get_rsi

# Automatically checks cache and calculates if needed
rsi = await get_rsi(symbol, closes_array)
```

### Pattern 3: Batch Operations

```python
# Get multiple metrics at once
metrics = await calc_repo.get_metrics(symbol, [
    "RSI_14", "EMA_200", "SHARPE", "CAGR_5Y"
])

# Store multiple metrics (each gets its own TTL)
await calc_repo.set_metrics(symbol, {
    "RSI_14": 45.2,
    "EMA_200": 150.5,
    "SHARPE": 1.8,
    "CAGR_5Y": 0.12
})
```

### Pattern 4: Override TTL

```python
# Use custom TTL instead of default
await calc_repo.set_metric(
    symbol, 
    "CUSTOM_METRIC", 
    value, 
    ttl_override=3600  # 1 hour
)
```

## Maintenance

### Cleanup Expired Metrics

```python
from app.repositories.calculations import CalculationsRepository

calc_repo = CalculationsRepository()
deleted_count = await calc_repo.delete_expired()
```

This is automatically called during daily maintenance.

### Get All Metrics for a Symbol

```python
all_metrics = await calc_repo.get_all_metrics("AAPL")
# Returns: {"RSI_14": 45.2, "EMA_200": 150.5, ...}
```

## Troubleshooting

### Metric Not Found

If `get_metric()` returns `None`:
1. Check if metric name is correct (case-sensitive)
2. Check if metric has expired (TTL passed)
3. Verify metric was stored with correct symbol (uppercase)

### TTL Not Working

- TTL is automatically looked up from `METRIC_TTL` in `constants.py`
- Unknown metrics use `DEFAULT_METRIC_TTL` (24 hours)
- Override with `ttl_override` parameter if needed

### Performance Issues

- Use batch operations (`get_metrics`, `set_metrics`) when possible
- Metrics calculation job pre-calculates expensive metrics
- Check cache hit rates in logs

## Migration

After deploying, run:
```bash
python scripts/migrate_v5_remove_score_cache.py
```

This removes old ScoreCache entries from `cache.db`.

