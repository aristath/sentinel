"""Deterministic contrarian strategy helpers."""

from __future__ import annotations

import math


def _clip(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(var)


def recent_dd252_min(closes_oldest_first: list[float], window_days: int = 42) -> float:
    """Return minimum rolling-252 drawdown observed in the recent lookback window."""
    if not closes_oldest_first:
        return 0.0
    closes = closes_oldest_first
    start_idx = max(0, len(closes) - max(1, window_days))
    mins: list[float] = []
    for i in range(start_idx, len(closes)):
        roll_start = max(0, i - 251)
        roll_max_i = max(closes[roll_start : i + 1])
        dd_i = (closes[i] / roll_max_i - 1.0) if roll_max_i > 0 else 0.0
        mins.append(dd_i)
    return min(mins) if mins else 0.0


def effective_opportunity_score(
    *,
    raw_opp_score: float,
    cycle_turn: int,
    freefall_block: int,
    recent_dd252_min_value: float,
    entry_t1_dd: float,
    entry_t3_dd: float,
    max_boost: float,
) -> float:
    """Apply guarded event-memory boost to opportunity score."""
    raw = _clip(raw_opp_score, 0.0, 1.0)
    if freefall_block == 1 or cycle_turn != 1:
        return raw
    if recent_dd252_min_value > entry_t1_dd:
        return raw

    depth_den = max(1e-9, abs(entry_t3_dd - entry_t1_dd))
    depth = _clip((abs(recent_dd252_min_value) - abs(entry_t1_dd)) / depth_den, 0.0, 1.0)
    boost = max_boost * (0.4 + 0.6 * depth)
    return _clip(raw + boost, 0.0, 1.0)


def _rsi14(closes: list[float]) -> float:
    if len(closes) < 15:
        return 50.0
    gains: list[float] = []
    losses: list[float] = []
    for i in range(len(closes) - 14, len(closes)):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-delta)
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    if avg_loss <= 1e-12:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def compute_contrarian_signal(closes_oldest_first: list[float]) -> dict[str, float | int]:
    """Compute deterministic contrarian metrics from close series."""
    if len(closes_oldest_first) < 130:
        return {
            "dd252": 0.0,
            "dd252_recent_min": 0.0,
            "rsi14": 50.0,
            "mom20": 0.0,
            "mom60": 0.0,
            "mom120": 0.0,
            "vol20": 0.0,
            "vol_ratio": 1.0,
            "dip_score": 0.0,
            "capitulation_score": 0.0,
            "cycle_turn": 0,
            "freefall_block": 0,
            "opp_score": 0.0,
            "core_rank": 0.0,
        }

    closes = closes_oldest_first
    last = closes[-1]
    rolling = closes[-252:] if len(closes) >= 252 else closes
    rolling_max = max(rolling) if rolling else last
    dd252 = (last / rolling_max - 1.0) if rolling_max > 0 else 0.0
    dd252_recent_min = recent_dd252_min(closes, window_days=42)
    rsi14 = _rsi14(closes)
    mom20 = last / closes[-21] - 1.0 if closes[-21] > 0 else 0.0
    mom60 = last / closes[-61] - 1.0 if closes[-61] > 0 else 0.0
    mom120 = last / closes[-121] - 1.0 if closes[-121] > 0 else 0.0

    returns = [
        math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0 and closes[i] > 0
    ]
    vol20 = _stdev(returns[-20:]) if len(returns) >= 20 else 0.0
    vol120 = _stdev(returns[-120:]) if len(returns) >= 120 else (vol20 if vol20 > 0 else 1e-9)
    vol_ratio = vol20 / max(vol120, 1e-9)

    dip = _clip((abs(dd252) - 0.12) / 0.23, 0.0, 1.0)
    cap = _clip((30.0 - rsi14) / 20.0, 0.0, 1.0)
    turn = 1 if mom20 > mom60 and mom20 > -0.02 else 0
    block = 1 if mom20 < -0.12 and vol_ratio > 1.5 else 0
    opp = 0.5 * dip + 0.3 * cap + 0.2 * turn
    if block:
        opp = 0.0

    core_rank = mom120 - (0.5 * vol20)
    return {
        "dd252": dd252,
        "dd252_recent_min": dd252_recent_min,
        "rsi14": rsi14,
        "mom20": mom20,
        "mom60": mom60,
        "mom120": mom120,
        "vol20": vol20,
        "vol_ratio": vol_ratio,
        "dip_score": dip,
        "capitulation_score": cap,
        "cycle_turn": turn,
        "freefall_block": block,
        "opp_score": _clip(opp, 0.0, 1.0),
        "core_rank": core_rank,
    }


