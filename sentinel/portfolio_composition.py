"""Portfolio composition + risk/return metrics.

Surfaces the data the web sidebar needs to replace the now-defunct Freedom24
PRAAMS analysis with our own equivalents, computed from data we already have:

- **Composition breakdowns** (% of EUR portfolio value): country, continent,
  industry, currency, asset class.
- **Time-series metrics** from `portfolio_snapshots`: 1Y / 5Y total return,
  annualized volatility, max drawdown, Sharpe ratio, beta vs a benchmark
  (default `VWCE.EU`), Herfindahl concentration.
- **Risk/Return radar axes** — six normalized 0..1 scores (higher = better)
  derived from the metrics above. Three return-side, three resilience-side.

All pure functions where possible so the math is testable in isolation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, timezone

# ISO-3166-1 alpha-2 country code -> continent. Full coverage so a new
# ticker in any country degrades gracefully instead of falling into
# "Unknown". Source: ISO 3166-1 + UN geoscheme (Middle East is grouped
# with Asia following the UN convention; readers who want a separate
# bucket can re-map after the fact).
#
# Generated once and kept inline because (a) it's static reference data,
# (b) it changes maybe once a decade when a country renames or splits,
# and (c) pulling in `pycountry-convert` for one lookup violates KISS.
CONTINENT_BY_COUNTRY: dict[str, str] = {
    # --- Africa (54 sovereign + dependent territories) ---
    "DZ": "Africa",
    "AO": "Africa",
    "BJ": "Africa",
    "BW": "Africa",
    "BF": "Africa",
    "BI": "Africa",
    "CM": "Africa",
    "CV": "Africa",
    "CF": "Africa",
    "TD": "Africa",
    "KM": "Africa",
    "CG": "Africa",
    "CD": "Africa",
    "CI": "Africa",
    "DJ": "Africa",
    "EG": "Africa",
    "GQ": "Africa",
    "ER": "Africa",
    "SZ": "Africa",
    "ET": "Africa",
    "GA": "Africa",
    "GM": "Africa",
    "GH": "Africa",
    "GN": "Africa",
    "GW": "Africa",
    "KE": "Africa",
    "LS": "Africa",
    "LR": "Africa",
    "LY": "Africa",
    "MG": "Africa",
    "MW": "Africa",
    "ML": "Africa",
    "MR": "Africa",
    "MU": "Africa",
    "YT": "Africa",
    "MA": "Africa",
    "MZ": "Africa",
    "NA": "Africa",
    "NE": "Africa",
    "NG": "Africa",
    "RE": "Africa",
    "RW": "Africa",
    "SH": "Africa",
    "ST": "Africa",
    "SN": "Africa",
    "SC": "Africa",
    "SL": "Africa",
    "SO": "Africa",
    "ZA": "Africa",
    "SS": "Africa",
    "SD": "Africa",
    "TZ": "Africa",
    "TG": "Africa",
    "TN": "Africa",
    "UG": "Africa",
    "EH": "Africa",
    "ZM": "Africa",
    "ZW": "Africa",
    # --- Antarctica ---
    "AQ": "Antarctica",
    "BV": "Antarctica",
    "TF": "Antarctica",
    "HM": "Antarctica",
    "GS": "Antarctica",
    # --- Asia (UN definition: includes Middle East & Central Asia) ---
    "AF": "Asia",
    "AM": "Asia",
    "AZ": "Asia",
    "BH": "Asia",
    "BD": "Asia",
    "BT": "Asia",
    "BN": "Asia",
    "KH": "Asia",
    "CN": "Asia",
    "CY": "Asia",
    "GE": "Asia",
    "HK": "Asia",
    "IN": "Asia",
    "ID": "Asia",
    "IR": "Asia",
    "IQ": "Asia",
    "IL": "Asia",
    "JP": "Asia",
    "JO": "Asia",
    "KZ": "Asia",
    "KP": "Asia",
    "KR": "Asia",
    "KW": "Asia",
    "KG": "Asia",
    "LA": "Asia",
    "LB": "Asia",
    "MO": "Asia",
    "MY": "Asia",
    "MV": "Asia",
    "MN": "Asia",
    "MM": "Asia",
    "NP": "Asia",
    "OM": "Asia",
    "PK": "Asia",
    "PS": "Asia",
    "PH": "Asia",
    "QA": "Asia",
    "SA": "Asia",
    "SG": "Asia",
    "LK": "Asia",
    "SY": "Asia",
    "TW": "Asia",
    "TJ": "Asia",
    "TH": "Asia",
    "TL": "Asia",
    "TR": "Asia",
    "TM": "Asia",
    "AE": "Asia",
    "UZ": "Asia",
    "VN": "Asia",
    "YE": "Asia",
    "IO": "Asia",
    # --- Europe ---
    "AX": "Europe",
    "AL": "Europe",
    "AD": "Europe",
    "AT": "Europe",
    "BY": "Europe",
    "BE": "Europe",
    "BA": "Europe",
    "BG": "Europe",
    "HR": "Europe",
    "CZ": "Europe",
    "DK": "Europe",
    "EE": "Europe",
    "FO": "Europe",
    "FI": "Europe",
    "FR": "Europe",
    "DE": "Europe",
    "GI": "Europe",
    "GR": "Europe",
    "GG": "Europe",
    "VA": "Europe",
    "HU": "Europe",
    "IS": "Europe",
    "IE": "Europe",
    "IM": "Europe",
    "IT": "Europe",
    "JE": "Europe",
    "XK": "Europe",
    "LV": "Europe",
    "LI": "Europe",
    "LT": "Europe",
    "LU": "Europe",
    "MT": "Europe",
    "MD": "Europe",
    "MC": "Europe",
    "ME": "Europe",
    "NL": "Europe",
    "MK": "Europe",
    "NO": "Europe",
    "PL": "Europe",
    "PT": "Europe",
    "RO": "Europe",
    "RU": "Europe",
    "SM": "Europe",
    "RS": "Europe",
    "SK": "Europe",
    "SI": "Europe",
    "ES": "Europe",
    "SJ": "Europe",
    "SE": "Europe",
    "CH": "Europe",
    "UA": "Europe",
    "GB": "Europe",
    # --- North America (incl. Central America & Caribbean) ---
    "AI": "North America",
    "AG": "North America",
    "AW": "North America",
    "BS": "North America",
    "BB": "North America",
    "BZ": "North America",
    "BM": "North America",
    "BQ": "North America",
    "CA": "North America",
    "KY": "North America",
    "CR": "North America",
    "CU": "North America",
    "CW": "North America",
    "DM": "North America",
    "DO": "North America",
    "SV": "North America",
    "GL": "North America",
    "GD": "North America",
    "GP": "North America",
    "GT": "North America",
    "HT": "North America",
    "HN": "North America",
    "JM": "North America",
    "MQ": "North America",
    "MX": "North America",
    "MS": "North America",
    "NI": "North America",
    "PA": "North America",
    "PR": "North America",
    "BL": "North America",
    "KN": "North America",
    "LC": "North America",
    "MF": "North America",
    "PM": "North America",
    "VC": "North America",
    "SX": "North America",
    "TT": "North America",
    "TC": "North America",
    "US": "North America",
    "VG": "North America",
    "VI": "North America",
    # --- Oceania ---
    "AS": "Oceania",
    "AU": "Oceania",
    "CX": "Oceania",
    "CC": "Oceania",
    "CK": "Oceania",
    "FJ": "Oceania",
    "PF": "Oceania",
    "GU": "Oceania",
    "KI": "Oceania",
    "MH": "Oceania",
    "FM": "Oceania",
    "NR": "Oceania",
    "NC": "Oceania",
    "NZ": "Oceania",
    "NU": "Oceania",
    "NF": "Oceania",
    "MP": "Oceania",
    "PW": "Oceania",
    "PG": "Oceania",
    "PN": "Oceania",
    "WS": "Oceania",
    "SB": "Oceania",
    "TK": "Oceania",
    "TO": "Oceania",
    "TV": "Oceania",
    "UM": "Oceania",
    "VU": "Oceania",
    "WF": "Oceania",
    # --- South America ---
    "AR": "South America",
    "BO": "South America",
    "BR": "South America",
    "CL": "South America",
    "CO": "South America",
    "EC": "South America",
    "FK": "South America",
    "GF": "South America",
    "GY": "South America",
    "PY": "South America",
    "PE": "South America",
    "SR": "South America",
    "UY": "South America",
    "VE": "South America",
}

# instr_kind_c -> human asset class. Mirrors Tradernet's `instr_kind` values
# (see docs/tradernet/miscellaneous/instruments.md). Anything else -> "Other".
ASSET_CLASS_BY_KIND_C: dict[int, str] = {
    1: "Stock",
    2: "Preferred Stock",
    7: "ETF / Fund",
    10: "Depositary Receipt",
    14: "Crypto Share",
}

# Trading days per year — standard convention for annualizing daily metrics.
TRADING_DAYS_PER_YEAR = 252

# Default risk-free rate (annualized, decimal). Stored as a setting so the
# user can override; this is just the fall-back used when the setting is
# missing or unparseable.
DEFAULT_RISK_FREE_RATE = 0.02

# Minimum daily-return samples required to compute beta against a benchmark.
# Below this the regression is too noisy to be useful — we skip the benchmark.
MIN_SAMPLES_FOR_BETA = 30


@dataclass(frozen=True)
class Bucket:
    """One slice of a composition breakdown — `pct` is 0..1."""

    name: str
    pct: float


def continent_for(country: str | None) -> str:
    """Map an ISO-2 country code to its continent. Anything non-ISO-2 or
    unmapped falls into "Unknown" — that covers our preserved multi-CSV values
    (e.g. "US, Asia") as well as legitimately unclassified securities.
    """
    if not country or len(country) != 2:
        return "Unknown"
    return CONTINENT_BY_COUNTRY.get(country.upper(), "Unknown")


def asset_class_for(instr_kind_c: int | None) -> str:
    """Map Tradernet's `instr_kind_c` to a human asset-class label."""
    if instr_kind_c is None:
        return "Other"
    return ASSET_CLASS_BY_KIND_C.get(int(instr_kind_c), "Other")


