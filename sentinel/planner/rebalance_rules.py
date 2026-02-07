"""Pure rule helpers for the deterministic rebalance engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def desired_tranche_stage(dd252: float, t1: float = -0.12, t2: float = -0.20, t3: float = -0.28) -> int:
    """Map drawdown value to target tranche stage (0..3)."""
    if dd252 <= t3:
        return 3
    if dd252 <= t2:
        return 2
    if dd252 <= t1:
        return 1
    return 0


def get_forced_opportunity_exit(
    *,
    signal: dict[str, float | int | str],
    state: dict[str, Any],
    current_qty: int,
    price: float,
    avg_cost: float,
    as_of_date: str | None,
    time_stop_days: int,
) -> dict[str, Any] | None:
    """Evaluate opportunity exit/rotation rules and return forced sell spec if triggered."""
    if current_qty <= 0:
        return None

    entry_price = float(avg_cost or 0) or float(state.get("last_entry_price", 0) or 0) or price
    if entry_price <= 0 or price <= 0:
        return None

    gain = (price / entry_price) - 1.0
    scaleout_stage = int(state.get("scaleout_stage", 0) or 0)
    mom20 = float(signal.get("mom20", 0.0) or 0.0)
    mom60 = float(signal.get("mom60", 0.0) or 0.0)
    lot_size = int(signal.get("lot_size", 1) or 1)

    if scaleout_stage < 1 and gain >= 0.10:
        return {
            "quantity": max(lot_size, int((int(current_qty * 0.30) // lot_size) * lot_size)),
            "reason": "Opportunity scale-out T1 (+10% from entry)",
            "reason_code": "scaleout_10",
        }

    if scaleout_stage < 2 and gain >= 0.18:
        return {
            "quantity": max(lot_size, int((int(current_qty * 0.30) // lot_size) * lot_size)),
            "reason": "Opportunity scale-out T2 (+18% from entry)",
            "reason_code": "scaleout_18",
        }

    if scaleout_stage >= 1 and gain > 0 and mom20 < mom60:
        return {
            "quantity": (int(current_qty) // lot_size) * lot_size,
            "reason": "Opportunity exit on momentum rollover after recovery",
            "reason_code": "exit_momentum",
        }

    last_entry_ts = state.get("last_entry_ts")
    if last_entry_ts:
        if as_of_date is not None:
            now_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
        else:
            now_dt = datetime.now()
        age_days = (now_dt - datetime.fromtimestamp(int(last_entry_ts))).days
        if age_days >= time_stop_days and gain < 0.10:
            return {
                "quantity": (int(current_qty) // lot_size) * lot_size,
                "reason": f"Opportunity time-stop rotation ({time_stop_days} days without progress)",
                "reason_code": "time_stop_rotation",
            }

    return None


def calculate_priority(action: str, allocation_delta: float, contrarian_score: float) -> float:
    """Calculate relative recommendation priority score."""
    base = abs(allocation_delta) * 10
    if action == "buy":
        return base + contrarian_score
    return base - contrarian_score


def generate_buy_reason(
    *,
    symbol: str,
    contrarian_score: float,
    current_alloc: float,
    target_alloc: float,
    signal: dict[str, float | int | str],
    lot_class: str,
) -> str:
    """Generate human-readable reason for a buy recommendation."""
    underweight = (target_alloc - current_alloc) * 100
    dip = float(signal.get("dip_score", 0.0))
    cap = float(signal.get("capitulation_score", 0.0))
    turn = int(signal.get("cycle_turn", 0))

    if current_alloc == 0:
        return (
            f"New contrarian entry ({lot_class} lot): dip={dip:.2f}, cap={cap:.2f}, turn={turn}, "
            f"score={contrarian_score:.2f}"
        )

    return (
        f"Underweight by {underweight:.1f}%. Contrarian score={contrarian_score:.2f}, "
        f"dip={dip:.2f}, cap={cap:.2f}, turn={turn}, lot={lot_class}"
    )


def generate_sell_reason(
    *,
    symbol: str,
    contrarian_score: float,
    current_alloc: float,
    target_alloc: float,
    signal: dict[str, float | int | str],
) -> str:
    """Generate human-readable reason for a sell recommendation."""
    overweight = (current_alloc - target_alloc) * 100
    sleeve = str(signal.get("sleeve", "core"))

    if target_alloc == 0:
        if contrarian_score < 0:
            return f"Exit {sleeve} position: {symbol} has weak contrarian score ({contrarian_score:.2f})"
        return f"Exit {sleeve} position: {symbol} not in target portfolio"

    return f"Overweight by {overweight:.1f}% in {sleeve} sleeve. Reduce to target allocation"


def calculate_transaction_cost(value: float, fixed_fee: float, pct_fee: float) -> float:
    """Calculate transaction cost for a trade value."""
    return fixed_fee + (value * pct_fee)