def classify_lot_size(
    *,
    price: float,
    lot_size: int,
    fx_rate_to_eur: float,
    portfolio_value_eur: float,
    fee_fixed_eur: float,
    fee_pct: float,
    standard_max_pct: float,
    coarse_max_pct: float,
) -> dict[str, float | str]:
    """Classify a symbol's minimum tradable ticket for small-portfolio sizing."""
    one_lot_local = max(0.0, float(lot_size) * float(price))
    one_lot_eur = one_lot_local * max(fx_rate_to_eur, 0.0)
    min_ticket_eur = one_lot_eur + max(0.0, fee_fixed_eur) + (one_lot_eur * max(0.0, fee_pct))
    if portfolio_value_eur <= 0:
        ticket_pct = 1.0
    else:
        ticket_pct = min_ticket_eur / portfolio_value_eur
    if ticket_pct <= standard_max_pct:
        lot_class = "standard"
    elif ticket_pct <= coarse_max_pct:
        lot_class = "coarse"
    else:
        lot_class = "jumbo"
    return {
        "min_ticket_eur": min_ticket_eur,
        "ticket_pct": ticket_pct,
        "lot_class": lot_class,
    }


def compute_symbol_targets(
    symbol_signals: dict[str, dict[str, float | int]],
    user_multipliers: dict[str, float],
    *,
    core_target: float,
    opportunity_target: float,
    min_opp_score: float,
    max_opportunity_target: float | None = None,
) -> tuple[dict[str, float], dict[str, str]]:
    """Build target allocations and sleeve mapping from deterministic signals.

    `user_multipliers` are caller-provided preference weights derived from conviction.
    """
    core_candidates = {}
    opp_candidates = {}

    for symbol, metrics in symbol_signals.items():
        multiplier = max(0.0, float(user_multipliers.get(symbol, 1.0)))
        if multiplier <= 0:
            continue
        core_rank = float(metrics.get("core_rank", 0.0))
        opp_score = float(metrics.get("opp_score", 0.0))
        vol20 = max(float(metrics.get("vol20", 0.0)), 1e-6)
        core_candidates[symbol] = max(0.001, core_rank + 1.0) * multiplier
        if opp_score >= min_opp_score:
            opp_candidates[symbol] = (opp_score / vol20) * multiplier

    if not core_candidates and not opp_candidates:
        return {}, {}

    if max_opportunity_target is None:
        max_opportunity_target = opportunity_target
    max_opportunity_target = _clip(max_opportunity_target, opportunity_target, 1.0)

    effective_opportunity_target = opportunity_target
    if opp_candidates and max_opportunity_target > opportunity_target:
        breadth = _clip(len(opp_candidates) / 8.0, 0.0, 1.0)
        avg_opp = sum(float(symbol_signals[s].get("opp_score", 0.0)) for s in opp_candidates) / len(opp_candidates)
        strength = _clip((avg_opp - min_opp_score) / max(1e-9, (1.0 - min_opp_score)), 0.0, 1.0)
        boost = (0.5 * breadth) + (0.5 * strength)
        effective_opportunity_target = opportunity_target + ((max_opportunity_target - opportunity_target) * boost)

    effective_core_target = max(0.0, 1.0 - effective_opportunity_target)

    allocations: dict[str, float] = {}
    sleeves: dict[str, str] = {}

    # Core sleeve
    core_weight_sum = sum(core_candidates.values())
    if core_weight_sum > 0:
        for symbol, weight in core_candidates.items():
            allocations[symbol] = allocations.get(symbol, 0.0) + (weight / core_weight_sum) * effective_core_target
            sleeves.setdefault(symbol, "core")

    # Opportunity sleeve
    opp_weight_sum = sum(opp_candidates.values())
    if opp_weight_sum > 0:
        for symbol, weight in opp_candidates.items():
            allocations[symbol] = allocations.get(symbol, 0.0) + (
                (weight / opp_weight_sum) * effective_opportunity_target
            )
            sleeves[symbol] = "opportunity"
    else:
        # Keep portfolio fully invested if no tactical candidates
        core_weight_sum = sum(core_candidates.values())
        if core_weight_sum > 0:
            for symbol, weight in core_candidates.items():
                allocations[symbol] = weight / core_weight_sum

    total = sum(allocations.values())
    if total <= 0:
        return {}, {}
    allocations = {symbol: value / total for symbol, value in allocations.items() if value > 0}
    return allocations, sleeves
