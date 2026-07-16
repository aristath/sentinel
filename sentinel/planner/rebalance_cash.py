"""Cash-constraint and deficit-funding helpers for the rebalance engine."""

from __future__ import annotations

import inspect
import logging
import math
from dataclasses import replace
from typing import TYPE_CHECKING

from sentinel.strategy import compute_contrarian_signal

from .models import PlannerState, TradeRecommendation
from .preferences import is_explicit_downgrade, normalize_user_multiplier
from .rebalance_rules import buy_rank_key, calculate_transaction_cost

if TYPE_CHECKING:
    from .rebalance import RebalanceEngine

logger = logging.getLogger(__name__)


async def _setting(engine: "RebalanceEngine", key: str, default: float | int) -> float | int:
    """Read setting with safe fallback for mocked/unit-test engines."""
    try:
        value = await engine._settings.get(key, default)
    except Exception:
        return default
    return default if value is None else value


async def _load_latest_trades(engine: "RebalanceEngine", symbols: list[str]) -> dict[str, dict]:
    """Best-effort latest-trade-per-symbol lookup for cool-off gating.

    Returns an empty map when the backing db doesn't expose the bulk getter
    (e.g. mocked engines in unit tests), in which case cool-off gating is a
    no-op and the caller falls back to its prior behaviour.
    """
    getter = getattr(engine._db, "get_latest_trades_for_symbols", None)
    if not callable(getter) or not symbols:
        return {}
    try:
        maybe = getter(symbols)
        result = await maybe if inspect.isawaitable(maybe) else maybe
    except Exception:
        return {}
    return result if isinstance(result, dict) else {}


async def _one_lot_value_eur(
    engine: "RebalanceEngine",
    buy: TradeRecommendation,
    fx_rates: dict[str, float],
) -> float:
    one_lot_local = buy.lot_size * buy.price
    if buy.currency == "EUR":
        return one_lot_local
    rate = fx_rates.get(buy.currency, 0.0)
    if rate > 0:
        return one_lot_local * rate
    return await engine._currency.to_eur(one_lot_local, buy.currency)


