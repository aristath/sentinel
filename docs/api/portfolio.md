# Portfolio

Base path: `/api/portfolio`

---

## `GET /api/portfolio`

Returns the full current portfolio state: positions, cash balances, and aggregate values.

**Response**
```json
{
  "positions": [
    {
      "symbol": "AAPL.US",
      "name": "Apple Inc.",
      "quantity": 5.0,
      "avg_cost": 160.00,
      "current_price": 270.94,
      "currency": "USD",
      "updated_at": "now",
      "value_local": 1354.70,
      "value_eur": 1159.01,
      "invested_eur": 684.74,
      "profit_pct": 69.34
    }
  ],
  "total_value": 23917.92,
  "total_value_eur": 23917.92,
  "portfolio_return_pct": 12.5,
  "cash": {
    "EUR": 1200.00,
    "USD": 350.00
  },
  "total_cash_eur": 1499.43
}
```

**Position fields**

| Field | Description |
|---|---|
| `value_local` | Position value in the security's native currency |
| `value_eur` | Position value converted to EUR |
| `invested_eur` | Cost basis of the position in EUR (`avg_cost × quantity` converted) |
| `profit_pct` | Unrealised P&L as a percentage of invested cost |
| `updated_at` | Timestamp of last quote update (`"now"` when synced live) |

**Top-level fields**

| Field | Description |
|---|---|
| `total_value` | Total portfolio value in base currency |
| `total_value_eur` | Total portfolio value in EUR |
| `portfolio_return_pct` | Overall return percentage from inception |
| `cash` | Cash balances per currency |
| `total_cash_eur` | Sum of all cash balances converted to EUR |

---

## `POST /api/portfolio/sync`

Triggers a live sync of portfolio positions from the broker. Equivalent to running the `sync:portfolio` job manually.

**Response**
```json
{ "status": "ok" }
```

---

## `GET /api/portfolio/cagr`

Returns a lightweight CAGR from inception for ambient display. Calculated from net card deposits to current portfolio value.

**Response**
```json
{
  "cagr": 20.4,
  "years": 1.97,
  "target": 11.0
}
```

- `cagr` — Compound annual growth rate in percent
- `years` — Years since first portfolio snapshot
- `target` — Hardcoded target CAGR (11%)

---

## `GET /api/portfolio/pnl-history`

Returns daily P&L history for the past 365 days with 365-day rolling time-weighted return (TWR).

**Response**
```json
{
  "snapshots": [
    {
      "date": "2025-04-27",
      "total_value_eur": 44200.00,
      "net_deposits_eur": 40000.00,
      "pnl_eur": 4200.00,
      "pnl_pct": 10.5,
      "actual_ann_return": 9.8
    }
  ],
  "summary": {
    "start_value": 38000.00,
    "end_value": 44200.00,
    "start_net_deposits": 36000.00,
    "end_net_deposits": 40000.00,
    "pnl_absolute": 4200.00,
    "pnl_percent": 10.5,
    "target_ann_return": 11.0
  }
}
```

- `actual_ann_return` — 365-day rolling TWR annualised (null if insufficient history)

---

## `GET /api/portfolio/structure`

Freedom24 PRAAMS analysis (rating, risk/return radar, sector/region/currency breakdowns, replacement recommendations) proxied from `freedom24.com`. Cached in memory for 5 minutes; pass `?force=true` to bypass.

Requires `freedom24_login` and `freedom24_password` settings. Returns `503` when either is missing or the upstream call fails — this is an external scrape, not a stable contract.

**Status note**: as of 2026-05, Freedom24's PRAAMS surface has been intermittently empty (missing `portfolioAnalysis` key) for our credentials. The replacement is `/api/portfolio/composition`, computed locally.

---

## `GET /api/portfolio/composition`

Locally computed composition + risk/return metrics, designed to replace the now-unreliable `/structure` endpoint. Everything is derived from data we already have: positions, securities table, portfolio snapshots, benchmark indices, cash flow history.

**Response** (truncated)
```json
{
  "as_of": "2026-05-22",
  "total_value_eur": 30522.47,
  "composition": {
    "by_country":  [{"name": "CN", "pct": 0.634}, ...],
    "by_continent": [{"name": "Asia", "pct": 0.687}, ...],
    "by_industry": [{"name": "Machinery, Tools, Heavy Vehicles, Trains & Ships", "pct": 0.560}, ...],
    "by_currency": [{"name": "EUR", "pct": 0.45}, ...],
    "by_asset_class": [{"name": "Stock", "pct": 0.947}, {"name": "Depositary Receipt", "pct": 0.053}]
  },
  "composition_ideal":     { "by_country": [...], "by_industry": [...] },
  "composition_post_plan": { "by_country": [...], "by_industry": [...] },
  "metrics": {
    "return_1y": 0.241,
    "return_since_inception_cagr": 0.182,
    "inception_years": 2.04,
    "volatility": 0.39,
    "max_drawdown": 0.296,
    "sharpe": -0.066,
    "hhi": 0.341,
    "alpha_1y": 0.241,
    "primary_benchmark_symbol": "SP500.IDX",
    "benchmark_return_1y": 0.0,
    "risk_free_rate": 0.02
  },
  "benchmarks": [
    {"symbol": "SP500.IDX", "name": "Index S&P 500", "beta": 0.84, "correlation": 0.72, "return_1y": 0.12, "samples": 245},
    ...
  ],
  "radar": {
    "return_1y": 0.74,
    "sharpe": 0.23,
    "alpha": 0.90,
    "low_volatility": 0.03,
    "low_drawdown": 0.41,
    "low_concentration": 0.35
  }
}
```

- `composition.*` — current allocation (% of EUR portfolio value), per breakdown
- `composition_ideal.*` — planner's ideal weights rolled up by country/industry
- `composition_post_plan.*` — what the breakdowns would look like after executing all pending recommendations
- `metrics.return_1y` — 365-day rolling TWR (decimal fraction)
- `metrics.return_since_inception_cagr` — annualised growth from the first snapshot, EUR-deposit-normalised
- `metrics.volatility` — annualised standard deviation of daily HPRs (outlier-filtered for snapshot-reconstruction artefacts)
- `metrics.primary_benchmark_symbol` — auto-picked benchmark (highest correlation with this portfolio's daily returns) used for the radar's `alpha` axis
- `benchmarks` — beta + correlation against every benchmark in the `benchmarks` table with ≥30 days of overlap, sorted by absolute correlation
- `radar` — six 0..1 normalised axes for the Risk/Return visualization
