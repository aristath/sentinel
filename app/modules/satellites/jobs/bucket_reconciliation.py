"""Daily bucket reconciliation job.

Ensures virtual bucket balances match actual brokerage balances by:
1. Running reconciliation for each currency (EUR, USD)
2. Logging discrepancies
3. Alerting if significant drift detected
4. Auto-correcting minor discrepancies within tolerance

This job is CRITICAL for maintaining the fundamental invariant:
SUM(bucket_balances for currency X) == Actual brokerage balance for currency X
"""

import logging

logger = logging.getLogger(__name__)

# Optional import - job is disabled if satellites module not available
try:
    from app.modules.satellites.services.reconciliation_service import (
        ReconciliationService,
    )

    RECONCILIATION_AVAILABLE = True
except ImportError:
    RECONCILIATION_AVAILABLE = False
    logger.debug("Reconciliation service not available - job disabled")


async def run_bucket_reconciliation():
    """Run daily bucket reconciliation for all currencies.

    Checks that virtual bucket balances sum to actual brokerage balances.
    Reports discrepancies and performs auto-correction if within tolerance.
    """
    if not RECONCILIATION_AVAILABLE:
        logger.debug("Bucket reconciliation skipped - satellites module not available")
        return

    logger.info("Starting daily bucket reconciliation")

    try:
        reconciliation_service = ReconciliationService()

        # Reconcile each currency
        currencies = ["EUR", "USD"]  # Add more as needed
        results = {}

        for currency in currencies:
            try:
                logger.info(f"Reconciling {currency} balances...")
                result = await reconciliation_service.reconcile(currency)

                results[currency] = {
                    "virtual_total": result.virtual_total,
                    "actual_balance": result.actual_balance,
                    "discrepancy": result.discrepancy,
                    "within_tolerance": result.within_tolerance,
                    "corrected": result.corrected,
                    "needs_attention": result.needs_attention,
                }

                if result.needs_attention:
                    logger.warning(
                        f"BUCKET RECONCILIATION ALERT: {currency} balance mismatch detected! "
                        f"Virtual: {result.virtual_total:.2f}, "
                        f"Actual: {result.actual_balance:.2f}, "
                        f"Discrepancy: {result.discrepancy:.2f} {currency}"
                    )
                elif result.corrected:
                    logger.info(
                        f"Auto-corrected {currency} balance discrepancy: "
                        f"{result.discrepancy:.2f} {currency} (within tolerance)"
                    )
                else:
                    logger.info(
                        f"✓ {currency} balances reconciled successfully "
                        f"(virtual: {result.virtual_total:.2f}, actual: {result.actual_balance:.2f})"
                    )

            except Exception as e:
                logger.error(f"Failed to reconcile {currency}: {e}", exc_info=True)
                results[currency] = {"error": str(e)}

        # Summary
        total_discrepancies = sum(
            1
            for r in results.values()
            if isinstance(r, dict) and r.get("needs_attention")
        )

        if total_discrepancies > 0:
            logger.warning(
                f"Bucket reconciliation completed with {total_discrepancies} discrepancies requiring attention"
            )
        else:
            logger.info(
                "Bucket reconciliation completed successfully - all balances match"
            )

        return results

    except Exception as e:
        logger.error(f"Bucket reconciliation job failed: {e}", exc_info=True)
        raise
