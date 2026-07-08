# Portfolio Composition & Analytics

**File**: `sentinel/portfolio_composition.py` (41KB)

## Overview

This module provides portfolio analytics and composition breakdowns that power the web UI sidebar. It replaces the defunct Freedom24 PRAAMS analysis with Sentinel's own computed metrics.

## Key Features

### Composition Breakdowns

Returns portfolio allocation percentages by:

- **Country**: Geographic exposure based on security metadata
- **Continent**: Aggregated geographic regions
- **Industry**: TRBC industry classification
- **Currency**: Base currency of each security
- **Asset Class**: Stock vs ETF vs other (from `instr_kind_c`)

### Time-Series Metrics (from `portfolio_snapshots` table)

- **1Y / 5Y Total Return**: Compound annual growth rate
- **Annualized Volatility**: Standard deviation of daily returns
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted return (assumes 2% risk-free rate)
- **Beta vs Benchmark**: Typically vs `VWCE.EU`
- **Herfindahl Index**: Concentration measure (higher = more concentrated)

### Risk/Return Radar Chart

Six normalized 0..1 scores for the radar visualization:

- **Return-side**: 1Y return, 5Y return, Sharpe ratio
- **Resilience-side**: Lower volatility, higher Sharpe, lower max drawdown

Higher scores = better performance

## Architecture

### Key Classes

#### `PortfolioComposition`

Main facade class that coordinates analytics:

```python
from sentinel.portfolio_composition import PortfolioComposition

pc = PortfolioComposition()
composition = await pc.get_composition_breakdown()
metrics = await pc.get_risk_return_metrics()
radar = await pc.get_radar_chart_data()
```

### Design Patterns

1. **Pure Functions**: Math operations are pure and testable in isolation
2. **Singleton Support**: Can work with injected `Database` instance or use singleton
3. **ISO Country Codes**: Full ISO-3166-1 coverage for graceful degradation

## Data Dependencies

- `portfolio_snapshots` table: Time-series portfolio value history
- `securities` table: Country, industry, currency metadata
- `prices` table: For computing returns (if needed)

## API Endpoints

Exposed via `sentinel/api/routers/portfolio.py`:

- `GET /api/portfolio/composition` - Full composition breakdown
- `GET /api/portfolio/metrics` - Risk/return metrics
- `GET /api/portfolio/radar` - Radar chart data

## Testing

Tests located in `tests/test_portfolio_composition.py` (27K, comprehensive coverage)

Key test scenarios:

- Composition calculation with various portfolio states
- Metric computation edge cases (empty data, single snapshot)
- Radar score normalization bounds
- Continent mapping for all ISO countries

## Usage Examples

### Get Full Portfolio Composition

```python
from sentinel.portfolio_composition import PortfolioComposition

pc = PortfolioComposition()
result = await pc.get_composition_breakdown()

# Result structure:
{
    "by_country": {"US": 45.2, "IE": 23.1, ...},
    "by_continent": {"North America": 50.3, "Europe": 40.1, ...},
    "by_industry": {"Technology": 25.4, "Financials": 18.2, ...},
    "by_currency": {"USD": 60.5, "EUR": 30.2, ...},
    "by_asset_class": {"Stock": 75.3, "ETF": 24.7}
}
```

### Get Risk/Return Metrics

```python
metrics = await pc.get_risk_return_metrics()

# Result structure:
{
    "return_1y": 12.4,
    "return_5y": 8.7,
    "volatility_annualized": 14.2,
    "max_drawdown": -23.5,
    "sharpe_ratio": 0.85,
    "beta": 0.92,
    "herfindahl_index": 0.08
}
```

### Get Radar Chart Data

```python
radar = await pc.get_radar_chart_data()

# Result structure (all values 0..1):
{
    "return_1y": 0.78,
    "return_5y": 0.65,
    "sharpe": 0.82,
    "volatility": 0.71,  # Lower vol = higher score
    "max_drawdown": 0.68,  # Lower DD = higher score
    "concentration": 0.75  # Lower Herfindahl = higher score
}
```

## Implementation Details

### Continent Mapping

Uses full ISO-3166-1 alpha-2 country code mapping (54 African countries, UN-defined Asia including Middle East, etc.). Static dictionary `CONTINENT_BY_COUNTRY` kept inline for simplicity.

### Benchmark Comparison

Default benchmark is `VWCE.EU` (Vanguard FTSE All-World UCITS ETF). Beta calculation uses linear regression of portfolio returns vs benchmark returns.

### Herfindahl Index

Calculated as sum of squared allocation weights:

```
H = Σ(weight_i²)
```

- Perfectly diversified (N equal positions): H = 1/N
- Concentrated (single position): H = 1.0
- Lower is better (more diversified)

## Common Pitfalls

1. **Empty Portfolio**: Returns zeros for all metrics, not errors
2. **Insufficient History**: 5Y metrics require 5+ years of snapshots
3. **Missing Metadata**: Securities without country/industry are excluded from breakdowns
4. **Currency Conversion**: All metrics computed in EUR base currency

## Related Documentation

- [Strategy: Contrarian](./strategy_contrarian.md) - How allocation targets are computed
- [API: Portfolio](../sentinel/api/routers/portfolio.py) - Endpoint implementation
- [Test: Portfolio Composition](../tests/test_portfolio_composition.py) - Test suite