def _bucket_pcts(weighted: dict[str, float]) -> list[Bucket]:
    """Convert a {name: weight} dict to a sorted list of Bucket(name, pct)."""
    total = sum(weighted.values())
    if total <= 0:
        return []
    items = [Bucket(name=k, pct=v / total) for k, v in weighted.items()]
    # Largest slice first, with "Unknown" pushed to the end regardless of size
    # so the meaningful buckets dominate the eye.
    items.sort(key=lambda b: (b.name == "Unknown", -b.pct, b.name))
    return items


def compose(positions_eur: dict[str, float], securities_map: dict[str, dict]) -> dict[str, list[Bucket]]:
    """Build all five composition breakdowns from a {symbol: eur_value} mapping.

    `securities_map` is `{symbol: securities_row}` and is used to look up the
    metadata fields (geography, industry, currency, instr_kind_c) for each
    held position. Missing or blank fields are bucketed as "Unknown".

    Returns a dict with keys ``by_country``, ``by_continent``, ``by_industry``,
    ``by_currency``, ``by_asset_class``, each a list of ``Bucket``.
    """
    by_country: dict[str, float] = {}
    by_continent: dict[str, float] = {}
    by_industry: dict[str, float] = {}
    by_currency: dict[str, float] = {}
    by_kind: dict[str, float] = {}

    for symbol, value in positions_eur.items():
        if value <= 0:
            continue
        sec = securities_map.get(symbol) or {}

        country = (sec.get("geography") or "").strip() or "Unknown"
        by_country[country] = by_country.get(country, 0.0) + value
        cont = continent_for(country)
        by_continent[cont] = by_continent.get(cont, 0.0) + value

        industry = (sec.get("industry") or "").strip() or "Unknown"
        by_industry[industry] = by_industry.get(industry, 0.0) + value

        ccy = (sec.get("currency") or "").strip() or "Unknown"
        by_currency[ccy] = by_currency.get(ccy, 0.0) + value

        kind = asset_class_for(sec.get("instr_kind_c"))
        by_kind[kind] = by_kind.get(kind, 0.0) + value

    return {
        "by_country": _bucket_pcts(by_country),
        "by_continent": _bucket_pcts(by_continent),
        "by_industry": _bucket_pcts(by_industry),
        "by_currency": _bucket_pcts(by_currency),
        "by_asset_class": _bucket_pcts(by_kind),
    }


