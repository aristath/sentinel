"""Portfolio API routes."""

import bisect
import logging
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.freedom24_web import Freedom24WebClient
from sentinel.services.portfolio import PortfolioService
from sentinel.services.valuation import PortfolioValuationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

PERIOD_WINDOWS = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365}
PNL_HISTORY_WINDOWS = {"3M": 90, "6M": 180, "1Y": 365, "ALL": None}
BENCHMARK_MAX_STALENESS_DAYS = 5


def _empty_period_stat() -> dict[str, float | None]:
    return {"portfolio_eur": None, "portfolio_pct": None, "benchmark_pct": None, "alpha_pct": None}


def _benchmark_period_return(
    benchmark_rows: list[dict],
    start_date: str,
    end_date: str,
) -> float | None:
    """Return benchmark period performance, or None when either edge is stale/missing."""
    benchmark = sorted(
        ((row["date"], float(row["close"])) for row in benchmark_rows if row.get("close") is not None),
        key=lambda point: point[0],
    )
    benchmark_dates = [point[0] for point in benchmark]
    benchmark_values = [point[1] for point in benchmark]

    def value_on_or_before(target: str) -> float | None:
        index = bisect.bisect_right(benchmark_dates, target) - 1
        if index < 0:
            return None
        found_date = date_type.fromisoformat(benchmark_dates[index])
        target_date = date_type.fromisoformat(target)
        if (target_date - found_date).days > BENCHMARK_MAX_STALENESS_DAYS:
            return None
        return benchmark_values[index]

    start_value = value_on_or_before(start_date)
    end_value = value_on_or_before(end_date)
    if not start_value or end_value is None:
        return None
    return round((end_value / start_value - 1) * 100, 2)


def _trade_iso_date(trade: dict) -> str:
    return datetime.fromtimestamp(int(trade["executed_at"])).date().isoformat()


def _add_cash_effect(effects: dict[str, float], currency: str, amount: float) -> None:
    effects[currency] = effects.get(currency, 0.0) + amount


def _is_fx_trade(symbol: str) -> bool:
    return "/" in symbol


def _apply_trade_effect(
    quantities: dict[str, float],
    cash_effects: dict[str, float],
    trade: dict,
    symbol_currencies: dict[str, str],
) -> None:
    symbol = trade["symbol"]
    side = trade["side"]
    quantity = float(trade["quantity"] or 0.0)
    price = float(trade["price"] or 0.0)
    commission = float(trade.get("commission") or 0.0)
    commission_currency = trade.get("commission_currency") or "EUR"

    if commission:
        _add_cash_effect(cash_effects, commission_currency, -commission)

    if _is_fx_trade(symbol):
        base, quote = symbol.split("/", 1)
        quote_amount = quantity * price
        if side == "BUY":
            _add_cash_effect(cash_effects, base, quantity)
            _add_cash_effect(cash_effects, quote, -quote_amount)
        else:
            _add_cash_effect(cash_effects, base, -quantity)
            _add_cash_effect(cash_effects, quote, quote_amount)
        return

    currency = symbol_currencies.get(symbol)
    if currency is None:
        return

    native_amount = quantity * price
    if side == "BUY":
        quantities[symbol] = quantities.get(symbol, 0.0) - quantity
        _add_cash_effect(cash_effects, currency, -native_amount)
    else:
        quantities[symbol] = quantities.get(symbol, 0.0) + quantity
        _add_cash_effect(cash_effects, currency, native_amount)


async def _position_value_on_date(
    deps: CommonDependencies,
    symbol: str,
    quantity: float,
    currency: str,
    iso_date: str,
    fallback_prices: dict[str, float] | None = None,
) -> float | None:
    if abs(quantity) < 0.0000001:
        return 0.0
    prices = await deps.db.get_prices(symbol, days=1, end_date=iso_date)
    price = None
    if prices:
        price_date = date_type.fromisoformat(prices[0]["date"])
        target_date = date_type.fromisoformat(iso_date)
        if (target_date - price_date).days <= BENCHMARK_MAX_STALENESS_DAYS:
            price = float(prices[0]["close"])
    if price is None and fallback_prices is not None:
        price = fallback_prices.get(symbol)
    if price is None:
        return None
    native_value = quantity * price
    return await deps.currency.to_eur_for_date(native_value, currency, iso_date)


