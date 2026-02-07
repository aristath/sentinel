"""Cash-constraint and deficit-funding helpers for the rebalance engine."""

from __future__ import annotations

import inspect
import math
from typing import TYPE_CHECKING

from sentinel.strategy import compute_contrarian_signal

from .models import TradeRecommendation
from .rebalance_rules import calculate_transaction_cost

if TYPE_CHECKING:
    from .rebalance import RebalanceEngine


async def _setting(engine: "RebalanceEngine", key: str, default: float | int) -> float | int:
    """Read setting with safe fallback for mocked/unit-test engines."""
    try:
        value = await engine._settings.get(key, default)
    except Exception:
        return default
    return default if value is None else value


async def apply_cash_constraint(
    *,
    engine: "RebalanceEngine",
    recommendations: list[TradeRecommendation],
    min_trade_value: float,
    as_of_date: str | None = None,
    ideal: dict[str, float] | None = None,
    current: dict[str, float] | None = None,
    total_value: float | None = None,
    symbol_convictions: dict[str, float] | None = None,
) -> list[TradeRecommendation]:
    """Scale down buy recommendations to fit within available cash."""
    fixed_fee = await engine._settings.get("transaction_fee_fixed", 2.0)
    pct_fee = await engine._settings.get("transaction_fee_percent", 0.2) / 100

    sells = [r for r in recommendations if r.action == "sell"]
    buys = [r for r in recommendations if r.action == "buy"]

    if not buys:
        return recommendations

    # Calculate available budget
    current_cash = await engine._portfolio.total_cash_eur()
    net_sell_proceeds = sum(
        abs(r.value_delta_eur) - calculate_transaction_cost(abs(r.value_delta_eur), fixed_fee, pct_fee) for r in sells
    )
    available_budget = current_cash + net_sell_proceeds

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
                s["symbol"]: max(0.0, min(1.0, float(s.get("user_multiplier", 0.5) or 0.5))) for s in all_securities
            }
    if total_buy_costs > available_budget and len(buys) > 1:
        buy_rank = []
        for buy in buys:
            conviction = conviction_by_symbol.get(buy.symbol, 0.5)
            rank = float(buy.priority) * (0.5 + conviction)
            buy_rank.append((buy, conviction, rank))
        sorted_by_rank = sorted(buy_rank, key=lambda x: x[2])
        ranks = [r for _, _, r in sorted_by_rank]
        median_rank = ranks[len(ranks) // 2]
        trimmed_symbols: set[str] = set()
        running_cost = total_buy_costs
        for buy, _, rank in sorted_by_rank:
            if running_cost <= available_budget:
                break
            if rank >= median_rank:
                continue
            trimmed_symbols.add(buy.symbol)
            running_cost -= buy.value_delta_eur + calculate_transaction_cost(buy.value_delta_eur, fixed_fee, pct_fee)

        if trimmed_symbols:
            buys = [b for b in buys if b.symbol not in trimmed_symbols]
            recommendations = [r for r in recommendations if not (r.action == "buy" and r.symbol in trimmed_symbols)]
            total_buy_costs = sum(
                r.value_delta_eur + calculate_transaction_cost(r.value_delta_eur, fixed_fee, pct_fee) for r in buys
            )

    if not buys:
        return sells

    if total_buy_costs <= available_budget:
        return sells + buys

    # If budget is short, rotate out weakest holdings to fund high-priority buys.
    deficit = total_buy_costs - available_budget
    if deficit > 0:
        buy_conviction_cap = max((conviction_by_symbol.get(b.symbol, 0.5) for b in buys), default=0.5)
        funding_sells = await engine._generate_deficit_sells(
            deficit + engine.BALANCE_BUFFER_EUR,
            as_of_date=as_of_date,
            ideal=ideal,
            current=current,
            total_value=total_value,
            reason_kind="funding_rotation",
            max_sell_conviction=buy_conviction_cap,
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
                recommendations = [
                    r for r in recommendations if not (r.action == "sell" and r.symbol in existing_sell_symbols)
                ]
                recommendations = new_sells + recommendations
                net_sell_proceeds = sum(
                    abs(r.value_delta_eur) - calculate_transaction_cost(abs(r.value_delta_eur), fixed_fee, pct_fee)
                    for r in sells
                )
                available_budget = current_cash + net_sell_proceeds
                total_buy_costs = sum(
                    r.value_delta_eur + calculate_transaction_cost(r.value_delta_eur, fixed_fee, pct_fee) for r in buys
                )
                if total_buy_costs <= available_budget:
                    return recommendations

    # Scale down buys
    buys_by_priority = sorted(buys, key=lambda x: -x.priority)
    remaining_budget = available_budget

    buy_minimums = []
    for buy in buys_by_priority:
        one_lot_local = buy.lot_size * buy.price
        if buy.currency != "EUR":
            one_lot_eur = await engine._currency.to_eur(one_lot_local, buy.currency)
        else:
            one_lot_eur = one_lot_local

        if one_lot_eur >= min_trade_value:
            min_qty = buy.lot_size
            min_eur = one_lot_eur
        elif one_lot_eur <= 0:
            continue
        else:
            lots_needed = int(min_trade_value / one_lot_eur) + 1
            min_qty = lots_needed * buy.lot_size
            min_eur = lots_needed * one_lot_eur

        if min_qty > buy.quantity:
            min_qty = buy.quantity
            min_local_value = min_qty * buy.price
            if buy.currency != "EUR":
                min_eur = await engine._currency.to_eur(min_local_value, buy.currency)
            else:
                min_eur = min_local_value

        min_cost_with_tx = min_eur + calculate_transaction_cost(min_eur, fixed_fee, pct_fee)
        ideal_cost_with_tx = buy.value_delta_eur + calculate_transaction_cost(buy.value_delta_eur, fixed_fee, pct_fee)
        buy_minimums.append(
            {
                "buy": buy,
                "min_qty": min_qty,
                "min_eur": min_eur,
                "min_cost": min_cost_with_tx,
                "ideal_eur": buy.value_delta_eur,
                "ideal_cost": ideal_cost_with_tx,
            }
        )

    included_buys = []
    for item in buy_minimums:
        if item["min_cost"] <= remaining_budget:
            included_buys.append(item)
            remaining_budget -= item["min_cost"]

    if not included_buys:
        return sells

    # Distribute remaining budget proportionally
    total_extra_needed = sum(max(0, item["ideal_cost"] - item["min_cost"]) for item in included_buys)

    final_buys = []
    for item in included_buys:
        buy = item["buy"]
        min_eur = item["min_eur"]
        ideal_cost = item["ideal_cost"]
        allocated_eur = min_eur

        if total_extra_needed > 0 and remaining_budget > 0:
            extra_needed = max(0, ideal_cost - item["min_cost"])
            proportion = extra_needed / total_extra_needed
            extra_budget = proportion * remaining_budget
            extra_trade_value = extra_budget / (1 + pct_fee)
            allocated_eur += extra_trade_value

        # Convert back to quantity
        if buy.currency != "EUR":
            rate = await engine._currency.get_rate(buy.currency)
            local_value = allocated_eur / rate if rate > 0 else allocated_eur
        else:
            local_value = allocated_eur

        raw_qty = local_value / buy.price
        rounded_qty = (int(raw_qty) // buy.lot_size) * buy.lot_size

        if rounded_qty < buy.lot_size:
            continue

        actual_local = rounded_qty * buy.price
        if buy.currency != "EUR":
            actual_eur = await engine._currency.to_eur(actual_local, buy.currency)
        else:
            actual_eur = actual_local

        if actual_eur < min_trade_value:
            continue

        final_buys.append(
            TradeRecommendation(
                symbol=buy.symbol,
                action="buy",
                current_allocation=buy.current_allocation,
                target_allocation=buy.target_allocation,
                allocation_delta=buy.allocation_delta,
                current_value_eur=buy.current_value_eur,
                target_value_eur=buy.target_value_eur,
                value_delta_eur=actual_eur,
                quantity=rounded_qty,
                price=buy.price,
                currency=buy.currency,
                lot_size=buy.lot_size,
                contrarian_score=buy.contrarian_score,
                priority=buy.priority,
                reason=buy.reason,
                reason_code=buy.reason_code,
                sleeve=buy.sleeve,
                lot_class=buy.lot_class,
                ticket_pct=buy.ticket_pct,
                core_floor_active=buy.core_floor_active,
            )
        )

    final_buys.sort(key=lambda x: -x.priority)

    # Top-up with leftover budget
    total_buy_cost = sum(
        b.value_delta_eur + calculate_transaction_cost(b.value_delta_eur, fixed_fee, pct_fee) for b in final_buys
    )
    leftover = available_budget - total_buy_cost

    iterations = 0
    while leftover > 0 and iterations < 1000:
        iterations += 1
        added_any = False
        for i, buy in enumerate(final_buys):
            one_lot_local = buy.lot_size * buy.price
            if buy.currency != "EUR":
                one_lot_eur = await engine._currency.to_eur(one_lot_local, buy.currency)
            else:
                one_lot_eur = one_lot_local
            one_lot_cost = one_lot_eur + calculate_transaction_cost(one_lot_eur, fixed_fee, pct_fee)

            if one_lot_cost <= leftover:
                new_qty = buy.quantity + buy.lot_size
                new_local_value = new_qty * buy.price
                if buy.currency != "EUR":
                    new_eur = await engine._currency.to_eur(new_local_value, buy.currency)
                else:
                    new_eur = new_local_value

                final_buys[i] = TradeRecommendation(
                    symbol=buy.symbol,
                    action="buy",
                    current_allocation=buy.current_allocation,
                    target_allocation=buy.target_allocation,
                    allocation_delta=buy.allocation_delta,
                    current_value_eur=buy.current_value_eur,
                    target_value_eur=buy.target_value_eur,
                    value_delta_eur=new_eur,
                    quantity=new_qty,
                    price=buy.price,
                    currency=buy.currency,
                    lot_size=buy.lot_size,
                    contrarian_score=buy.contrarian_score,
                    priority=buy.priority,
                    reason=buy.reason,
                    reason_code=buy.reason_code,
                    sleeve=buy.sleeve,
                    lot_class=buy.lot_class,
                    ticket_pct=buy.ticket_pct,
                    core_floor_active=buy.core_floor_active,
                )
                leftover -= one_lot_cost
                added_any = True

        if not added_any:
            break

    return sells + final_buys


async def get_deficit_sells(
    *,
    engine: "RebalanceEngine",
    as_of_date: str | None = None,
    ideal: dict[str, float] | None = None,
    current: dict[str, float] | None = None,
    total_value: float | None = None,
) -> list[TradeRecommendation]:
    """Generate sell recommendations if negative balances can't be covered."""
    balances = await engine._get_cash_balances_for_context(as_of_date=as_of_date)

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
        reason_kind="cash_deficit",
    )


async def generate_deficit_sells(
    *,
    engine: "RebalanceEngine",
    deficit_eur: float,
    as_of_date: str | None = None,
    ideal: dict[str, float] | None = None,
    current: dict[str, float] | None = None,
    total_value: float | None = None,
    reason_kind: str = "cash_deficit",
    max_sell_conviction: float | None = None,
) -> list[TradeRecommendation]:
    """Generate sell recommendations to cover remaining deficit."""
    sells: list[TradeRecommendation] = []
    remaining_deficit = deficit_eur

    all_securities = await engine._db.get_all_securities(active_only=False)
    securities_map = {s["symbol"]: s for s in all_securities}
    positions = await engine._get_positions_for_context(as_of_date=as_of_date, securities_map=securities_map)
    if not positions:
        return sells

    position_data = []
    conviction_bias = float(await _setting(engine, "strategy_funding_conviction_bias", 1.0))
    for pos in positions:
        symbol = pos["symbol"]
        qty = pos.get("quantity", 0)
        if qty <= 0:
            continue

        price = pos.get("current_price", 0)
        if as_of_date is not None:
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
        hist = await engine._db.get_prices(symbol, days=250, end_date=as_of_date)
        closes = [float(r["close"]) for r in reversed(hist) if r.get("close") is not None]
        score = float(compute_contrarian_signal(closes).get("opp_score", 0.0))

        local_value = qty * price
        eur_value = await engine._currency.to_eur(local_value, currency)
        conviction = max(0.0, min(1.0, float(sec.get("user_multiplier", 0.5) or 0.5)))

        curr_alloc = float((current or {}).get(symbol, 0.0))
        tgt_alloc = float((ideal or {}).get(symbol, 0.0))
        overweight = max(0.0, curr_alloc - tgt_alloc)

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
                "conviction": conviction,
            }
        )

    if max_sell_conviction is not None:
        cap = max(0.0, min(1.0, float(max_sell_conviction)))
        limited = [p for p in position_data if float(p["conviction"]) <= cap]
        # If nothing is eligible under cap, do not force higher-conviction sells for low-conviction buys.
        if reason_kind == "funding_rotation" and not limited:
            return sells
        if limited:
            position_data = limited

    if reason_kind == "funding_rotation":
        position_data.sort(
            key=lambda x: (
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
        cash_balances = await engine._get_cash_balances_for_context(as_of_date=as_of_date)
        total_value += float(cash_balances.get("EUR", 0.0))
        total_value += sum(float(p["eur_value"]) for p in position_data)
    else:
        total_value = await engine._portfolio.total_value()

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

        if eur_value <= remaining_deficit:
            sell_qty = (qty // lot_size) * lot_size
        else:
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

        current_alloc = eur_value / total_value if total_value > 0 else float(pos["current_allocation"])
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
