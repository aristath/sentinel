"""Bucket maintenance job - updates high water marks and checks for hibernation.

This job runs daily to:
1. Update high water marks for all active satellites
2. Check for severe drawdowns and trigger hibernation if needed
3. Update bucket status based on current conditions
4. Reset consecutive losses if bucket recovers
"""

import logging
from datetime import datetime

from app.modules.satellites.domain.aggression_calculator import calculate_aggression
from app.modules.satellites.domain.models import BucketStatus
from app.modules.satellites.services.balance_service import BalanceService
from app.modules.satellites.services.bucket_service import BucketService
from app.repositories import PositionRepository

logger = logging.getLogger(__name__)


async def update_high_water_marks():
    """Update high water marks for all active satellites.

    This job should run daily to:
    1. Calculate current bucket value (positions + cash)
    2. Update high water mark if current value exceeds it
    3. Check for severe drawdowns and trigger hibernation
    4. Log significant changes
    """
    bucket_service = BucketService()
    balance_service = BalanceService()
    position_repo = PositionRepository()

    # Get all buckets (including core)
    buckets = await bucket_service.get_all_buckets()

    logger.info(f"Updating high water marks for {len(buckets)} buckets")

    updated_count = 0
    hibernated_count = 0
    recovered_count = 0

    for bucket in buckets:
        try:
            # Calculate current bucket value
            positions = await position_repo.get_all()
            bucket_positions = [
                p for p in positions if getattr(p, "bucket_id", "core") == bucket.id
            ]

            # Sum position values
            position_values = [
                p.market_value_eur
                for p in bucket_positions
                if p.market_value_eur is not None
            ]
            positions_value = sum(position_values)

            # Get cash balance
            balances = await balance_service.get_all_balances(bucket.id)
            cash_eur = sum(b.balance for b in balances if b.currency == "EUR")
            # TODO: Convert USD to EUR if needed

            current_value = positions_value + cash_eur

            # Check if this is a new high water mark
            if bucket.high_water_mark is None or current_value > bucket.high_water_mark:
                old_hwm = bucket.high_water_mark or 0.0
                await bucket_service.update_high_water_mark(bucket.id, current_value)
                updated_count += 1

                pct_increase = (
                    ((current_value - old_hwm) / old_hwm * 100) if old_hwm > 0 else 0
                )
                logger.info(
                    f"{bucket.id}: New high water mark €{current_value:.2f} "
                    f"(+{pct_increase:.1f}% from €{old_hwm:.2f})"
                )

                # Reset consecutive losses on new high
                if bucket.consecutive_losses > 0:
                    await bucket_service.reset_consecutive_losses(bucket.id)
                    logger.info(
                        f"{bucket.id}: Reset consecutive losses "
                        f"(was {bucket.consecutive_losses})"
                    )

            # Check for severe drawdown (>35% = hibernation threshold)
            if bucket.high_water_mark and bucket.high_water_mark > 0:
                drawdown = (
                    bucket.high_water_mark - current_value
                ) / bucket.high_water_mark

                if drawdown >= 0.35:
                    # Trigger hibernation
                    if bucket.status != BucketStatus.HIBERNATING:
                        await bucket_service.hibernate(
                            bucket.id,
                            reason=f"Severe drawdown: {drawdown*100:.1f}% from high water mark",
                        )
                        hibernated_count += 1
                        logger.warning(
                            f"{bucket.id}: HIBERNATED due to {drawdown*100:.1f}% drawdown "
                            f"(€{bucket.high_water_mark:.2f} → €{current_value:.2f})"
                        )
                elif drawdown >= 0.25:
                    # Major drawdown warning
                    logger.warning(
                        f"{bucket.id}: Major drawdown {drawdown*100:.1f}% "
                        f"(€{bucket.high_water_mark:.2f} → €{current_value:.2f})"
                    )
                elif bucket.status == BucketStatus.HIBERNATING and drawdown < 0.30:
                    # Recovery from hibernation (when drawdown < 30%)
                    await bucket_service.resume(
                        bucket.id,
                        reason=f"Recovery from drawdown (now {drawdown*100:.1f}%)",
                    )
                    recovered_count += 1
                    logger.info(
                        f"{bucket.id}: Resumed from hibernation "
                        f"(drawdown reduced to {drawdown*100:.1f}%)"
                    )

            # For satellites, calculate and log aggression status
            if bucket.id != "core" and bucket.target_allocation_pct > 0:
                # Calculate total portfolio value (approximate)
                total_portfolio_value = sum(
                    sum(
                        p.market_value_eur
                        for p in positions
                        if p.market_value_eur is not None
                    )
                    for _ in [1]  # Just once
                )
                # Add all cash
                all_cash = sum(
                    b.balance
                    for bucket_temp in buckets
                    for b in await balance_service.get_all_balances(bucket_temp.id)
                    if b.currency == "EUR"
                )
                total_portfolio_value += all_cash

                target_value = bucket.target_allocation_pct * total_portfolio_value

                aggression_result = calculate_aggression(
                    current_value=current_value,
                    target_value=target_value,
                    high_water_mark=bucket.high_water_mark,
                )

                logger.info(
                    f"{bucket.id}: Current value €{current_value:.2f}, "
                    f"Target €{target_value:.2f} ({bucket.target_allocation_pct*100:.1f}%), "
                    f"HWM €{bucket.high_water_mark or 0:.2f}, "
                    f"Aggression {aggression_result.aggression*100:.0f}% "
                    f"({'HIBERNATING' if aggression_result.in_hibernation else 'ACTIVE'})"
                )

        except Exception as e:
            logger.error(
                f"Error updating high water mark for {bucket.id}: {e}",
                exc_info=True,
            )
            # Continue with other buckets

    logger.info(
        f"High water mark update complete: "
        f"{updated_count} updated, "
        f"{hibernated_count} hibernated, "
        f"{recovered_count} recovered"
    )

    return {
        "total_buckets": len(buckets),
        "updated_count": updated_count,
        "hibernated_count": hibernated_count,
        "recovered_count": recovered_count,
        "timestamp": datetime.now().isoformat(),
    }