async def _cash_value_on_date(deps: CommonDependencies, cash: dict[str, float], iso_date: str) -> float:
    total = 0.0
    for currency, amount in cash.items():
        if abs(amount) < 0.0000001:
            continue
        total += await deps.currency.to_eur_for_date(amount, currency, iso_date)
    return total


async def _start_value_from_current_state(
    deps: CommonDependencies,
    *,
    current_positions: list[dict],
    current_cash: dict[str, float],
    trades: list[dict],
    cash_flows: list[dict],
    symbol_currencies: dict[str, str],
    start_date: str,
    allow_price_fallback: bool = False,
) -> float | None:
    quantities = {position["symbol"]: float(position.get("quantity") or 0.0) for position in current_positions}
    fallback_prices = {
        position["symbol"]: float(position["current_price"])
        for position in current_positions
        if position.get("current_price") is not None
    }
    cash_effects: dict[str, float] = {}

    for trade in trades:
        if _trade_iso_date(trade) <= start_date:
            continue
        _apply_trade_effect(quantities, cash_effects, trade, symbol_currencies)

    for trade in sorted(trades, key=lambda item: item["executed_at"]):
        if _trade_iso_date(trade) <= start_date or _is_fx_trade(trade["symbol"]):
            continue
        fallback_prices.setdefault(trade["symbol"], float(trade["price"] or 0.0))

    for cf in cash_flows:
        if cf["date"] <= start_date or cf["type_id"] in ("block", "unblock"):
            continue
        _add_cash_effect(cash_effects, cf["currency"], float(cf["amount"] or 0.0))

    start_cash = dict(current_cash)
    for currency, effect in cash_effects.items():
        start_cash[currency] = start_cash.get(currency, 0.0) - effect

    total = await _cash_value_on_date(deps, start_cash, start_date)
    for symbol, quantity in quantities.items():
        currency = symbol_currencies.get(symbol)
        if currency is None:
            continue
        value = await _position_value_on_date(
            deps,
            symbol,
            quantity,
            currency,
            start_date,
            fallback_prices if allow_price_fallback else None,
        )
        if value is None:
            return None
        total += value
    return total


async def _cashflow_value_since(
    deps: CommonDependencies,
    cash_flows: list[dict],
    *,
    start_date: str,
    external_only: bool,
) -> float:
    total = 0.0
    for cf in cash_flows:
        if cf["date"] <= start_date:
            continue
        if external_only and cf["type_id"] not in ("card", "card_payout"):
            continue
        if cf["type_id"] in ("block", "unblock"):
            continue
        total += await deps.currency.to_eur_for_date(cf["amount"], cf["currency"], cf["date"])
    return total


async def _current_net_deposits_eur(deps: CommonDependencies) -> float:
    current_net_deposits = 0.0
    summary = await deps.db.get_cash_flow_summary()
    for type_id, currencies in summary.items():
        if type_id not in ("card", "card_payout"):
            continue
        for curr, total in currencies.items():
            amount_eur = await deps.currency.to_eur(total, curr)
            current_net_deposits += amount_eur if type_id == "card" else -abs(amount_eur)
    return current_net_deposits


