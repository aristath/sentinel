"""Cash flow sync job for periodic updates from Tradernet API."""

import json
import logging

from app.core.database.manager import get_db_manager
from app.core.events import SystemEvent, emit
from app.domain.models import DividendRecord
from app.infrastructure.external.tradernet import get_tradernet_client
from app.infrastructure.locking import file_lock
from app.modules.display.services.display_service import set_led4, set_text
from app.repositories import DividendRepository

logger = logging.getLogger(__name__)


async def sync_cash_flows():
    """
    Sync cash flow transactions from Tradernet API to local database.

    This job:
    1. Fetches all cash flow transactions from Tradernet API
    2. Upserts them into the local database
    3. Handles errors gracefully with logging

    Uses file locking to prevent concurrent syncs.
    """
    async with file_lock("cash_flow_sync", timeout=120.0):
        await _sync_cash_flows_internal()


async def _sync_cash_flows_internal():
    """Internal cash flow sync implementation."""
    logger.info("Starting cash flow sync")

    emit(SystemEvent.CASH_FLOW_SYNC_START)
    set_text("SYNCING CASH FLOWS...")
    set_led4(0, 255, 0)  # Green for processing

    client = get_tradernet_client()

    if not client.is_connected:
        if not client.connect():
            logger.warning("Failed to connect to Tradernet, skipping cash flow sync")
            error_msg = "BROKER CONNECTION FAILED"
            emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
            set_text(error_msg)
            return

    try:
        # Fetch all cash flows from API
        transactions = client.get_all_cash_flows(limit=1000)

        if not transactions:
            logger.info("No cash flow transactions found in API")
            return

        logger.info(f"Fetched {len(transactions)} transactions from API")

        db_manager = get_db_manager()

        # Get existing transaction IDs to avoid duplicates
        cursor = await db_manager.ledger.execute(
            "SELECT transaction_id FROM cash_flows WHERE transaction_id IS NOT NULL"
        )
        existing_ids = {row[0] for row in await cursor.fetchall()}

        synced_count = 0
        dividend_repo = DividendRepository()

        async with db_manager.ledger.transaction():
            for txn in transactions:
                txn_id = txn.get("transaction_id")
                if txn_id and txn_id in existing_ids:
                    continue

                # Get amount in EUR (use exchange rate or default to same as amount)
                amount = txn.get("amount", 0)
                currency = txn.get("currency", "EUR")
                amount_eur = (
                    txn.get("amount_eur") or amount
                )  # Fallback to amount if no EUR conversion

                # Serialize params to JSON if it's a dict
                params = txn.get("params")
                params_json = txn.get("params_json")
                if params and not params_json:
                    params_json = (
                        json.dumps(params) if isinstance(params, dict) else str(params)
                    )

                cursor = await db_manager.ledger.execute(
                    """
                    INSERT INTO cash_flows
                    (transaction_id, type_doc_id, transaction_type, date, amount, currency,
                     amount_eur, status, status_c, description, params_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        txn.get("transaction_id"),
                        txn.get("type_doc_id", 0),  # Default to 0 if not provided
                        txn.get("type") or txn.get("transaction_type"),
                        txn.get("date"),
                        amount,
                        currency,
                        amount_eur,
                        txn.get("status"),
                        txn.get("status_c"),
                        txn.get("description"),
                        params_json,
                    ),
                )
                cash_flow_id = cursor.lastrowid
                synced_count += 1

                # Create dividend record if this is a dividend cash flow
                transaction_type = (
                    txn.get("type") or txn.get("transaction_type", "")
                ).lower()
                if transaction_type == "dividend":
                    try:
                        # Extract symbol from params
                        symbol = None
                        if params:
                            symbol = params.get("ticker") or params.get("symbol")
                        elif params_json:
                            # Try to parse params_json
                            try:
                                parsed_params = (
                                    json.loads(params_json)
                                    if isinstance(params_json, str)
                                    else params_json
                                )
                                symbol = parsed_params.get(
                                    "ticker"
                                ) or parsed_params.get("symbol")
                            except (json.JSONDecodeError, TypeError):
                                pass

                        if symbol:
                            # Check if dividend record already exists for this cash flow
                            existing = await dividend_repo.exists_for_cash_flow(
                                cash_flow_id
                            )
                            if not existing:
                                dividend = DividendRecord(
                                    symbol=symbol,
                                    cash_flow_id=cash_flow_id,
                                    amount=amount,
                                    currency=currency,
                                    amount_eur=amount_eur,
                                    payment_date=txn.get("date", ""),
                                    reinvested=False,
                                )
                                await dividend_repo.create(dividend)
                                logger.info(
                                    f"Created dividend record for {symbol}: {amount_eur:.2f} EUR "
                                    f"(cash_flow_id={cash_flow_id})"
                                )
                            else:
                                logger.debug(
                                    f"Dividend record already exists for cash_flow_id={cash_flow_id}, skipping"
                                )
                        else:
                            logger.warning(
                                f"Could not extract symbol from dividend cash flow "
                                f"(transaction_id={txn_id}, cash_flow_id={cash_flow_id})"
                            )
                    except Exception as e:
                        logger.error(
                            f"Error creating dividend record for cash_flow_id={cash_flow_id}: {e}",
                            exc_info=True,
                        )
                        # Don't fail the entire sync if dividend record creation fails

        logger.info(
            f"Cash flow sync complete: {synced_count}/{len(transactions)} transactions synced"
        )

        emit(SystemEvent.CASH_FLOW_SYNC_COMPLETE)

    except Exception as e:
        logger.error(f"Cash flow sync failed: {e}", exc_info=True)
        error_msg = "CASH FLOW SYNC CRASHES"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)
        set_text(error_msg)
    finally:
        set_led4(0, 0, 0)  # Clear LED when done
