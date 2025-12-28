"""Transaction parsing functions for Tradernet API."""

import hashlib
import json
import logging
from datetime import datetime
from typing import Optional

from app.infrastructure.external.tradernet.utils import (
    get_exchange_rate_sync,
    led_api_call,
)

logger = logging.getLogger(__name__)


def parse_cps_history_params(params_str) -> dict:
    """Parse params JSON string from CPS history record."""
    try:
        return json.loads(params_str) if isinstance(params_str, str) else params_str
    except (json.JSONDecodeError, TypeError):
        return {}


def extract_amount_and_currency(params: dict, type_doc_id: int) -> tuple[float, str]:
    """Extract amount and currency from params based on transaction type."""
    amount = 0.0
    currency = "EUR"

    try:
        if "totalMoneyOut" in params:
            amount = float(params.get("totalMoneyOut", 0))
            currency = params.get("currency", "EUR")
        elif "totalMoneyIn" in params:
            amount = float(params.get("totalMoneyIn", 0))
            currency = params.get("currency", "EUR")
        elif "structured_product_trade_sum" in params:
            amount = float(params.get("structured_product_trade_sum", 0))
            currency = params.get("structured_product_currency", "USD")
        elif "amount" in params:
            amount = float(params.get("amount", 0))
            currency = params.get("currency", "EUR")
        elif "sum" in params:
            amount = float(params.get("sum", 0))
            currency = params.get("currency", "EUR")
    except (ValueError, TypeError):
        pass

    return amount, currency


def convert_amount_to_eur(amount: float, currency: str) -> float:
    """Convert amount to EUR using exchange rate."""
    if currency == "EUR" or amount == 0:
        return amount

    try:
        rate = get_exchange_rate_sync(currency, "EUR")
        if rate > 0:
            return amount / rate
    except Exception as e:
        logger.debug(f"Failed to convert {amount} {currency} to EUR: {e}")

    return amount


def create_transaction_id(record: dict, type_doc_id) -> str:
    """Create unique transaction ID from record."""
    transaction_id = (
        record.get("id") or record.get("transaction_id") or record.get("doc_id")
    )

    if not transaction_id:
        unique_str = f"{type_doc_id}_{record.get('date_crt', '')}_{record.get('status_c', '')}_{json.dumps(record.get('params', {}), sort_keys=True)}"
        transaction_id = (
            f"{type_doc_id}_{hashlib.md5(unique_str.encode()).hexdigest()[:8]}"
        )

    return str(transaction_id)


def extract_withdrawal_fee(
    params: dict, transaction_id: str, date: str, currency: str, status: str, status_c
) -> Optional[dict]:
    """Extract withdrawal fee as separate transaction."""
    if "total_commission" not in params:
        return None

    withdrawal_fee = params.get("total_commission", 0)
    if not withdrawal_fee or float(withdrawal_fee) <= 0:
        return None

    fee_currency = params.get("commission_currency", currency)
    fee_amount_eur = convert_amount_to_eur(float(withdrawal_fee), fee_currency)

    return {
        "transaction_id": f"{transaction_id}_fee",
        "type_doc_id": "withdrawal_fee",
        "transaction_type": "withdrawal_fee",
        "date": date,
        "amount": float(withdrawal_fee),
        "currency": fee_currency,
        "amount_eur": round(fee_amount_eur, 2),
        "status": status,
        "status_c": status_c,
        "description": f"Withdrawal fee for {params.get('totalMoneyOut', 0)} {currency} withdrawal",
        "params": {"withdrawal_id": transaction_id, **params},
    }


def extract_structured_product_fee(
    params: dict, transaction_id: str, date: str, currency: str, status: str, status_c
) -> Optional[dict]:
    """Extract structured product commission as separate transaction."""
    if "structured_product_trade_commission" not in params:
        return None

    sp_commission = params.get("structured_product_trade_commission", 0)
    if not sp_commission or float(sp_commission) <= 0:
        return None

    sp_comm_eur = convert_amount_to_eur(float(sp_commission), currency)

    return {
        "transaction_id": f"{transaction_id}_fee",
        "type_doc_id": "structured_product_fee",
        "transaction_type": "structured_product_fee",
        "date": date,
        "amount": float(sp_commission),
        "currency": currency,
        "amount_eur": round(sp_comm_eur, 2),
        "status": status,
        "status_c": status_c,
        "description": "Structured product commission",
        "params": {"product_id": transaction_id, **params},
    }


def process_cps_history_record(record: dict, type_mapping: dict) -> list[dict]:
    """Process a single CPS history record and return transactions."""
    transactions: list[dict] = []

    try:
        params = parse_cps_history_params(record.get("params", "{}"))
        type_doc_id = record.get("type_doc_id")
        if type_doc_id is None:
            return transactions

        status_c = record.get("status_c")
        transaction_type = type_mapping.get(type_doc_id, f"type_{type_doc_id}")

        amount, currency = extract_amount_and_currency(params, type_doc_id)
        amount_eur = convert_amount_to_eur(amount, currency)

        transaction_id = create_transaction_id(record, type_doc_id)

        date_crt = record.get("date_crt", "")
        date = (
            date_crt[:10]
            if len(date_crt) >= 10
            else date_crt or datetime.now().strftime("%Y-%m-%d")
        )

        description = record.get("name", "") or record.get("description", "")

        status_map: dict[int, str] = {
            1: "pending",
            2: "processing",
            3: "completed",
            4: "cancelled",
            5: "rejected",
        }
        status = status_map.get(status_c or 0, f"status_{status_c}")

        transactions.append(
            {
                "transaction_id": transaction_id,
                "type_doc_id": type_doc_id,
                "transaction_type": transaction_type,
                "date": date,
                "amount": amount,
                "currency": currency or "EUR",
                "amount_eur": round(amount_eur, 2),
                "status": status,
                "status_c": status_c,
                "description": description,
                "params": params,
            }
        )

        fee_transaction = extract_withdrawal_fee(
            params, transaction_id, date, currency, status, status_c
        )
        if fee_transaction:
            transactions.append(fee_transaction)

        sp_fee_transaction = extract_structured_product_fee(
            params, transaction_id, date, currency, status, status_c
        )
        if sp_fee_transaction:
            transactions.append(sp_fee_transaction)

    except Exception as e:
        logger.error(f"Failed to process transaction record: {e}")

    return transactions