async def _period_stats_from_reconstructed_starts(
    deps: CommonDependencies,
    benchmark_rows: list[dict],
    *,
    current_value: float,
    current_net_deposits: float,
    cash_flows: list[dict],
    as_of_date: date_type,
) -> dict[str, dict[str, float | None]]:
    current_positions = await deps.db.get_all_positions()
    current_cash = await deps.db.get_cash_balances()
    securities = await deps.db.get_all_securities(active_only=False)
    symbol_currencies = {security["symbol"]: security.get("currency", "EUR") for security in securities}
    for position in current_positions:
        symbol_currencies[position["symbol"]] = position.get("currency") or symbol_currencies.get(
            position["symbol"], "EUR"
        )

    earliest_start = min(
        [as_of_date - timedelta(days=days) for days in PERIOD_WINDOWS.values()] + [as_of_date.replace(month=1, day=1)]
    )
    trades = await deps.db.get_trades(start_date=earliest_start.isoformat(), limit=10000)

    result: dict[str, dict[str, float | None]] = {}
    as_of_iso = as_of_date.isoformat()

    async def calculate(start_date: date_type, *, allow_price_fallback: bool = False) -> dict[str, float | None]:
        start_iso = start_date.isoformat()
        start_value = await _start_value_from_current_state(
            deps,
            current_positions=current_positions,
            current_cash=current_cash,
            trades=trades,
            cash_flows=cash_flows,
            symbol_currencies=symbol_currencies,
            start_date=start_iso,
            allow_price_fallback=allow_price_fallback,
        )
        if start_value is None or start_value <= 0:
            return _empty_period_stat()

        external_cashflow = await _cashflow_value_since(
            deps,
            cash_flows,
            start_date=start_iso,
            external_only=True,
        )
        portfolio_eur = round(current_value - start_value - external_cashflow, 2)
        portfolio_pct = round((portfolio_eur / start_value) * 100, 2)
        benchmark_pct = _benchmark_period_return(benchmark_rows, start_iso, as_of_iso)
        return {
            "portfolio_eur": portfolio_eur,
            "portfolio_pct": portfolio_pct,
            "benchmark_pct": benchmark_pct,
            "alpha_pct": round(portfolio_pct - benchmark_pct, 2) if benchmark_pct is not None else None,
        }

    for label, days in PERIOD_WINDOWS.items():
        result[label] = await calculate(as_of_date - timedelta(days=days), allow_price_fallback=label in {"1W", "1M"})
    result["YTD"] = await calculate(as_of_date.replace(month=1, day=1))

    all_portfolio_eur = round(current_value - current_net_deposits, 2)
    all_portfolio_pct = round((all_portfolio_eur / current_net_deposits) * 100, 2) if current_net_deposits > 0 else None
    result["All"] = {
        "portfolio_eur": all_portfolio_eur,
        "portfolio_pct": all_portfolio_pct,
        "benchmark_pct": None,
        "alpha_pct": None,
    }
    return result


async def _snapshot_adjusted_period_stats(
    deps: CommonDependencies,
    benchmark_rows: list[dict],
    *,
    current_value: float,
    current_net_deposits: float,
    cash_flows: list[dict],
    as_of_date: date_type,
) -> dict[str, dict[str, float | None]]:
    """Long-window stats from snapshots, adjusted to the live endpoint value."""
    from sentinel.portfolio_composition import build_daily_pnl

    snapshots = await deps.db.get_portfolio_snapshots()
    if not snapshots:
        return {}

    deposits_by_date: dict[str, float] = {}
    running = 0.0
    for cf in sorted([cf for cf in cash_flows if cf["type_id"] in ("card", "card_payout")], key=lambda cf: cf["date"]):
        amount_eur = await deps.currency.to_eur_for_date(cf["amount"], cf["currency"], cf["date"])
        running += amount_eur
        deposits_by_date[cf["date"]] = running

    daily = build_daily_pnl(snapshots, deposits_by_date)
    dates = [point["date"] for point in daily]
    as_of_iso = as_of_date.isoformat()

    def index_on_or_before(target: str) -> int | None:
        index = bisect.bisect_right(dates, target) - 1
        return index if index >= 0 else None

    def calculate(label: str, start_date: date_type) -> tuple[str, dict[str, float | None]] | None:
        start_index = index_on_or_before(start_date.isoformat())
        if start_index is None:
            return None
        start = daily[start_index]
        start_value = start["total_value_eur"]
        if start_value <= 0:
            return None

        portfolio_eur = round(current_value - start_value - (current_net_deposits - start["net_deposits_eur"]), 2)
        portfolio_pct = round((portfolio_eur / start_value) * 100, 2)
        benchmark_pct = _benchmark_period_return(benchmark_rows, start["date"], as_of_iso)
        return label, {
            "portfolio_eur": portfolio_eur,
            "portfolio_pct": portfolio_pct,
            "benchmark_pct": benchmark_pct,
            "alpha_pct": round(portfolio_pct - benchmark_pct, 2) if benchmark_pct is not None else None,
        }

    pairs = [
        calculate("6M", as_of_date - timedelta(days=180)),
        calculate("1Y", as_of_date - timedelta(days=365)),
        calculate("YTD", as_of_date.replace(month=1, day=1)),
    ]
    return dict(pair for pair in pairs if pair is not None)


