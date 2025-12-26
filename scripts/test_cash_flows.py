#!/usr/bin/env python3
"""Test script to explore tradernet API cash flow history.

This script loads credentials from .env.aristath and calls the tradernet API
to discover all available cash flow transaction types.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from tradernet import TraderNetAPI

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load credentials from .env.aristath
env_file = Path(__file__).parent.parent / ".env.aristath"
if not env_file.exists():
    print(f"Error: {env_file} not found")
    sys.exit(1)

load_dotenv(env_file)

api_key = os.getenv("TRADERNET_API_KEY")
api_secret = os.getenv("TRADERNET_API_SECRET")

if not api_key or not api_secret:
    print(
        "Error: TRADERNET_API_KEY and TRADERNET_API_SECRET must be set in .env.aristath"
    )
    sys.exit(1)

print("Connecting to Tradernet API...")
client = TraderNetAPI(api_key, api_secret)

try:
    # Test connection
    user_info = client.user_info()
    print("✓ Connected successfully")
    print(f"  User: {user_info.get('login', 'N/A')}")
    print()
except Exception as e:
    print(f"✗ Failed to connect: {e}")
    sys.exit(1)


def _analyze_transaction_types(records: list) -> tuple[dict, dict, dict]:
    """Analyze transaction types and return counts and details."""
    type_counts = {}
    status_counts = {}
    type_details = {}

    for record in records:
        type_doc_id = record.get("type_doc_id")
        status_c = record.get("status_c")

        if type_doc_id not in type_counts:
            type_counts[type_doc_id] = 0
            type_details[type_doc_id] = {
                "count": 0,
                "statuses": set(),
                "sample": record,
            }
        type_counts[type_doc_id] += 1
        type_details[type_doc_id]["count"] += 1
        type_details[type_doc_id]["statuses"].add(status_c)

        if status_c not in status_counts:
            status_counts[status_c] = 0
        status_counts[status_c] += 1

    return type_counts, status_counts, type_details


def _parse_record_params(sample: dict) -> dict:
    """Parse params from a record sample."""
    params_str = sample.get("params", "{}")
    try:
        return json.loads(params_str) if isinstance(params_str, str) else params_str
    except Exception:
        return {}


def _print_type_details(type_doc_id: int, count: int, details: dict) -> None:
    """Print details for a transaction type."""
    sample = details["sample"]
    print(f"Type ID: {type_doc_id} ({count} records)")
    print(f"  Status codes: {sorted(details['statuses'])}")

    params = _parse_record_params(sample)
    description = sample.get("name", "")
    if description:
        print(f"  Description: {description}")

    if "currency" in params:
        print(f"  Currency: {params.get('currency')}")
    if "totalMoneyOut" in params:
        print(f"  Amount (out): {params.get('totalMoneyOut')}")
    if "totalMoneyIn" in params:
        print(f"  Amount (in): {params.get('totalMoneyIn')}")

    date_crt = sample.get("date_crt", "")
    if date_crt:
        print(f"  Date: {date_crt[:10] if len(date_crt) >= 10 else date_crt}")

    print()


def _print_transaction_summary(type_counts: dict, type_details: dict) -> None:
    """Print transaction type summary."""
    print("=" * 80)
    print("TRANSACTION TYPE SUMMARY")
    print("=" * 80)
    print(f"\nFound {len(type_counts)} unique transaction types:\n")

    for type_doc_id in sorted(type_counts.keys()):
        _print_type_details(
            type_doc_id, type_counts[type_doc_id], type_details[type_doc_id]
        )


def _print_status_summary(status_counts: dict) -> None:
    """Print status code summary."""
    print("=" * 80)
    print("STATUS CODE SUMMARY")
    print("=" * 80)
    for status_c in sorted(status_counts.keys()):
        print(f"Status {status_c}: {status_counts[status_c]} records")
    print()


def _print_sample_records(type_details: dict) -> None:
    """Print sample records for each type."""
    print("=" * 80)
    print("SAMPLE RECORDS (one per type)")
    print("=" * 80)
    for type_doc_id in sorted(type_details.keys()):
        sample = type_details[type_doc_id]["sample"]
        print(f"\nType {type_doc_id}:")
        print(json.dumps(sample, indent=2, default=str))


# Get cash flow history with high limit to see all types
print("Fetching cash flow history...")
try:
    history = client.authorized_request(
        "getClientCpsHistory", {"limit": 1000}, version=2
    )

    if not history:
        print("No history returned")
        sys.exit(0)

    records = history if isinstance(history, list) else []
    print(f"✓ Retrieved {len(records)} records")
    print()

    type_counts, status_counts, type_details = _analyze_transaction_types(records)

    _print_transaction_summary(type_counts, type_details)
    _print_status_summary(status_counts)
    _print_sample_records(type_details)

except Exception as e:
    print(f"✗ Failed to fetch history: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