def rollup_country_industry(
    allocation_by_symbol: dict[str, float],
    securities_map: dict[str, dict],
) -> dict[str, list[Bucket]]:
    """Roll up a {symbol: weight} mapping into country and industry buckets.

    Used for both the planner's ideal portfolio (% per symbol) and the
    post-plan projection (EUR value per symbol). The function is unit-agnostic
    — buckets are normalized to fractions in `_bucket_pcts` either way.
    """
    by_country: dict[str, float] = {}
    by_industry: dict[str, float] = {}
    for symbol, weight in allocation_by_symbol.items():
        if weight <= 0:
            continue
        sec = securities_map.get(symbol) or {}
        country = (sec.get("geography") or "").strip() or "Unknown"
        industry = (sec.get("industry") or "").strip() or "Unknown"
        by_country[country] = by_country.get(country, 0.0) + weight
        by_industry[industry] = by_industry.get(industry, 0.0) + weight
    return {
        "by_country": _bucket_pcts(by_country),
        "by_industry": _bucket_pcts(by_industry),
    }


# ---------------------------------------------------------------------------
# Time-series metrics
# ---------------------------------------------------------------------------


def _ts_to_iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def daily_value_series(snapshots: list[dict]) -> list[tuple[str, float]]:
    """Reduce raw snapshots to a [(iso_date, total_value_eur), ...] series.

    Each snapshot row is ``{"date": <unix_ts>, "data": {positions, cash_eur}}``
    matching `Database.get_portfolio_snapshots` output. Snapshots without
    valid positions data become value=0; that's caller's problem to filter.
    """
    out: list[tuple[str, float]] = []
    for snap in snapshots:
        ts = snap.get("date")
        data = snap.get("data") or {}
        positions = data.get("positions") or {}
        cash = float(data.get("cash_eur") or 0.0)
        pv = sum(float(p.get("value_eur", 0.0)) for p in positions.values())
        if ts is None:
            continue
        out.append((_ts_to_iso(int(ts)), pv + cash))
    return out