def _intraday_stat_from_valuation(
    valuation: dict[str, Any],
) -> dict[str, float | None] | None:
    """Current-vs-previous-close move from the shared live valuation."""
    intraday_pnl = valuation.get("intraday_pnl_eur")
    if intraday_pnl is None:
        return None
    current_value = float(valuation.get("total_value_eur") or 0.0)
    portfolio_eur = round(float(intraday_pnl), 2)
    start_value = current_value - portfolio_eur
    portfolio_pct = round((portfolio_eur / start_value) * 100, 2) if start_value > 0 else None
    return {
        "portfolio_eur": portfolio_eur,
        "portfolio_pct": portfolio_pct,
        "benchmark_pct": None,
        "alpha_pct": None,
    }


@router.get("")
async def get_portfolio(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Get current portfolio state."""
    service = PortfolioService(
        db=deps.db,
        portfolio=None,  # Uses singleton
        currency=deps.currency,
    )
    return await service.get_portfolio_state()


@router.get("/structure")
async def get_portfolio_structure(force: bool = False) -> dict[str, Any]:
    """PRAAMS portfolio analysis from freedom24.com (rating, risk/return radar,
    sector/region/currency breakdowns, replacement recommendations).

    Requires `freedom24_login` and `freedom24_password` to be set. Result is
    cached in memory for 5 minutes; pass ?force=true to bypass.
    """
    data = await Freedom24WebClient().get_portfolio_structure(force_refresh=force)
    if data is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not fetch portfolio structure. Check freedom24_login / "
                "freedom24_password settings and try again."
            ),
        )
    return data


@router.post("/sync")
async def sync_portfolio() -> dict[str, str]:
    """Sync portfolio from broker."""
    service = PortfolioService()
    return await service.sync_portfolio()


@router.get("/composition")
async def get_portfolio_composition(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Portfolio composition + risk/return metrics for the sidebar widgets.

    Surfaces: composition breakdowns (% of EUR value by country, continent,
    industry, currency, asset class), portfolio-level metrics (1Y/5Y return,
    volatility, max drawdown, Sharpe, beta vs VWCE.EU, HHI concentration),
    and the six radar axes derived from those metrics. See
    `sentinel.portfolio_composition` for the math.
    """
    from sentinel.portfolio_composition import build_composition

    return await build_composition(deps.db, deps.currency, deps.settings)


@router.get("/cagr")
async def get_portfolio_cagr(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Lightweight CAGR from inception for ambient display."""
    snapshots = await deps.db.get_portfolio_snapshots()
    if not snapshots:
        return {"cagr": 0.0, "years": 0.0, "target": 11.0}

    # Latest snapshot → final value
    latest = snapshots[-1]
    data = latest["data"]
    positions_value = sum(p.get("value_eur", 0) for p in data.get("positions", {}).values())
    final_value = positions_value + (data.get("cash_eur", 0.0) or 0.0)

    # Net deposits from card cash flows
    cash_flows = await deps.db.get_cash_flows()
    total_deposits = 0.0
    for cf in cash_flows:
        if cf["type_id"] in ("card", "card_payout"):
            amount_eur = await deps.currency.to_eur_for_date(cf["amount"], cf["currency"], cf["date"])
            total_deposits += amount_eur

    # Years from first snapshot to now
    first_ts = snapshots[0]["date"]
    last_ts = snapshots[-1]["date"]
    years = (last_ts - first_ts) / (365.25 * 86400)

    if years > 0 and total_deposits > 0 and final_value > 0:
        cagr = ((final_value / total_deposits) ** (1 / years) - 1) * 100
    else:
        cagr = 0.0

    return {
        "cagr": round(cagr, 2),
        "years": round(years, 2),
        "target": 11.0,
    }


@router.get("/pnl-history")
async def get_portfolio_pnl_history(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    period: str = "1Y",
) -> dict[str, Any]:
    """
    Get portfolio P&L history for the selected chart range.

    Snapshots store only positions + cash. All derived metrics
    (total_value, net_deposits, returns) are computed at query time via
    the shared helpers in `sentinel.portfolio_composition`.
    """
    from sentinel.portfolio_composition import build_daily_pnl

    period = period.upper()
    if period not in PNL_HISTORY_WINDOWS:
        allowed = ", ".join(PNL_HISTORY_WINDOWS)
        raise HTTPException(status_code=400, detail=f"Invalid P&L period. Expected one of: {allowed}")
    days = PNL_HISTORY_WINDOWS[period]

    # Bounded ranges need an extra year to calculate the first rolling return.
    # ALL deliberately reads the complete snapshot history.
    # Snapshot maintenance is handled by scheduled jobs; avoid backfill work on request path.
    snapshot_days = days + 365 if days is not None else None
    snapshots = await deps.db.get_portfolio_snapshots(snapshot_days)

    if not snapshots:
        return {"snapshots": [], "summary": None}

    # Cumulative net-deposits lookup keyed by ISO date. Card deposits +
    # withdrawals (card_payout) only — that's what funds the account.
    cash_flows = await deps.db.get_cash_flows()
    cf_sorted = sorted(
        [cf for cf in cash_flows if cf["type_id"] in ("card", "card_payout")],
        key=lambda cf: cf["date"],
    )
    deposits_by_date: dict[str, float] = {}
    running = 0.0
    for cf in cf_sorted:
        amount_eur = await deps.currency.to_eur_for_date(cf["amount"], cf["currency"], cf["date"])
        running += amount_eur
        deposits_by_date[cf["date"]] = running

    daily = build_daily_pnl(snapshots, deposits_by_date)
    valuation = await PortfolioValuationService(db=deps.db, broker=deps.broker, currency=deps.currency).current()
    current_value = valuation["total_value_eur"]
    if current_value > 0:
        current_net_deposits = await _current_net_deposits_eur(deps)
        today_iso = date_type.today().isoformat()
        pnl_eur = current_value - current_net_deposits
        live_point = {
            "date": today_iso,
            "total_value_eur": round(current_value, 2),
            "net_deposits_eur": round(current_net_deposits, 2),
            "pnl_eur": round(pnl_eur, 2),
            "pnl_pct": round((pnl_eur / current_net_deposits * 100), 2) if current_net_deposits > 0 else 0.0,
        }
        if daily and daily[-1]["date"] == today_iso:
            daily[-1] = live_point
        elif not daily or daily[-1]["date"] < today_iso:
            daily.append(live_point)

    # --- Build output with rolling TWR ---
    window = 365
    if days is None:
        output_start = window
    else:
        start_date = (date_type.today() - timedelta(days=days)).isoformat()
        output_start = 0
        for idx, d in enumerate(daily):
            if d["date"] >= start_date:
                output_start = idx
                break
        output_start = max(output_start, window)

    last_daily_idx = len(daily) - 1

    result_snapshots = []
    i = output_start
    while i < last_daily_idx + 1:
        in_future = i > last_daily_idx

        if in_future:
            last_date = datetime.strptime(daily[last_daily_idx]["date"], "%Y-%m-%d")
            future_date = last_date + timedelta(days=i - last_daily_idx)
            point = {
                "date": future_date.strftime("%Y-%m-%d"),
                "total_value_eur": None,
                "net_deposits_eur": None,
                "pnl_eur": None,
                "pnl_pct": None,
            }
        else:
            d = daily[i]
            point = {
                "date": d["date"],
                "total_value_eur": d["total_value_eur"],
                "net_deposits_eur": d["net_deposits_eur"],
                "pnl_eur": d["pnl_eur"],
                "pnl_pct": d["pnl_pct"],
            }

        # Actual: 365-day rolling TWR
        if not in_future and i >= window:
            cumulative = 1.0
            valid = True
            for j in range(i - window + 1, i + 1):
                prev_val = daily[j - 1]["total_value_eur"]
                curr_val = daily[j]["total_value_eur"]
                cash_flow = daily[j]["net_deposits_eur"] - daily[j - 1]["net_deposits_eur"]
                if prev_val and prev_val > 0:
                    hpr = (curr_val - prev_val - cash_flow) / prev_val
                    cumulative *= 1.0 + hpr
                else:
                    valid = False
                    break
            if valid:
                point["actual_ann_return"] = round((cumulative - 1.0) * 100.0, 2)
            else:
                point["actual_ann_return"] = None
        else:
            point["actual_ann_return"] = None

        result_snapshots.append(point)
        i += 1

    if not result_snapshots:
        return {"snapshots": [], "summary": None}

    # Overlay the benchmark's trailing-1Y return on the same axis as the
    # portfolio's rolling TWR — the honest "would a plain all-world ETF have
    # done better?" comparison. Degrades to nulls if the benchmark has no data.
    from sentinel.portfolio_composition import benchmark_rolling_returns

    benchmark_symbol = await deps.settings.get("performance_benchmark_symbol", "VWCE.EU")
    # The benchmark is an investable ETF held in the `prices` table (e.g. VWCE.EU).
    benchmark_days = days + 365 + 10 if days is not None else None
    benchmark_rows = await deps.db.get_prices(benchmark_symbol, days=benchmark_days)
    benchmark_returns = benchmark_rolling_returns(
        benchmark_rows or [],
        [s["date"] for s in result_snapshots],
        window_days=window,
    )
    for s in result_snapshots:
        s["benchmark_ann_return"] = benchmark_returns.get(s["date"])

    first = result_snapshots[0]
    last = first
    last_benchmark = None
    for s in result_snapshots:
        if s["total_value_eur"] is not None:
            last = s
        if s.get("benchmark_ann_return") is not None:
            last_benchmark = s["benchmark_ann_return"]

    summary = {
        "start_value": first["total_value_eur"],
        "end_value": last["total_value_eur"],
        "start_net_deposits": first["net_deposits_eur"],
        "end_net_deposits": last["net_deposits_eur"],
        "pnl_absolute": last["pnl_eur"],
        "pnl_percent": last["pnl_pct"],
        "target_ann_return": 11.0,
        "benchmark_symbol": benchmark_symbol,
        "benchmark_ann_return": last_benchmark,
        "actual_ann_return": last.get("actual_ann_return"),
    }

    return {"snapshots": result_snapshots, "summary": summary}


@router.get("/period-stats")
async def get_portfolio_period_stats(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Table-only portfolio period stats using live current value as the endpoint."""
    cash_flows = await deps.db.get_cash_flows()

    current_net_deposits = await _current_net_deposits_eur(deps)
    benchmark_symbol = await deps.settings.get("performance_benchmark_symbol", "VWCE.EU")
    benchmark_rows = await deps.db.get_prices(benchmark_symbol)
    valuation = await PortfolioValuationService(db=deps.db, broker=deps.broker, currency=deps.currency).current()
    current_value = valuation["total_value_eur"]

    as_of_date = date_type.today()
    period_stats = await _period_stats_from_reconstructed_starts(
        deps,
        benchmark_rows or [],
        current_value=current_value,
        current_net_deposits=current_net_deposits,
        cash_flows=cash_flows,
        as_of_date=as_of_date,
    )
    period_stats.update(
        await _snapshot_adjusted_period_stats(
            deps,
            benchmark_rows or [],
            current_value=current_value,
            current_net_deposits=current_net_deposits,
            cash_flows=cash_flows,
            as_of_date=as_of_date,
        )
    )
    intraday_stat = _intraday_stat_from_valuation(valuation)
    if intraday_stat is not None:
        period_stats["1D"] = intraday_stat
    return {
        "as_of_date": as_of_date.isoformat(),
        "benchmark_symbol": benchmark_symbol,
        "period_stats": period_stats,
    }