def process_corporate_action(action: dict) -> Optional[dict]:
    """Process a single corporate action and return transaction dict."""
    action_type = action.get("type", "").lower()

    if action_type not in ["dividend", "coupon", "maturity", "partial_maturity"]:
        return None

    amount_per_one = float(action.get("amount_per_one", 0))
    executed_count = int(action.get("executed_count", 0))
    amount = amount_per_one * executed_count

    if amount == 0:
        return None

    currency = action.get("currency", "USD")
    pay_date = action.get("pay_date", action.get("ex_date", ""))
    date = pay_date[:10] if len(pay_date) >= 10 else pay_date

    amount_eur = convert_amount_to_eur(amount, currency)

    action_id = action.get("id") or action.get("corporate_action_id", "")
    transaction_id = f"corp_action_{action_type}_{action_id}"

    ticker = action.get("ticker", "")
    description = f"{action_type.title()}: {ticker} ({executed_count} shares × {amount_per_one} {currency})"

    return {
        "transaction_id": transaction_id,
        "type_doc_id": f"corp_{action_type}",
        "transaction_type": action_type,
        "date": date,
        "amount": amount,
        "currency": currency,
        "amount_eur": round(amount_eur, 2),
        "status": "completed",
        "status_c": None,
        "description": description,
        "params": action,
    }


def process_trade_fee(trade: dict) -> Optional[dict]:
    """Process a single trade fee and return transaction dict."""
    commission_str = trade.get("commission", "0")
    try:
        commission = float(commission_str) if commission_str else 0.0
    except (ValueError, TypeError):
        commission = 0.0

    if commission == 0:
        return None

    currency = trade.get("commission_currency", trade.get("curr_c", "EUR"))
    trade_date = trade.get("date", "")
    date = trade_date[:10] if len(trade_date) >= 10 else trade_date

    amount_eur = convert_amount_to_eur(commission, currency)

    trade_id = trade.get("id") or trade.get("order_id", "")
    transaction_id = f"trade_fee_{trade_id}"

    instr_name = trade.get("instr_nm", "")
    description = f"Trading fee: {instr_name}"

    return {
        "transaction_id": transaction_id,
        "type_doc_id": "trade_fee",
        "transaction_type": "trading_fee",
        "date": date,
        "amount": commission,
        "currency": currency,
        "amount_eur": round(amount_eur, 2),
        "status": "completed",
        "status_c": None,
        "description": description,
        "params": trade,
    }


def get_cps_history_transactions(client, limit: int) -> list[dict]:
    """Get transactions from CPS history."""
    try:
        with led_api_call():
            history = client.authorized_request(
                "getClientCpsHistory", {"limit": limit}, version=2
            )

        records = history if isinstance(history, list) else []
        type_mapping = {337: "withdrawal", 297: "structured_product_purchase"}

        transactions = []
        for record in records:
            transactions.extend(process_cps_history_record(record, type_mapping))
        return transactions
    except Exception as e:
        logger.warning(f"Failed to get CPS history: {e}")
        return []


def get_corporate_action_transactions(client) -> list[dict]:
    """Get transactions from corporate actions."""
    try:
        with led_api_call():
            corporate_actions = client.corporate_actions()

        executed_actions = [
            a
            for a in corporate_actions
            if isinstance(a, dict) and a.get("executed", False)
        ]

        transactions = []
        for action in executed_actions:
            transaction = process_corporate_action(action)
            if transaction:
                transactions.append(transaction)
        return transactions
    except Exception as e:
        logger.warning(f"Failed to get corporate actions: {e}")
        return []


def parse_withdrawal_record(record: dict) -> Optional[dict]:
    """Parse a withdrawal record and return withdrawal dict."""
    if record.get("type_doc_id") != 337:
        return None

    if record.get("status_c") != 3:
        return None

    params_str = record.get("params", "{}")
    try:
        params = json.loads(params_str) if isinstance(params_str, str) else params_str
    except json.JSONDecodeError:
        return None

    currency = params.get("currency", "EUR")
    amount = float(params.get("totalMoneyOut", 0))

    if currency != "EUR" and amount > 0:
        rate = get_exchange_rate_sync(currency, "EUR")
        if rate > 0:
            amount = amount / rate

    date_crt = record.get("date_crt", "")
    date = date_crt[:10] if len(date_crt) >= 10 else date_crt

    return {
        "date": date,
        "amount": amount,
        "amount_eur": round(amount, 2),
        "currency": currency,
        "description": record.get("name", ""),
    }


def get_trade_fee_transactions(client) -> list[dict]:
    """Get transactions from trade fees."""
    try:
        with led_api_call():
            trades_data = client.get_trades_history()

        trade_list = trades_data.get("trades", {}).get("trade", [])

        transactions = []
        for trade in trade_list:
            transaction = process_trade_fee(trade)
            if transaction:
                transactions.append(transaction)
        return transactions
    except Exception as e:
        logger.warning(f"Failed to get trades history: {e}")
        return []
