"""Portfolio API routes."""

import bisect
import logging
import math
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from typing_extensions import Annotated

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.freedom24_web import Freedom24WebClient
from sentinel.planner.deposit_history import DepositHistoryHelper
from sentinel.services.portfolio import PortfolioService
from sentinel.services.valuation import PortfolioValuationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

PERIOD_WINDOWS = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365}
PNL_HISTORY_WINDOWS = {"3M": 90, "6M": 180, "1Y": 365, "ALL": None}
BENCHMARK_MAX_STALENESS_DAYS = 5
VALUE_PROJECTION_YEARS = {5, 10, 15, 20, 25}
DEFAULT_VALUE_PROJECTION_YEARS = 10
MONTHS_PER_YEAR = 12
AVG_DAYS_PER_MONTH = 365.25 / 12
MWR_DAYS_PER_YEAR = 365.0


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
        amount_eur = await deps.currency.to_eur_for_date(cf["amount"], cf["currency"], cf["date"])
        total += -abs(amount_eur) if cf["type_id"] == "card_payout" else amount_eur
    return total


async def _external_cashflow_delta_eur(deps: CommonDependencies, cashflow: dict) -> float:
    """EUR funding delta: deposits add, withdrawals subtract."""
    amount_eur = await deps.currency.to_eur_for_date(cashflow["amount"], cashflow["currency"], cashflow["date"])
    return -abs(amount_eur) if cashflow["type_id"] == "card_payout" else amount_eur


async def _current_net_deposits_eur(
    deps: CommonDependencies,
    cash_flows: list[dict] | None = None,
) -> float:
    """Return cumulative external funding using transaction-date FX.

    Historical portfolio points value each contribution on its transaction
    date. The live point must use the same basis; converting currency totals at
    today's rate creates a synthetic cash flow whenever FX moves.
    """
    if cash_flows is None:
        cash_flows = await deps.db.get_cash_flows()

    current_net_deposits = 0.0
    for cash_flow in cash_flows:
        if cash_flow["type_id"] not in ("card", "card_payout"):
            continue
        current_net_deposits += await _external_cashflow_delta_eur(deps, cash_flow)
    return current_net_deposits


async def _cumulative_external_deposits_by_date(
    deps: CommonDependencies,
    cash_flows: list[dict],
) -> dict[str, float]:
    """Return cumulative account funding keyed by cash-flow date."""
    cf_sorted = sorted(
        [cf for cf in cash_flows if cf["type_id"] in ("card", "card_payout")],
        key=lambda cf: cf["date"],
    )
    deposits_by_date: dict[str, float] = {}
    running = 0.0
    for cf in cf_sorted:
        running += await _external_cashflow_delta_eur(deps, cf)
        deposits_by_date[cf["date"]] = running
    return deposits_by_date


async def _daily_portfolio_value_history(
    deps: CommonDependencies,
    snapshots: list[dict],
    cash_flows: list[dict],
    *,
    current_value: float | None = None,
    current_net_deposits: float | None = None,
) -> list[dict]:
    """Build daily value history and splice in the live current value for today."""
    from sentinel.portfolio_composition import build_daily_pnl

    deposits_by_date = await _cumulative_external_deposits_by_date(deps, cash_flows)
    daily = build_daily_pnl(snapshots, deposits_by_date)
    if current_value is None:
        valuation = await PortfolioValuationService(db=deps.db, broker=deps.broker, currency=deps.currency).current()
        current_value = float(valuation["total_value_eur"])
    if current_value > 0:
        live_net_deposits = (
            await _current_net_deposits_eur(deps, cash_flows) if current_net_deposits is None else current_net_deposits
        )
        today_iso = date_type.today().isoformat()
        pnl_eur = current_value - live_net_deposits
        live_point = {
            "date": today_iso,
            "total_value_eur": round(current_value, 2),
            "net_deposits_eur": round(live_net_deposits, 2),
            "pnl_eur": round(pnl_eur, 2),
            "pnl_pct": round((pnl_eur / live_net_deposits * 100), 2) if live_net_deposits > 0 else 0.0,
        }
        if daily and daily[-1]["date"] == today_iso:
            daily[-1] = live_point
        elif not daily or daily[-1]["date"] < today_iso:
            daily.append(live_point)
    return daily