async def check_consecutive_losses():
    """Check for excessive consecutive losses and pause buckets if needed.

    This is a separate check from drawdown-based hibernation.
    If a bucket has 5+ consecutive losing trades, it should be paused
    for manual review.
    """
    bucket_service = BucketService()
    buckets = await bucket_service.get_all_buckets()

    paused_count = 0

    for bucket in buckets:
        if bucket.consecutive_losses >= bucket.max_consecutive_losses:
            if bucket.status not in [BucketStatus.PAUSED, BucketStatus.HIBERNATING]:
                await bucket_service.pause(
                    bucket.id,
                    reason=f"Consecutive losses threshold reached: {bucket.consecutive_losses}",
                )
                paused_count += 1
                logger.warning(
                    f"{bucket.id}: PAUSED due to {bucket.consecutive_losses} "
                    f"consecutive losses (threshold: {bucket.max_consecutive_losses})"
                )

    if paused_count > 0:
        logger.info(f"Paused {paused_count} buckets due to consecutive losses")

    return {"paused_count": paused_count}


async def run_bucket_maintenance():
    """Run all bucket maintenance tasks.

    This is the main entry point for the scheduled job.
    """
    logger.info("=== Starting bucket maintenance ===")

    try:
        # Update high water marks and check for hibernation
        hwm_result = await update_high_water_marks()

        # Check for consecutive losses
        loss_result = await check_consecutive_losses()

        logger.info(
            f"=== Bucket maintenance complete: "
            f"{hwm_result['updated_count']} HWM updates, "
            f"{hwm_result['hibernated_count']} hibernated, "
            f"{hwm_result['recovered_count']} recovered, "
            f"{loss_result['paused_count']} paused ==="
        )

        return {
            "success": True,
            "hwm_result": hwm_result,
            "loss_result": loss_result,
        }

    except Exception as e:
        logger.error(f"Bucket maintenance failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
