"""Shared current-market execution context."""

from __future__ import annotations

import json


async def get_open_market_symbols(broker, db) -> set[str]:
    """Return active securities whose broker market is currently open."""
    market_data = await broker.get_market_status("*")
    if not market_data:
        return set()

    open_market_ids = {str(market.get("i")) for market in market_data.get("m", []) if market.get("s") == "OPEN"}
    if not open_market_ids:
        return set()

    open_symbols: set[str] = set()
    for security in await db.get_all_securities(active_only=True):
        raw_data = security.get("data")
        if not raw_data:
            continue
        try:
            data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            market_id = str(data.get("mrkt", {}).get("mkt_id"))
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
            continue
        if market_id in open_market_ids:
            open_symbols.add(security["symbol"])
    return open_symbols