def _annualized_money_weighted_return(
    daily: list[dict],
    *,
    opening_value_as_contribution: bool,
) -> float | None:
    """Return the XIRR-style annual rate implied by dated external funding.

    Since-inception calculations use every deposit and withdrawal. Bounded
    periods additionally treat the opening portfolio value as the capital
    invested at the start of the period, then apply only later external flows.
    """
    if len(daily) < 2:
        return None

    start = date_type.fromisoformat(daily[0]["date"])
    end = date_type.fromisoformat(daily[-1]["date"])
    if end <= start:
        return None

    current_value = float(daily[-1]["total_value_eur"] or 0.0)
    if current_value <= 0:
        return None

    contributions: list[tuple[date_type, float]] = []
    if opening_value_as_contribution:
        opening_value = float(daily[0]["total_value_eur"] or 0.0)
        if opening_value <= 0:
            return None
        contributions.append((start, opening_value))
        previous_net_deposits = float(daily[0]["net_deposits_eur"] or 0.0)
        cash_flow_points = daily[1:]
    else:
        previous_net_deposits = 0.0
        cash_flow_points = daily

    for point in cash_flow_points:
        net_deposits = float(point["net_deposits_eur"] or 0.0)
        contribution = net_deposits - previous_net_deposits
        if abs(contribution) >= 0.01:
            contributions.append((date_type.fromisoformat(point["date"]), contribution))
        previous_net_deposits = net_deposits

    if not contributions or not any(amount > 0 for _date, amount in contributions):
        return None

    def accumulated_value(annual_return: float) -> float:
        growth_base = max(0.000001, 1.0 + annual_return)
        total = 0.0
        for contribution_date, contribution in contributions:
            years_until_end = max((end - contribution_date).days / MWR_DAYS_PER_YEAR, 0.0)
            total += contribution * (growth_base**years_until_end)
        return total

    low = -0.999999
    high = 1.0
    low_residual = accumulated_value(low) - current_value
    high_residual = accumulated_value(high) - current_value
    while low_residual * high_residual > 0 and high < 100.0:
        high = (high * 2.0) + 1.0
        high_residual = accumulated_value(high) - current_value

    if low_residual * high_residual > 0:
        return None

    for _iteration in range(100):
        mid = (low + high) / 2.0
        mid_residual = accumulated_value(mid) - current_value
        if low_residual * mid_residual <= 0:
            high = mid
        else:
            low = mid
            low_residual = mid_residual

    return (low + high) / 2.0


def _projection_monthly_return(daily: list[dict]) -> tuple[float | None, float | None, float]:
    """Annualize dated net contributions into a monthly money-weighted return."""
    if len(daily) < 2:
        return None, None, 0.0

    start = date_type.fromisoformat(daily[0]["date"])
    end = date_type.fromisoformat(daily[-1]["date"])
    elapsed_months = max((end - start).days / AVG_DAYS_PER_MONTH, 1.0)
    annualized_return = _annualized_money_weighted_return(
        daily,
        opening_value_as_contribution=False,
    )
    if annualized_return is None:
        return None, None, elapsed_months

    monthly_return = ((1.0 + annualized_return) ** (1.0 / MONTHS_PER_YEAR)) - 1.0
    return monthly_return, annualized_return, elapsed_months


def _trailing_money_weighted_return(
    daily: list[dict],
    end_index: int,
    *,
    window_days: int = 365,
) -> float | None:
    """Annualized investor return ending at one point over a bounded window."""
    if end_index <= 0 or end_index >= len(daily):
        return None

    end = date_type.fromisoformat(daily[end_index]["date"])
    target_start = end - timedelta(days=window_days)
    dates = [point["date"] for point in daily[: end_index + 1]]
    start_index = bisect.bisect_right(dates, target_start.isoformat()) - 1
    if start_index < 0:
        return None

    actual_start = date_type.fromisoformat(daily[start_index]["date"])
    if (target_start - actual_start).days > BENCHMARK_MAX_STALENESS_DAYS:
        return None

    return _annualized_money_weighted_return(
        daily[start_index : end_index + 1],
        opening_value_as_contribution=True,
    )


def _compound_projected_value(
    current_value: float,
    monthly_return: float,
    avg_monthly_net_deposit: float,
    projection_months: int,
) -> float:
    projected_value = current_value
    for _month in range(1, projection_months + 1):
        projected_value = max(0.0, projected_value * (1.0 + monthly_return) + avg_monthly_net_deposit)
    return projected_value


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


