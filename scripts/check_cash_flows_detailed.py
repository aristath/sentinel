#!/usr/bin/env python3
"""Check corporate actions and trades for cash flow data."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from tradernet import TraderNetAPI

env_file = Path(__file__).parent.parent / ".env.aristath"
load_dotenv(env_file)

api_key = os.getenv("TRADERNET_API_KEY")
api_secret = os.getenv("TRADERNET_API_SECRET")
client = TraderNetAPI(api_key, api_secret)

print("=" * 80)
print("CHECKING CORPORATE ACTIONS (DIVIDENDS, ETC.)")
print("=" * 80)

try:
    actions = client.corporate_actions()
    if isinstance(actions, list):
        print(f"Total corporate actions: {len(actions)}")

        # Filter for executed ones (those that actually paid out)
        executed = [a for a in actions if a.get("executed", False)]
        print(f"Executed actions: {len(executed)}")

        # Group by type
        types = {}
        for action in executed:
            action_type = action.get("type", "unknown")
            types[action_type] = types.get(action_type, 0) + 1

        print(f"\nExecuted action types:")
        for action_type, count in sorted(types.items()):
            print(f"  {action_type}: {count}")

        # Show sample dividend
        dividends = [
            a for a in executed if "dividend" in str(a.get("type", "")).lower()
        ]
        if dividends:
            print(f"\nSample dividend (first of {len(dividends)}):")
            sample = dividends[0]
            print(
                json.dumps(
                    {
                        k: v
                        for k, v in sample.items()
                        if k
                        in [
                            "id",
                            "type",
                            "ticker",
                            "currency",
                            "ex_date",
                            "pay_date",
                            "rate",
                            "amount_per_one",
                            "executed_count",
                            "executed",
                        ]
                    },
                    indent=2,
                    default=str,
                )
            )
except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 80)
print("CHECKING TRADES HISTORY FOR FEES/COMMISSIONS")
print("=" * 80)

try:
    trades = client.get_trades_history()
    if isinstance(trades, dict):
        trade_list = trades.get("trades", [])
        print(f"Total trades: {len(trade_list)}")

        if trade_list:
            # Check what fields are available
            sample = trade_list[0]
            print(f"\nSample trade fields:")
            print(
                json.dumps(
                    {
                        k: v
                        for k, v in sample.items()
                        if any(
                            keyword in k.lower()
                            for keyword in [
                                "fee",
                                "commission",
                                "cost",
                                "price",
                                "amount",
                                "currency",
                                "date",
                            ]
                        )
                    },
                    indent=2,
                    default=str,
                )
            )

            # Look for commission/fee fields
            fee_fields = [
                k
                for k in sample.keys()
                if "fee" in k.lower()
                or "commission" in k.lower()
                or "cost" in k.lower()
            ]
            if fee_fields:
                print(f"\nFound fee/commission fields: {fee_fields}")
            else:
                print("\nNo explicit fee/commission fields found in trade data")
except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 80)
print("CHECKING getClientCpsHistory WITH DATE RANGE")
print("=" * 80)

try:
    # Try with date range to see if we get more records
    from datetime import datetime, timedelta

    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * 5)  # 5 years

    history = client.authorized_request(
        "getClientCpsHistory",
        {
            "limit": 10000,
            "date_from": start_date.strftime("%Y-%m-%d"),
            "date_to": end_date.strftime("%Y-%m-%d"),
        },
        version=2,
    )
    records = history if isinstance(history, list) else []
    print(f"With date range: Found {len(records)} records")

    # Check for new type_doc_ids
    type_counts = {}
    for record in records:
        type_id = record.get("type_doc_id")
        type_counts[type_id] = type_counts.get(type_id, 0) + 1

    print(f"Transaction types found: {sorted(type_counts.keys())}")

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
