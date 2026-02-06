#!/usr/bin/env python3
"""Test script to fetch trades history and cashflows from Tradernet API."""

import asyncio
import json
from typing import Any, cast

from sentinel.database import Database
from sentinel.settings import Settings


async def main():
    db = Database()
    await db.connect()
    settings = Settings()

    api_key = await settings.get("tradernet_api_key")
    api_secret = await settings.get("tradernet_api_secret")

    if not api_key or not api_secret:
        print("No API credentials found")
        return

    from tradernet import TraderNetAPI

    api = TraderNetAPI(public=api_key, private=api_secret)

    # Test 1: Get trades history
    print("=" * 60)
    print("TRADES HISTORY")
    print("=" * 60)
    response = api.get_trades_history(start="2024-01-01", end="2025-12-31", limit=5)
    if response:
        print(json.dumps(response, indent=2, default=str)[:3000])

    # Test 2: Try getUserCashFlows for dividends
    print("\n" + "=" * 60)
    print("CASHFLOWS (Dividends)")
    print("=" * 60)

    # Use raw API request for getUserCashFlows
    cashflow_response = cast(Any, api).request(
        "getUserCashFlows",
        {
            "take": 100,
            "filters": [{"field": "type_code", "operator": "eq", "value": "dividend"}],
            "sort": [{"field": "date", "dir": "DESC"}],
        },
    )
    if cashflow_response:
        print(json.dumps(cashflow_response, indent=2, default=str)[:3000])

    # Test 3: Get ALL cashflows
    print("\n" + "=" * 60)
    print("ALL CASHFLOWS")
    print("=" * 60)

    all_cashflows = cast(Any, api).request(
        "getUserCashFlows",
        {
            "take": 20,
            "sort": [{"field": "date", "dir": "DESC"}],
        },
    )
    if all_cashflows:
        print(json.dumps(all_cashflows, indent=2, default=str)[:3000])


if __name__ == "__main__":
    asyncio.run(main())