def _snapshot_adjusted_period_stats(
    benchmark_rows: list[dict],
    *,
    daily: list[dict],
    current_value: float,
    current_net_deposits: float,
    as_of_date: date_type,
) -> dict[str, dict[str, float | None]]:
    """Long-window stats from snapshots, adjusted to the live endpoint value."""
    if not daily:
        return {}
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
            total_deposits += await _external_cashflow_delta_eur(deps, cf)

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
    daily = await _daily_portfolio_value_history(deps, snapshots, cash_flows)

    # Build the rolling 365-day investor return. This uses the opening value,
    # every later deposit/withdrawal, and the closing value; it does not chain
    # day-to-day holding-period returns.
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

        annualized_mwr = None if in_future else _trailing_money_weighted_return(daily, i, window_days=window)
        rolling_mwr_pct = round(annualized_mwr * 100.0, 2) if annualized_mwr is not None else None
        point["rolling_365d_money_weighted_return_pct"] = rolling_mwr_pct
        # Backward-compatible generic field used by older clients.
        point["actual_ann_return"] = rolling_mwr_pct

        result_snapshots.append(point)
        i += 1

    if not result_snapshots:
        return {"snapshots": [], "summary": None}

    # Overlay the benchmark's trailing-1Y market return as context. The
    # portfolio series itself is money-weighted using the investor's cash flows.
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
        "trailing_365d_money_weighted_return_pct": last.get("rolling_365d_money_weighted_return_pct"),
    }

    return {"snapshots": result_snapshots, "summary": summary}