def build_daily_pnl(snapshots: list[dict], deposits_by_date: dict[str, float]) -> list[dict]:
    """Build the daily P&L series the `/api/portfolio/pnl-history` endpoint
    publishes — `[{date, total_value_eur, net_deposits_eur, pnl_eur, pnl_pct}, ...]`.

    `deposits_by_date` is the cumulative EUR-converted deposit total as of
    each ISO date that had a cash flow. We bisect to find the running total
    on every snapshot date so deposits stay correctly attributed even when
    there's no cash-flow event on the exact snapshot day.
    """
    import bisect

    nd_dates = sorted(deposits_by_date.keys())
    nd_values = [deposits_by_date[d] for d in nd_dates]

    def _net_deposits_as_of(iso_date: str) -> float:
        idx = bisect.bisect_right(nd_dates, iso_date) - 1
        return nd_values[idx] if idx >= 0 else 0.0

    daily: list[dict] = []
    for snap in snapshots:
        ts = snap.get("date")
        data = snap.get("data") or {}
        if ts is None:
            continue
        iso_date = _ts_to_iso(int(ts))
        positions = data.get("positions") or {}
        cash_eur = float(data.get("cash_eur") or 0.0)
        positions_value = sum(float(p.get("value_eur", 0)) for p in positions.values())
        total_value = positions_value + cash_eur
        net_deposits = _net_deposits_as_of(iso_date)
        pnl_eur = total_value - net_deposits
        pnl_pct = (pnl_eur / net_deposits * 100) if net_deposits > 0 else 0.0
        daily.append(
            {
                "date": iso_date,
                "total_value_eur": round(total_value, 2),
                "net_deposits_eur": round(net_deposits, 2),
                "pnl_eur": round(pnl_eur, 2),
                "pnl_pct": round(pnl_pct, 2),
            }
        )
    return daily


# A single-day HPR above this magnitude is treated as a snapshot
# reconstruction artifact rather than a real market move. We've observed days
# where a card deposit recorded on day N first appears in the snapshot on
# day N+2 (e.g. across a weekend), producing apparent +20% / -20% daily
# returns that have no corresponding price movement.
#
# This filter is only applied where each daily value matters individually
# (volatility, Sharpe, beta). It is NOT applied to TWR, where consecutive
# +X / -X artifacts cancel multiplicatively.
#
# TODO: replace snapshot-derived HPRs with positions × daily-price-change
# math so this filter becomes unnecessary. The data exists (trades + prices
# + FX rates); the work is one focused refactor of the metrics pipeline.
HPR_RECONSTRUCTION_OUTLIER = 0.15


