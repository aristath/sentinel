#!/usr/bin/env python3
"""Explore tradernet API to find all cash flow related endpoints."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from tradernet import TraderNetAPI

# Load credentials
env_file = Path(__file__).parent.parent / ".env.aristath"
if not env_file.exists():
    print(f"Error: {env_file} not found")
    sys.exit(1)

load_dotenv(env_file)

api_key = os.getenv("TRADERNET_API_KEY")
api_secret = os.getenv("TRADERNET_API_SECRET")

if not api_key or not api_secret:
    print("Error: TRADERNET_API_KEY and TRADERNET_API_SECRET must be set")
    sys.exit(1)

client = TraderNetAPI(api_key, api_secret)

print("=" * 80)
print("EXPLORING TRADERNET API FOR CASH FLOW DATA")
print("=" * 80)
print()

# 1. Check getClientCpsHistory with higher limit and date range
print("1. getClientCpsHistory with limit=5000...")
try:
    history = client.authorized_request(
        "getClientCpsHistory", {"limit": 5000}, version=2
    )
    records = history if isinstance(history, list) else []
    print(f"   Found {len(records)} total records")

    # Count all type_doc_ids
    type_counts = {}
    for record in records:
        type_id = record.get("type_doc_id")
        type_counts[type_id] = type_counts.get(type_id, 0) + 1

    print(f"   Found {len(type_counts)} unique transaction types:")
    for type_id in sorted(type_counts.keys()):
        print(f"     Type {type_id}: {type_counts[type_id]} records")
    print()
except Exception as e:
    print(f"   Error: {e}")
    print()

# 2. Check broker report
print("2. get_broker_report...")
try:
    report = client.get_broker_report()
    print(f"   Type: {type(report)}")
    if isinstance(report, dict):
        print(f"   Keys: {list(report.keys())[:20]}")
        # Look for cash flow related fields
        report_str = json.dumps(report, default=str)
        if (
            "fee" in report_str.lower()
            or "commission" in report_str.lower()
            or "dividend" in report_str.lower()
        ):
            print("   Contains fee/commission/dividend data!")
    print()
except Exception as e:
    print(f"   Error: {e}")
    print()

# 3. Check trades history
print("3. get_trades_history...")
try:
    trades = client.get_trades_history()
    print(f"   Type: {type(trades)}")
    if isinstance(trades, list):
        print(f"   Found {len(trades)} trades")
        if trades:
            print(
                f"   Sample trade keys: {list(trades[0].keys()) if isinstance(trades[0], dict) else 'N/A'}"
            )
    elif isinstance(trades, dict):
        print(f"   Keys: {list(trades.keys())[:20]}")
    print()
except Exception as e:
    print(f"   Error: {e}")
    print()

# 4. Check corporate actions (dividends, splits, etc.)
print("4. corporate_actions...")
try:
    actions = client.corporate_actions()
    print(f"   Type: {type(actions)}")
    if isinstance(actions, list):
        print(f"   Found {len(actions)} corporate actions")
        if actions:
            print(
                f"   Sample action keys: {list(actions[0].keys()) if isinstance(actions[0], dict) else 'N/A'}"
            )
    elif isinstance(actions, dict):
        print(f"   Keys: {list(actions.keys())[:20]}")
    print()
except Exception as e:
    print(f"   Error: {e}")
    print()

# 5. Check account summary for cash flow fields
print("5. account_summary (checking for cash flow fields)...")
try:
    summary = client.account_summary()
    if isinstance(summary, dict):
        result = summary.get("result", {})
        ps = result.get("ps", {})
        acc = ps.get("acc", [])
        print(f"   Cash accounts: {len(acc)}")
        for cash in acc[:3]:
            print(f"     {cash}")

        # Look for transaction history in summary
        if "transactions" in str(summary).lower() or "history" in str(summary).lower():
            print("   Contains transaction/history data!")
    print()
except Exception as e:
    print(f"   Error: {e}")
    print()

# 6. Try to find other API methods that might have cash flows
print("6. Searching for other potential cash flow endpoints...")
potential_methods = [
    "getClientTransactions",
    "getClientCashFlows",
    "getClientPayments",
    "getClientFees",
    "getClientDividends",
    "getAccountTransactions",
    "getAccountHistory",
]

for method in potential_methods:
    try:
        result = client.authorized_request(method, {}, version=2)
        print(f"   {method}: Found data! Type: {type(result)}")
        if isinstance(result, (list, dict)):
            print(
                f"      Length/Keys: {len(result) if isinstance(result, list) else list(result.keys())[:5]}"
            )
    except Exception:
        # Silently skip methods that don't exist
        pass

print()
print("=" * 80)
print("EXPLORATION COMPLETE")
print("=" * 80)