@router.get("/value-projection")
async def get_portfolio_value_projection(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
    years: int = DEFAULT_VALUE_PROJECTION_YEARS,
    avg_monthly_net_deposit_eur: Annotated[float | None, Query()] = None,
) -> dict[str, Any]:
    """Portfolio value history plus a selected-horizon projection.

    The forward series uses the same rolling 6-month net deposit helper the
    planner uses, then compounds the portfolio by the money-weighted inception
    run-rate implied by dated net deposits/withdrawals and today's value.
    """
    if years not in VALUE_PROJECTION_YEARS:
        allowed = ", ".join(f"{value}Y" for value in sorted(VALUE_PROJECTION_YEARS))
        raise HTTPException(status_code=400, detail=f"Invalid projection horizon. Expected one of: {allowed}")
    if avg_monthly_net_deposit_eur is not None and not math.isfinite(avg_monthly_net_deposit_eur):
        raise HTTPException(status_code=400, detail="Invalid monthly net deposit override")

    snapshots = await deps.db.get_portfolio_snapshots()
    if not snapshots:
        return {"history": [], "projection": [], "summary": None}

    cash_flows = await deps.db.get_cash_flows()
    daily = await _daily_portfolio_value_history(deps, snapshots, cash_flows)
    if not daily:
        return {"history": [], "projection": [], "summary": None}

    today_iso = date_type.today().isoformat()
    current = daily[-1]
    current_value = float(current["total_value_eur"] or 0.0)
    current_net_deposits = float(current["net_deposits_eur"] or 0.0)
    total_pnl_eur = current_value - current_net_deposits
    total_pnl_pct = (total_pnl_eur / current_net_deposits * 100.0) if current_net_deposits > 0 else 0.0

    actual_avg_monthly_net_deposit = await DepositHistoryHelper(
        db=deps.db, currency=deps.currency
    ).get_rolling_6m_avg_net_deposit(as_of_date=today_iso)
    avg_monthly_net_deposit = (
        float(avg_monthly_net_deposit_eur)
        if avg_monthly_net_deposit_eur is not None
        else actual_avg_monthly_net_deposit
    )
    monthly_return, annualized_return, elapsed_months = _projection_monthly_return(daily)
    projection_monthly_return = monthly_return if monthly_return is not None else 0.0

    projection: list[dict[str, Any]] = [
        {
            "date": today_iso,
            "projected_value_eur": round(current_value, 2),
            "months_ahead": 0,
        }
    ]
    projected_value = current_value
    projection_months = years * MONTHS_PER_YEAR
    today = date_type.fromisoformat(today_iso)
    for month in range(1, projection_months + 1):
        projected_value = max(0.0, projected_value * (1.0 + projection_monthly_return) + avg_monthly_net_deposit)
        projected_date = today + timedelta(days=round(month * AVG_DAYS_PER_MONTH))
        projection.append(
            {
                "date": projected_date.isoformat(),
                "projected_value_eur": round(projected_value, 2),
                "months_ahead": month,
            }
        )
    actual_projected_value = (
        projected_value
        if avg_monthly_net_deposit_eur is None
        else _compound_projected_value(
            current_value,
            projection_monthly_return,
            actual_avg_monthly_net_deposit,
            projection_months,
        )
    )
    projected_future_net_deposits = avg_monthly_net_deposit * projection_months
    projected_net_deposits = current_net_deposits + projected_future_net_deposits
    actual_projected_future_net_deposits = actual_avg_monthly_net_deposit * projection_months
    actual_projected_net_deposits = current_net_deposits + actual_projected_future_net_deposits

    summary = {
        "start_date": daily[0]["date"],
        "current_date": today_iso,
        "current_value_eur": round(current_value, 2),
        "current_net_deposits_eur": round(current_net_deposits, 2),
        "total_pnl_eur": round(total_pnl_eur, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "annualized_total_pnl_pct": round(annualized_return * 100.0, 2) if annualized_return is not None else None,
        "monthly_return_rate": monthly_return,
        "avg_monthly_net_deposit_eur": round(avg_monthly_net_deposit, 2),
        "actual_avg_monthly_net_deposit_eur": round(actual_avg_monthly_net_deposit, 2),
        "avg_monthly_net_deposit_override_eur": (
            round(avg_monthly_net_deposit, 2) if avg_monthly_net_deposit_eur is not None else None
        ),
        "deposit_window_months": DepositHistoryHelper.WINDOW_MONTHS,
        "projection_years": years,
        "projection_months": projection_months,
        "projected_value_eur": round(projected_value, 2),
        "actual_projected_value_eur": round(actual_projected_value, 2),
        "projected_future_net_deposits_eur": round(projected_future_net_deposits, 2),
        "projected_net_deposits_eur": round(projected_net_deposits, 2),
        "actual_projected_future_net_deposits_eur": round(actual_projected_future_net_deposits, 2),
        "actual_projected_net_deposits_eur": round(actual_projected_net_deposits, 2),
        "elapsed_months": round(elapsed_months, 1),
    }

    return {
        "history": [
            {
                "date": point["date"],
                "total_value_eur": point["total_value_eur"],
                "net_deposits_eur": point["net_deposits_eur"],
                "pnl_eur": point["pnl_eur"],
                "pnl_pct": point["pnl_pct"],
            }
            for point in daily
        ],
        "projection": projection,
        "summary": summary,
    }


@router.get("/period-stats")
async def get_portfolio_period_stats(
    deps: Annotated[CommonDependencies, Depends(get_common_deps)],
) -> dict[str, Any]:
    """Table-only portfolio period stats using live current value as the endpoint."""
    cash_flows = await deps.db.get_cash_flows()

    current_net_deposits = await _current_net_deposits_eur(deps, cash_flows)
    benchmark_symbol = await deps.settings.get("performance_benchmark_symbol", "VWCE.EU")
    benchmark_rows = await deps.db.get_prices(benchmark_symbol)
    valuation = await PortfolioValuationService(db=deps.db, broker=deps.broker, currency=deps.currency).current()
    current_value = valuation["total_value_eur"]
    snapshots = await deps.db.get_portfolio_snapshots()
    daily = await _daily_portfolio_value_history(
        deps,
        snapshots,
        cash_flows,
        current_value=current_value,
        current_net_deposits=current_net_deposits,
    )
    since_inception_money_weighted_return_pct = None
    if len(daily) >= 2:
        _monthly_return, annualized_return, _elapsed_months = _projection_monthly_return(daily)
        if annualized_return is not None:
            since_inception_money_weighted_return_pct = round(annualized_return * 100.0, 2)

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
        _snapshot_adjusted_period_stats(
            benchmark_rows or [],
            daily=daily,
            current_value=current_value,
            current_net_deposits=current_net_deposits,
            as_of_date=as_of_date,
        )
    )
    intraday_stat = _intraday_stat_from_valuation(valuation)
    if intraday_stat is not None:
        period_stats["1D"] = intraday_stat
    return {
        "as_of_date": as_of_date.isoformat(),
        "benchmark_symbol": benchmark_symbol,
        "since_inception_money_weighted_return_pct": since_inception_money_weighted_return_pct,
        "period_stats": period_stats,
    }