def daily_hprs(daily: list[dict], filter_outliers: bool = False) -> list[float]:
    """Holding-period returns derived from a daily P&L series.

    For each pair (t-1, t):
        hpr_t = (value_t - value_(t-1) - net_deposit_change_t) / value_(t-1)

    Skips days where the prior value is non-positive (the portfolio was
    empty so there's no return to speak of). This is the same per-day
    return formula `/api/portfolio/pnl-history` uses for its rolling TWR.

    `filter_outliers=True` drops HPRs above `HPR_RECONSTRUCTION_OUTLIER`
    in magnitude — see the constant's doc for why this is needed for vol
    and other per-day-sensitive metrics.
    """
    out: list[float] = []
    for i in range(1, len(daily)):
        prev_v = daily[i - 1]["total_value_eur"]
        if not prev_v or prev_v <= 0:
            continue
        cash_flow = daily[i]["net_deposits_eur"] - daily[i - 1]["net_deposits_eur"]
        hpr = (daily[i]["total_value_eur"] - prev_v - cash_flow) / prev_v
        if filter_outliers and abs(hpr) > HPR_RECONSTRUCTION_OUTLIER:
            continue
        out.append(hpr)
    return out


def rolling_twr(daily: list[dict], window_days: int) -> float | None:
    """Time-weighted return over the most recent `window_days` of the series.

    Compounds the deposit-adjusted daily HPRs the same way the pnl-history
    endpoint does. Returns None when the window has fewer than 2 data points
    or any prior value in the window is non-positive (the chain is undefined).
    """
    if len(daily) < 2:
        return None
    window = daily[-(window_days + 1) :] if len(daily) > window_days else daily
    cumulative = 1.0
    for i in range(1, len(window)):
        prev_v = window[i - 1]["total_value_eur"]
        if not prev_v or prev_v <= 0:
            return None
        cash_flow = window[i]["net_deposits_eur"] - window[i - 1]["net_deposits_eur"]
        hpr = (window[i]["total_value_eur"] - prev_v - cash_flow) / prev_v
        cumulative *= 1.0 + hpr
    return cumulative - 1.0


def inception_cagr(daily: list[dict]) -> tuple[float, float]:
    """Compound annual growth rate from the first snapshot to the last.

    Returns `(cagr, years)` where `cagr` is a decimal fraction (0.11 = 11%)
    and `years` is the elapsed window in years. Falls back to (0, 0) when
    the data is too thin or deposits/final value make the formula undefined.
    """
    if len(daily) < 2:
        return 0.0, 0.0
    from datetime import date as date_type

    start = date_type.fromisoformat(daily[0]["date"])
    end = date_type.fromisoformat(daily[-1]["date"])
    years = (end - start).days / 365.25
    final_value = daily[-1]["total_value_eur"]
    total_deposits = daily[-1]["net_deposits_eur"]
    if years <= 0 or total_deposits <= 0 or final_value <= 0:
        return 0.0, years
    cagr = (final_value / total_deposits) ** (1.0 / years) - 1.0
    return cagr, years


def annualized_volatility(returns: list[float]) -> float:
    """Standard-deviation of daily returns × sqrt(252)."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    return math.sqrt(var) * math.sqrt(TRADING_DAYS_PER_YEAR)


def max_drawdown(values: list[float]) -> float:
    """Worst peak-to-trough drop in the value series, expressed as a positive
    fraction (e.g. 0.27 for a -27% drawdown). Returns 0 if input is empty.
    """
    if not values:
        return 0.0
    peak = values[0]
    worst = 0.0
    for v in values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > worst:
                worst = dd
    return worst


def sharpe_ratio(returns: list[float], risk_free_rate: float) -> float:
    """Annualized Sharpe: (mean - rf/252) / stdev × sqrt(252)."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
    return (mean - daily_rf) / std * math.sqrt(TRADING_DAYS_PER_YEAR)


def beta(portfolio_returns: list[float], benchmark_returns: list[float]) -> float:
    """OLS beta: cov(p, b) / var(b). Both series must be the same length."""
    n = min(len(portfolio_returns), len(benchmark_returns))
    if n < 2:
        return 0.0
    p = portfolio_returns[-n:]
    b = benchmark_returns[-n:]
    p_mean = sum(p) / n
    b_mean = sum(b) / n
    cov = sum((p[i] - p_mean) * (b[i] - b_mean) for i in range(n)) / (n - 1)
    var_b = sum((b[i] - b_mean) ** 2 for i in range(n)) / (n - 1)
    if var_b == 0:
        return 0.0
    return cov / var_b