async def _value_to_quantity(
    engine: "RebalanceEngine",
    buy: TradeRecommendation,
    value_eur: float,
    fx_rates: dict[str, float],
) -> tuple[int, float]:
    if value_eur <= 0 or buy.price <= 0 or buy.lot_size <= 0:
        return 0, 0.0

    if buy.currency != "EUR":
        rate = fx_rates.get(buy.currency, 0.0)
        local_value = value_eur / rate if rate > 0 else value_eur
    else:
        local_value = value_eur

    raw_qty = local_value / buy.price
    qty = (int(raw_qty) // buy.lot_size) * buy.lot_size
    qty = min(qty, buy.quantity)
    if qty < buy.lot_size:
        return 0, 0.0

    actual_local = qty * buy.price
    if buy.currency != "EUR":
        rate = fx_rates.get(buy.currency, 0.0)
        actual_eur = actual_local * rate if rate > 0 else await engine._currency.to_eur(actual_local, buy.currency)
    else:
        actual_eur = actual_local
    return qty, actual_eur


async def apply_cash_constraint(
    *,
    engine: "RebalanceEngine",
    recommendations: list[TradeRecommendation],
    min_trade_value: float,
    as_of_date: str | None = None,
    ideal: dict[str, float] | None = None,
    current: dict[str, float] | None = None,
    total_value: float | None = None,
    planning_total_value: float | None = None,
    symbol_convictions: dict[str, float] | None = None,
    preloaded_positions: list[dict] | None = None,
    preloaded_securities_map: dict[str, dict] | None = None,
    preloaded_symbol_scores: dict[str, float] | None = None,
    preloaded_symbol_prices: dict[str, float] | None = None,
    eligible_symbols: set[str] | None = None,
    state: PlannerState | None = None,
) -> list[TradeRecommendation]:
    """Scale down buy recommendations to fit within available cash."""
    fixed_fee = await engine._settings.get("transaction_fee_fixed", 2.0)
    pct_fee = await engine._settings.get("transaction_fee_percent", 0.2) / 100

    sells = [r for r in recommendations if r.action == "sell"]
    base_sells = list(sells)
    buys = sorted((r for r in recommendations if r.action == "buy"), key=buy_rank_key)

    if not buys:
        return recommendations

    currencies = {b.currency for b in buys if b.currency != "EUR"}
    fx_rates = {currency: await engine._currency.get_rate(currency) for currency in currencies}

    # Calculate available budget
    if state is not None:
        current_cash = state.cash_eur()
    else:
        current_cash = await engine._portfolio.total_cash_eur()

    reserve_base = float(total_value or 0.0)
    if reserve_base <= 0 and state is None:
        maybe_total = engine._portfolio.total_value()
        if inspect.isawaitable(maybe_total):
            maybe_total = await maybe_total
        reserve_base = float(maybe_total) if isinstance(maybe_total, int | float) else 0.0
    min_cash_buffer = max(0.0, float(await _setting(engine, "min_cash_buffer", 0.005)))
    cash_reserve = reserve_base * min_cash_buffer

    net_sell_proceeds = sum(
        abs(r.value_delta_eur) - calculate_transaction_cost(abs(r.value_delta_eur), fixed_fee, pct_fee) for r in sells
    )
    available_budget = max(0.0, current_cash + net_sell_proceeds - cash_reserve)

    # Calculate total buy costs
    total_buy_costs = sum(
        r.value_delta_eur + calculate_transaction_cost(r.value_delta_eur, fixed_fee, pct_fee) for r in buys
    )

    # When budget is tight, treat lower-conviction names as opportunistic:
    # trim weakest buys first before forcing additional funding sells.
    if symbol_convictions:
        conviction_by_symbol = {
            symbol: max(0.0, min(1.0, float(value))) for symbol, value in symbol_convictions.items()
        }
    else:
        conviction_by_symbol: dict[str, float] = {}
        get_securities = getattr(engine._db, "get_all_securities", None)
        if callable(get_securities):
            maybe_all = get_securities(active_only=False)
            if inspect.isawaitable(maybe_all):
                all_securities = await maybe_all
            elif isinstance(maybe_all, list):
                all_securities = maybe_all
            else:
                all_securities = []
            conviction_by_symbol = {
                s["symbol"]: max(
                    0.0,
                    min(
                        1.0,
                        float(normalize_user_multiplier(s.get("user_multiplier", 0.5))),
                    ),
                )
                for s in all_securities
            }
    if total_buy_costs <= available_budget:
        return sells + buys

    # Consume existing cash in opportunity order, then raise only enough for the
    # next preferred buy. Lower-ranked target gaps are future demand, not today's
    # funding requirement.
    remaining_for_ranked_buys = available_budget
    funded_prefix: list[TradeRecommendation] = []
    deficit = 0.0
    for buy in buys:
        full_cost = buy.value_delta_eur + calculate_transaction_cost(buy.value_delta_eur, fixed_fee, pct_fee)
        funded_prefix.append(buy)
        if full_cost <= remaining_for_ranked_buys:
            remaining_for_ranked_buys -= full_cost
            continue
        deficit = full_cost - remaining_for_ranked_buys
        break

    # If budget is short, rotate out weakest holdings to fund that selected demand.
    if deficit > 0:
        reserve_shortfall = max(0.0, cash_reserve - current_cash - net_sell_proceeds)
        buy_conviction_cap = max(
            (conviction_by_symbol.get(b.symbol, 0.5) for b in funded_prefix),
            default=0.5,
        )
        funding_sells = await engine._generate_deficit_sells(
            deficit + reserve_shortfall + engine.BALANCE_BUFFER_EUR,
            as_of_date=as_of_date,
            ideal=ideal,
            current=current,
            total_value=total_value,
            planning_total_value=planning_total_value,
            reason_kind="funding_rotation",
            max_sell_conviction=buy_conviction_cap,
            preloaded_positions=preloaded_positions,
            preloaded_securities_map=preloaded_securities_map,
            preloaded_symbol_scores=preloaded_symbol_scores,
            preloaded_symbol_prices=preloaded_symbol_prices,
            eligible_symbols=eligible_symbols,
            state=state,
        )
        if funding_sells:
            max_sells = int(await _setting(engine, "strategy_max_funding_sells_per_cycle", 2))
            max_turnover_pct = float(await _setting(engine, "strategy_max_funding_turnover_pct", 0.12))
            if max_sells >= 0:
                funding_sells = funding_sells[:max_sells]

            if total_value is None or total_value <= 0:
                if as_of_date is None:
                    total_value = await engine._portfolio.total_value()
            if total_value and total_value > 0 and max_turnover_pct > 0:
                max_turnover_value = total_value * max_turnover_pct
                running = 0.0
                capped: list[TradeRecommendation] = []
                for sell in funding_sells:
                    sell_value = abs(float(sell.value_delta_eur))
                    if not capped or (running + sell_value) <= max_turnover_value:
                        capped.append(sell)
                        running += sell_value
                funding_sells = capped

            existing_sell_symbols = {s.symbol for s in sells}
            new_sells = [s for s in funding_sells if s.symbol not in existing_sell_symbols]
            if new_sells:
                sells.extend(new_sells)
                net_sell_proceeds = sum(
                    abs(r.value_delta_eur) - calculate_transaction_cost(abs(r.value_delta_eur), fixed_fee, pct_fee)
                    for r in sells
                )
                available_budget = max(0.0, current_cash + net_sell_proceeds - cash_reserve)
                total_buy_costs = sum(
                    r.value_delta_eur + calculate_transaction_cost(r.value_delta_eur, fixed_fee, pct_fee) for r in buys
                )
                if total_buy_costs <= available_budget:
                    return sells + buys

    # Waterfall allocation: fully fund the highest-priority projected gap before
    # moving to the next one. Unreached buys are simply the tail of the ranked plan.
    final_buys: list[TradeRecommendation] = []
    remaining_budget = available_budget
    for buy in buys:
        one_lot_eur = await _one_lot_value_eur(engine, buy, fx_rates)
        if one_lot_eur <= 0:
            continue

        cost_for_full_buy = buy.value_delta_eur + calculate_transaction_cost(buy.value_delta_eur, fixed_fee, pct_fee)
        desired_eur = buy.value_delta_eur if cost_for_full_buy <= remaining_budget else remaining_budget / (1 + pct_fee)
        qty, actual_eur = await _value_to_quantity(engine, buy, desired_eur, fx_rates)
        if qty < buy.lot_size or actual_eur < min_trade_value:
            continue

        cost = actual_eur + calculate_transaction_cost(actual_eur, fixed_fee, pct_fee)
        if cost > remaining_budget:
            continue

        final_buys.append(replace(buy, value_delta_eur=actual_eur, quantity=qty))
        remaining_budget -= cost

    final_buys.sort(key=buy_rank_key)
    if not final_buys:
        # Funding rotations exist only to support selected demand. Mandatory
        # lifecycle/deficit sells supplied by the caller remain independent.
        return base_sells
    return sells + final_buys


async def get_deficit_sells(
    *,
    engine: "RebalanceEngine",
    as_of_date: str | None = None,
    ideal: dict[str, float] | None = None,
    current: dict[str, float] | None = None,
    total_value: float | None = None,
    planning_total_value: float | None = None,
    eligible_symbols: set[str] | None = None,
    state: PlannerState | None = None,
) -> list[TradeRecommendation]:
    """Generate sell recommendations if negative balances can't be covered."""
    balances = await engine._get_cash_balances_for_context(as_of_date=as_of_date, state=state)

    total_deficit_eur = 0.0
    for currency, amount in balances.items():
        if amount < 0:
            if currency == "EUR":
                total_deficit_eur += abs(amount) + engine.BALANCE_BUFFER_EUR
            else:
                total_deficit_eur += await engine._currency.to_eur(abs(amount), currency) + engine.BALANCE_BUFFER_EUR

    if total_deficit_eur == 0:
        return []

    total_positive_eur = 0.0
    for currency, amount in balances.items():
        if amount > 0:
            total_positive_eur += await engine._currency.to_eur(amount, currency)

    uncovered_deficit = total_deficit_eur - total_positive_eur
    if uncovered_deficit <= 0:
        return []

    return await generate_deficit_sells(
        engine=engine,
        deficit_eur=uncovered_deficit,
        as_of_date=as_of_date,
        ideal=ideal,
        current=current,
        total_value=total_value,
        planning_total_value=planning_total_value,
        reason_kind="cash_deficit",
        eligible_symbols=eligible_symbols,
        state=state,
    )


async def generate_deficit_sells(
    *,
    engine: "RebalanceEngine",
    deficit_eur: float,
    as_of_date: str | None = None,
    ideal: dict[str, float] | None = None,
    current: dict[str, float] | None = None,
    total_value: float | None = None,
    planning_total_value: float | None = None,
    reason_kind: str = "cash_deficit",
    max_sell_conviction: float | None = None,
    preloaded_positions: list[dict] | None = None,
    preloaded_securities_map: dict[str, dict] | None = None,
    preloaded_symbol_scores: dict[str, float] | None = None,
    preloaded_symbol_prices: dict[str, float] | None = None,
    eligible_symbols: set[str] | None = None,
    state: PlannerState | None = None,
) -> list[TradeRecommendation]:
    """Generate sell recommendations to cover remaining deficit."""
    sells: list[TradeRecommendation] = []
    remaining_deficit = deficit_eur

    if preloaded_securities_map is not None:
        securities_map = preloaded_securities_map
    else:
        all_securities = await engine._db.get_all_securities(active_only=False)
        securities_map = {s["symbol"]: s for s in all_securities}

    if preloaded_positions is not None:
        positions = preloaded_positions
    else:
        positions = await engine._get_positions_for_context(
            as_of_date=as_of_date,
            securities_map=securities_map,
            state=state,
        )
    if not positions:
        return sells

    position_data = []
    conviction_bias = float(await _setting(engine, "strategy_funding_conviction_bias", 1.0))
    for pos in positions:
        symbol = pos["symbol"]
        if eligible_symbols is not None and symbol not in eligible_symbols:
            continue
        qty = pos.get("quantity", 0)
        if qty <= 0:
            continue

        price = pos.get("current_price", 0)
        if preloaded_symbol_prices is not None and symbol in preloaded_symbol_prices:
            price = preloaded_symbol_prices[symbol]
        elif as_of_date is not None:
            hist = await engine._db.get_prices(symbol, days=1, end_date=as_of_date)
            if hist:
                close = hist[0].get("close")
                if close is not None:
                    try:
                        price = float(close)
                    except (TypeError, ValueError):
                        price = 0

        if price <= 0:
            continue

        sec = securities_map.get(symbol)
        if not sec:
            continue

        if not sec.get("allow_sell", 1):
            continue

        currency = sec.get("currency", "EUR")
        lot_size = sec.get("min_lot", 1)
        if preloaded_symbol_scores is not None and symbol in preloaded_symbol_scores:
            score = float(preloaded_symbol_scores[symbol])
        else:
            hist = await engine._db.get_prices(symbol, days=250, end_date=as_of_date)
            closes = [float(r["close"]) for r in reversed(hist) if r.get("close") is not None]
            score = float(compute_contrarian_signal(closes).get("opp_score", 0.0))

        local_value = qty * price
        eur_value = await engine._currency.to_eur(local_value, currency)
        # The stored slider value IS the conviction now — the weekly decay
        # job has already faded historical ratings, no read-time correction.
        conviction = max(0.0, min(1.0, float(normalize_user_multiplier(sec.get("user_multiplier", 0.5)))))

        curr_alloc = float((current or {}).get(symbol, 0.0))
        tgt_alloc = float((ideal or {}).get(symbol, 0.0))
        planning_value = (
            float(planning_total_value)
            if planning_total_value is not None and planning_total_value > 0
            else float(total_value or 0.0)
        )
        projected_target_value = tgt_alloc * planning_value if planning_value > 0 else 0.0
        overweight_value = max(0.0, eur_value - projected_target_value)
        overweight = (overweight_value / planning_value) if planning_value > 0 else max(0.0, curr_alloc - tgt_alloc)

        position_data.append(
            {
                "symbol": symbol,
                "quantity": qty,
                "price": price,
                "currency": currency,
                "lot_size": lot_size,
                "score": score,
                "eur_value": eur_value,
                "target_allocation": tgt_alloc,
                "current_allocation": curr_alloc,
                "overweight": overweight,
                "overweight_value": overweight_value,
                "conviction": conviction,
                # Deliberately rated <= 0.5 → "done with this name": preferred
                # funding source, sold first and never shielded by the cap below.
                "is_downgrade": is_explicit_downgrade(sec),
            }
        )

    if max_sell_conviction is not None:
        cap = max(0.0, min(1.0, float(max_sell_conviction)))
        # Explicitly-downgraded names stay eligible even if their (stale) conviction
        # sits above the cap — a name we've decided to exit is always fundable.
        limited = [p for p in position_data if float(p["conviction"]) <= cap or p["is_downgrade"]]
        # If nothing is eligible under cap, do not force higher-conviction sells for low-conviction buys.
        if reason_kind == "funding_rotation" and not limited:
            return sells
        if limited:
            position_data = limited

    if reason_kind == "funding_rotation":
        position_data.sort(
            key=lambda x: (
                # Downgraded names are the piggy bank: drain them first.
                0 if x["is_downgrade"] else 1,
                -x["overweight"],
                (x["conviction"] * x["conviction"]) * conviction_bias,
                x["score"],
                x["eur_value"],
            )
        )
    else:
        position_data.sort(key=lambda x: (x["score"], x["eur_value"]))
    if total_value is not None and total_value > 0:
        total_value = float(total_value)
    elif as_of_date is not None:
        total_value = 0.0
        cash_balances = await engine._get_cash_balances_for_context(as_of_date=as_of_date, state=state)
        total_value += float(cash_balances.get("EUR", 0.0))
        total_value += sum(float(p["eur_value"]) for p in position_data)
    else:
        total_value = await engine._portfolio.total_value()

    # Cool-off gating for funding-rotation sells only.
    #
    # This path builds sells directly and historically skipped the cool-off
    # check the main recommendation path enforces, letting the engine sell names
    # it had just bought to fund new buys (churn). Funding-rotation sells raise
    # cash for *optional* buys, so a name still inside its cool-off window is not
    # a good sell: we drop it and simply buy less. We never demote it to a
    # fallback tier — selling a good holding to satisfy a cash constraint is
    # itself a bad trade. If nothing eligible remains, we make no trade and let a
    # later cycle act once the window expires.
    #
    # Negative-balance repair (reason_kind="cash_deficit") is the one exception
    # and is intentionally NOT gated here: a real negative cash balance accrues
    # margin interest and must be covered. (Currency-only deficits are handled
    # upstream by the trading:balance_fix FX-conversion job; this path only sells
    # securities when an FX conversion can't cover the shortfall.)
    #
    # The *core* window is used as the opposite-side bound (rather than per-sleeve):
    # it's the more conservative of the configured windows, and over-blocking only
    # ever means "trade less", never a bad trade. The same-side window guards
    # re-selling a name we recently sold, matching the main-path policy.
    if reason_kind == "funding_rotation":
        cooloff_days = int(await _setting(engine, "strategy_core_cooloff_days", 21))
        same_side_cooloff_days = int(await _setting(engine, "strategy_same_side_cooloff_days", 15))
        if position_data and (cooloff_days > 0 or same_side_cooloff_days > 0):
            latest_trades = await _load_latest_trades(engine, [p["symbol"] for p in position_data])
            blocked_symbols: set[str] = set()
            for pos in position_data:
                is_blocked, _ = await engine._check_cooloff_violation(
                    pos["symbol"],
                    "sell",
                    cooloff_days,
                    same_side_cooloff_days=same_side_cooloff_days,
                    latest_trade=latest_trades.get(pos["symbol"]),
                    as_of_date=as_of_date,
                )
                if is_blocked:
                    blocked_symbols.add(pos["symbol"])
            if blocked_symbols:
                position_data = [p for p in position_data if p["symbol"] not in blocked_symbols]
                logger.debug(
                    "Cool-off suppressed %d funding-rotation sell candidate(s): %s",
                    len(blocked_symbols),
                    sorted(blocked_symbols),
                )

    for pos in position_data:
        if remaining_deficit <= 0:
            break

        symbol = pos["symbol"]
        qty = pos["quantity"]
        price = pos["price"]
        currency = pos["currency"]
        lot_size = pos["lot_size"]
        eur_value = pos["eur_value"]
        score = pos["score"]

        # Calculate how much we're overweight vs the projected target value.
        current_alloc = eur_value / total_value if total_value > 0 else float(pos["current_allocation"])
        target_alloc = float(pos["target_allocation"])
        overweight_value = float(pos.get("overweight_value", 0.0) or 0.0)
        if overweight_value <= 0 and planning_total_value is None:
            overweight_pct = max(0.0, current_alloc - target_alloc)
            overweight_value = overweight_pct * total_value

        # Only skip non-overweight positions for funding_rotation
        # For cash_deficit, we must sell even if not overweight to cover the deficit
        if overweight_value <= 0:
            if reason_kind == "funding_rotation":
                continue  # Skip if not overweight for funding_rotation

        if overweight_value <= remaining_deficit:
            # Sell entire overweight amount
            rate = await engine._currency.get_rate(currency)
            if currency != "EUR" and rate > 0:
                overweight_qty = overweight_value / (price * rate)
            else:
                overweight_qty = overweight_value / price
            sell_qty = (int(overweight_qty) // lot_size) * lot_size
        else:
            # Sell only what's needed to cover the deficit
            rate = await engine._currency.get_rate(currency)
            if rate > 0:
                local_needed = remaining_deficit / rate
            else:
                local_needed = remaining_deficit
            shares_needed = local_needed / price
            sell_qty = math.ceil(shares_needed / lot_size) * lot_size

        sell_qty = min(sell_qty, qty)

        if sell_qty < lot_size:
            continue

        target_alloc = float(pos["target_allocation"])
        sell_value_local = sell_qty * price
        sell_value_eur = await engine._currency.to_eur(sell_value_local, currency)
        next_target_value = max(0.0, eur_value - sell_value_eur)
        if total_value > 0:
            target_alloc = max(0.0, next_target_value / total_value)

        if reason_kind == "funding_rotation":
            reason = f"Sell to fund higher-priority buys ({remaining_deficit:.0f} EUR funding gap)"
            reason_code = "funding_rotation_sell"
        else:
            reason = f"Sell to repair negative cash balance ({remaining_deficit:.0f} EUR gap)"
            reason_code = "cash_deficit_repair"

        sells.append(
            TradeRecommendation(
                symbol=symbol,
                action="sell",
                current_allocation=current_alloc,
                target_allocation=target_alloc,
                allocation_delta=target_alloc - current_alloc,
                current_value_eur=eur_value,
                target_value_eur=next_target_value,
                value_delta_eur=-sell_value_eur,
                quantity=sell_qty,
                price=price,
                currency=currency,
                lot_size=lot_size,
                contrarian_score=score,
                priority=1000,
                reason=reason,
                reason_code=reason_code,
                sleeve="core",
            )
        )

        remaining_deficit -= sell_value_eur

    return sells
