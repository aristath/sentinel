"""Quarterly evaluation job - runs meta-allocator to adjust satellite allocations.

This job should run every 3 months (quarterly) to:
1. Evaluate satellite performance over the past quarter
2. Calculate performance scores (Sharpe, Sortino, win rate, etc.)
3. Adjust target allocations based on relative performance
4. Apply dampening to avoid excessive churn
5. Log results and notify if significant changes
"""

import logging
from datetime import datetime

from app.core.events import SystemEvent, emit
from app.modules.display.services.display_service import set_led4
from app.modules.satellites.services.meta_allocator import MetaAllocator

logger = logging.getLogger(__name__)


async def run_quarterly_evaluation(
    evaluation_months: int = 3,
    dampening_factor: float = 0.5,
    dry_run: bool = False,
):
    """Run quarterly satellite performance evaluation and reallocation.

    Args:
        evaluation_months: Months of history to evaluate (default 3)
        dampening_factor: How much to move toward target (default 0.5 = 50%)
        dry_run: If True, preview changes without applying (default False)
    """
    logger.info(f"=== Starting quarterly evaluation (dry_run={dry_run}) ===")

    set_led4(0, 255, 0)  # Green for processing

    try:
        meta_allocator = MetaAllocator()

        # Run evaluation
        if dry_run:
            result = await meta_allocator.preview_reallocation(
                evaluation_months=evaluation_months
            )
            logger.info("DRY RUN: Changes not applied")
        else:
            result = await meta_allocator.apply_reallocation(
                evaluation_months=evaluation_months,
                dampening_factor=dampening_factor,
            )
            logger.info("Changes applied to satellite allocations")

        # Log summary
        logger.info(
            f"Quarterly evaluation complete: "
            f"{result.satellites_evaluated} satellites evaluated, "
            f"{result.satellites_improved} improved, "
            f"{result.satellites_reduced} reduced"
        )

        # Log individual recommendations
        for rec in result.recommendations:
            if abs(rec.adjustment_pct) > 0.005:  # Only log significant changes
                logger.info(
                    f"{rec.bucket_id}: "
                    f"{rec.current_allocation_pct:.2%} → {rec.new_allocation_pct:.2%} "
                    f"({rec.adjustment_pct:+.2%}) - {rec.reason}"
                )

        # Check for major reallocations (>2% change)
        major_changes = [
            rec for rec in result.recommendations if abs(rec.adjustment_pct) > 0.02
        ]

        if major_changes:
            logger.warning(
                f"Major allocation changes detected ({len(major_changes)} satellites):"
            )
            for rec in major_changes:
                logger.warning(
                    f"  {rec.bucket_id}: {rec.adjustment_pct:+.2%} "
                    f"(score: {rec.performance_score:.2f})"
                )

        return {
            "success": True,
            "dry_run": dry_run,
            "satellites_evaluated": result.satellites_evaluated,
            "satellites_improved": result.satellites_improved,
            "satellites_reduced": result.satellites_reduced,
            "major_changes": len(major_changes),
            "timestamp": result.timestamp,
        }

    except Exception as e:
        logger.error(f"Quarterly evaluation failed: {e}", exc_info=True)
        error_msg = "EVALUATION FAILED"
        emit(SystemEvent.ERROR_OCCURRED, message=error_msg)

        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }

    finally:
        set_led4(0, 0, 0)  # Clear LED


async def preview_quarterly_evaluation(evaluation_months: int = 3):
    """Preview quarterly evaluation without applying changes.

    Args:
        evaluation_months: Months of history to evaluate

    Returns:
        Dict with preview results
    """
    return await run_quarterly_evaluation(
        evaluation_months=evaluation_months,
        dry_run=True,
    )