def hhi_concentration(positions_eur: dict[str, float]) -> float:
    """Herfindahl-Hirschman Index of position weights. 0 = perfectly diversified
    across infinite positions, 1 = single position. Cash is excluded.
    """
    total = sum(v for v in positions_eur.values() if v > 0)
    if total <= 0:
        return 0.0
    return sum((v / total) ** 2 for v in positions_eur.values() if v > 0)


# ---------------------------------------------------------------------------
# Radar normalization
# ---------------------------------------------------------------------------


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def radar_axes(metrics: dict[str, float]) -> dict[str, float]:
    """Convert raw portfolio metrics to 0..1 radar scores (higher = better).

    Return-side axes (higher = good directly):
        return_1y    -- 1Y total return, mapped from [-50%, +50%] -> [0, 1]
        sharpe       -- Sharpe ratio, mapped from [-1, +3] -> [0, 1]
        alpha        -- (return_1y - benchmark_return_1y), [-30%, +30%] -> [0, 1]

    Resilience-side axes (low risk -> high score):
        low_volatility       -- annual vol, mapped from [40%, 0%] -> [0, 1]
        low_drawdown         -- max DD, mapped from [50%, 0%] -> [0, 1]
        low_concentration    -- HHI, mapped from [0.5, 0.05] -> [0, 1]
    """
    ret_1y = metrics.get("return_1y", 0.0)
    sharpe = metrics.get("sharpe", 0.0)
    bench_1y = metrics.get("benchmark_return_1y", 0.0)
    vol = metrics.get("volatility", 0.0)
    dd = metrics.get("max_drawdown", 0.0)
    hhi = metrics.get("hhi", 0.0)

    return {
        "return_1y": _clamp((ret_1y + 0.5) / 1.0),
        "sharpe": _clamp((sharpe + 1.0) / 4.0),
        "alpha": _clamp(((ret_1y - bench_1y) + 0.3) / 0.6),
        "low_volatility": _clamp((0.4 - vol) / 0.4),
        "low_drawdown": _clamp((0.5 - dd) / 0.5),
        "low_concentration": _clamp((0.5 - hhi) / 0.45),
    }


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def _correlation(a: list[float], b: list[float]) -> float:
    """Pearson correlation of two equal-length series. 0 if degenerate."""
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a = a[-n:]
    b = b[-n:]
    a_mean = sum(a) / n
    b_mean = sum(b) / n
    num = sum((a[i] - a_mean) * (b[i] - b_mean) for i in range(n))
    var_a = sum((a[i] - a_mean) ** 2 for i in range(n))
    var_b = sum((b[i] - b_mean) ** 2 for i in range(n))
    if var_a == 0 or var_b == 0:
        return 0.0
    return num / math.sqrt(var_a * var_b)


def _benchmark_stats(
    portfolio_returns: list[float],
    portfolio_series: list[tuple[str, float]],
    benchmark_prices: list[dict],
) -> dict | None:
    """Align a benchmark's daily closes to the portfolio's date axis and
    compute beta, correlation, and 1y return. Returns None if there aren't
    enough overlapping samples for a meaningful regression.

    `benchmark_prices` is the rows from `db.get_benchmark_prices` (newest
    first). The portfolio series is chronological (oldest first).
    """
    if not benchmark_prices or len(portfolio_series) < 2:
        return None

    bench_by_date = {p["date"]: float(p.get("close") or 0.0) for p in benchmark_prices}

    # Walk the portfolio's date axis; collect (port_return_t, bench_return_t)
    # pairs only for days where the benchmark also has a price. This is the
    # right move for thinly-traded local indices that don't quote every day.
    pairs: list[tuple[float, float]] = []
    last_bench_value: float | None = None
    for i in range(1, len(portfolio_series)):
        date = portfolio_series[i][0]
        bench_val = bench_by_date.get(date)
        if bench_val is None or bench_val <= 0:
            last_bench_value = None
            continue
        if last_bench_value is None or last_bench_value <= 0:
            last_bench_value = bench_val
            continue
        bench_ret = bench_val / last_bench_value - 1.0
        last_bench_value = bench_val
        if i - 1 < len(portfolio_returns):
            pairs.append((portfolio_returns[i - 1], bench_ret))

    if len(pairs) < MIN_SAMPLES_FOR_BETA:
        return None

    p_series = [p for p, _ in pairs]
    b_series = [b for _, b in pairs]

    sorted_bench = sorted(benchmark_prices, key=lambda p: p["date"])
    bench_chrono = [float(p.get("close") or 0.0) for p in sorted_bench]
    bench_return_1y = 0.0
    if len(bench_chrono) > TRADING_DAYS_PER_YEAR:
        start = bench_chrono[-1 - TRADING_DAYS_PER_YEAR]
        if start > 0:
            bench_return_1y = bench_chrono[-1] / start - 1.0

    return {
        "beta": beta(p_series, b_series),
        "correlation": _correlation(p_series, b_series),
        "return_1y": bench_return_1y,
        "samples": len(pairs),
    }


async def _benchmark_table(
    db,
    portfolio_returns: list[float],
    portfolio_series: list[tuple[str, float]],
) -> list[dict]:
    """Compute beta + correlation + 1y return for every benchmark in the
    `benchmarks` table that has enough overlapping price history to matter.
    Sorted descending by absolute correlation so the most relevant ones lead.
    """
    rows: list[dict] = []
    for bench in await db.get_benchmarks():
        symbol = bench["symbol"]
        prices = await db.get_benchmark_prices(symbol, days=365 * 5)
        stats = _benchmark_stats(portfolio_returns, portfolio_series, prices)
        if stats is None:
            continue
        rows.append(
            {
                "symbol": symbol,
                "name": bench.get("name") or symbol,
                "mkt_short_code": bench.get("mkt_short_code"),
                "beta": round(stats["beta"], 4),
                "correlation": round(stats["correlation"], 4),
                "return_1y": round(stats["return_1y"], 6),
                "samples": stats["samples"],
            }
        )
    rows.sort(key=lambda r: abs(r["correlation"]), reverse=True)
    return rows


async def build_composition(db, currency, settings) -> dict:
    """Assemble the full composition + metrics payload for the API endpoint.

    Pulls everything: current positions (for live composition), portfolio
    snapshots (for time-series metrics), benchmark prices for every entry
    in the `benchmarks` table (for beta + alpha vs many indices), and cash
    flow history (for deposit-adjusted returns).
    """
    from sentinel.utils.positions import PositionCalculator

    positions = await db.get_all_positions()
    securities = await db.get_all_securities(active_only=False)
    securities_map = {s["symbol"]: s for s in securities}

    pos_calc = PositionCalculator(currency_converter=currency)
    positions_eur: dict[str, float] = {}
    for pos in positions:
        qty = pos.get("quantity", 0)
        price = pos.get("current_price", 0)
        if not qty or not price:
            continue
        v = await pos_calc.calculate_value_eur(qty, price, pos.get("currency", "EUR"))
        positions_eur[pos["symbol"]] = v

    buckets = compose(positions_eur, securities_map)

    # Pull the same daily P&L series the `/api/portfolio/pnl-history` endpoint
    # builds — single source of truth for portfolio time-series math.
    snapshots = await db.get_portfolio_snapshots(days=365 * 5)
    cash_flows = await db.get_cash_flows()
    cf_deposits = [cf for cf in cash_flows if cf.get("type_id") in ("card", "card_payout")]
    cf_deposits.sort(key=lambda cf: cf["date"])
    deposits_by_date: dict[str, float] = {}
    running = 0.0
    for cf in cf_deposits:
        amount_eur = await currency.to_eur_for_date(cf["amount"], cf["currency"], cf["date"])
        running += amount_eur
        deposits_by_date[cf["date"]] = running

    daily = build_daily_pnl(snapshots, deposits_by_date)
    series = [(d["date"], d["total_value_eur"]) for d in daily]
    # Daily HPRs across the last year only — earlier history is dominated by
    # the bootstrap period when the portfolio was tiny and deposit-timing
    # noise overwhelms real market movement. Volatility/Sharpe/beta need
    # clean recent data to be meaningful.
    daily_last_year = daily[-(TRADING_DAYS_PER_YEAR + 1) :] if len(daily) > TRADING_DAYS_PER_YEAR else daily
    # Outlier-filtered HPRs for stddev-based metrics (volatility, Sharpe,
    # beta). TWR is computed separately and is robust to these artifacts.
    returns = daily_hprs(daily_last_year, filter_outliers=True)
    risk_free = float(await settings.get("risk_free_rate", DEFAULT_RISK_FREE_RATE) or DEFAULT_RISK_FREE_RATE)

    benchmarks_table = await _benchmark_table(db, returns, series)

    # The radar's alpha axis needs ONE reference benchmark. Use the index
    # with the highest correlation to this portfolio — that's the one whose
    # outperformance is most meaningful as "alpha". If there are no
    # benchmarks at all (fresh deploy, sync hasn't run), gracefully degrade
    # to 0% benchmark return -> alpha equals portfolio return.
    primary = benchmarks_table[0] if benchmarks_table else None
    primary_return_1y = primary["return_1y"] if primary else 0.0
    primary_symbol = primary["symbol"] if primary else None

    cagr_value, cagr_years = inception_cagr(daily)
    return_1y_value = rolling_twr(daily, 365)

    metrics = {
        "return_1y": return_1y_value if return_1y_value is not None else 0.0,
        "return_since_inception_cagr": cagr_value,
        "inception_years": round(cagr_years, 2),
        "volatility": annualized_volatility(returns),
        "max_drawdown": max_drawdown([d["total_value_eur"] for d in daily_last_year]),
        "sharpe": sharpe_ratio(returns, risk_free),
        "hhi": hhi_concentration(positions_eur),
        "benchmark_return_1y": primary_return_1y,
        "primary_benchmark_symbol": primary_symbol,
        "risk_free_rate": risk_free,
    }
    metrics["alpha_1y"] = metrics["return_1y"] - metrics["benchmark_return_1y"]

    def _b(buckets_list: list[Bucket]) -> list[dict]:
        return [{"name": b.name, "pct": round(b.pct, 6)} for b in buckets_list]

    # Ideal composition — what the planner thinks the portfolio should hold
    # per security; rolled up by country/industry from the same metadata
    # columns the current composition uses. If the planner is unavailable
    # (fresh deploy, settings missing, ...) we degrade to empty lists rather
    # than crash the whole endpoint.
    ideal_buckets: dict[str, list[Bucket]] = {"by_country": [], "by_industry": []}
    post_plan_buckets: dict[str, list[Bucket]] = {"by_country": [], "by_industry": []}
    try:
        from sentinel.planner import Planner

        planner = Planner()
        ideal_by_symbol = await planner.calculate_ideal_portfolio()
        if ideal_by_symbol:
            ideal_buckets = rollup_country_industry(ideal_by_symbol, securities_map)

        # Post-plan: start from current EUR positions, apply each recommendation's
        # `target_value_eur` (the EUR exposure after the trade), then roll up.
        # Securities with no rec stay at their current value — the planner is
        # signalling "already at target."
        post_plan_value = dict(positions_eur)
        recs = await planner.get_recommendations()
        for rec in recs or []:
            symbol = getattr(rec, "symbol", None)
            target = getattr(rec, "target_value_eur", None)
            if symbol and target is not None and target >= 0:
                post_plan_value[symbol] = float(target)
        if post_plan_value:
            post_plan_buckets = rollup_country_industry(post_plan_value, securities_map)
    except Exception as e:
        # Planner failures (missing prices, broker offline, ...) should never
        # nuke the composition endpoint. Log and keep going with empty ideal
        # / post-plan; the frontend just hides those polylines.
        import logging

        logging.getLogger(__name__).warning("Planner unavailable for composition: %s", e)

    return {
        "as_of": date_type.today().isoformat(),
        "total_value_eur": round(sum(positions_eur.values()), 2),
        "composition": {
            "by_country": _b(buckets["by_country"]),
            "by_continent": _b(buckets["by_continent"]),
            "by_industry": _b(buckets["by_industry"]),
            "by_currency": _b(buckets["by_currency"]),
            "by_asset_class": _b(buckets["by_asset_class"]),
        },
        "composition_ideal": {
            "by_country": _b(ideal_buckets["by_country"]),
            "by_industry": _b(ideal_buckets["by_industry"]),
        },
        "composition_post_plan": {
            "by_country": _b(post_plan_buckets["by_country"]),
            "by_industry": _b(post_plan_buckets["by_industry"]),
        },
        "metrics": {k: round(v, 6) if isinstance(v, float) else v for k, v in metrics.items()},
        "benchmarks": benchmarks_table,
        "radar": radar_axes(metrics),
    }
