"""Dividend router - routes dividends based on satellite settings.

Routes dividends according to satellite configuration:
- reinvest_same: Keep dividend in satellite's cash balance (for reinvestment)
- send_to_core: Transfer dividend to core bucket
- accumulate_cash: Keep in satellite (same as reinvest_same)
"""

import logging
from typing import Optional

from app.modules.satellites.services.balance_service import BalanceService
from app.modules.satellites.services.bucket_service import BucketService

logger = logging.getLogger(__name__)


class DividendRouter:
    """Routes dividends to appropriate buckets based on settings."""

    def __init__(self):
        self.bucket_service = BucketService()
        self.balance_service = BalanceService()

    async def route_dividend(
        self,
        bucket_id: str,
        amount: float,
        currency: str,
        symbol: str,
        payment_date: str,
        description: Optional[str] = None,
    ) -> dict:
        """Route a dividend payment based on satellite settings.

        Args:
            bucket_id: The bucket that owns the position generating the dividend
            amount: Dividend amount
            currency: Currency code (EUR, USD, etc.)
            symbol: Stock symbol that generated the dividend
            payment_date: Dividend payment date
            description: Optional description

        Returns:
            Dict with routing details:
            {
                "source_bucket": str,
                "destination_bucket": str,
                "amount": float,
                "currency": str,
                "action": "kept" | "transferred",
                "dividend_handling": str
            }
        """
        # Get bucket to determine routing
        bucket = await self.bucket_service.get_bucket(bucket_id)
        if not bucket:
            logger.warning(f"Bucket {bucket_id} not found, routing dividend to core")
            # Default to core if bucket not found
            await self.balance_service.record_dividend(
                bucket_id="core",
                amount=amount,
                currency=currency,
                description=f"Dividend from {symbol} (orphaned from {bucket_id})",
            )
            return {
                "source_bucket": bucket_id,
                "destination_bucket": "core",
                "amount": amount,
                "currency": currency,
                "action": "transferred",
                "dividend_handling": "default_to_core",
            }

        # For core bucket, always keep dividends
        if bucket_id == "core":
            await self.balance_service.record_dividend(
                bucket_id="core",
                amount=amount,
                currency=currency,
                description=description or f"Dividend from {symbol}",
            )
            return {
                "source_bucket": "core",
                "destination_bucket": "core",
                "amount": amount,
                "currency": currency,
                "action": "kept",
                "dividend_handling": "core_default",
            }

        # For satellites, get settings to determine routing
        settings = await self.bucket_service.get_settings(bucket_id)
        if not settings:
            logger.warning(
                f"No settings for satellite {bucket_id}, defaulting to send_to_core"
            )
            dividend_handling = "send_to_core"
        else:
            dividend_handling = settings.dividend_handling

        # Route based on setting
        if dividend_handling == "send_to_core":
            # Transfer to core bucket
            await self.balance_service.transfer_between_buckets(
                from_bucket_id=bucket_id,
                to_bucket_id="core",
                amount=amount,
                currency=currency,
                description=f"Dividend from {symbol} (routed to core)",
            )
            logger.info(
                f"Routed dividend from {symbol} in {bucket_id} to core: "
                f"{amount:.2f} {currency}"
            )
            return {
                "source_bucket": bucket_id,
                "destination_bucket": "core",
                "amount": amount,
                "currency": currency,
                "action": "transferred",
                "dividend_handling": dividend_handling,
            }

        else:  # reinvest_same or accumulate_cash
            # Keep in satellite's cash balance
            await self.balance_service.record_dividend(
                bucket_id=bucket_id,
                amount=amount,
                currency=currency,
                description=description
                or f"Dividend from {symbol} (kept in {bucket_id})",
            )
            logger.info(
                f"Kept dividend from {symbol} in {bucket_id}: "
                f"{amount:.2f} {currency} (handling: {dividend_handling})"
            )
            return {
                "source_bucket": bucket_id,
                "destination_bucket": bucket_id,
                "amount": amount,
                "currency": currency,
                "action": "kept",
                "dividend_handling": dividend_handling,
            }

    async def route_dividend_by_position(
        self,
        symbol: str,
        amount: float,
        currency: str,
        payment_date: str,
        description: Optional[str] = None,
    ) -> dict:
        """Route dividend by looking up which bucket owns the position.

        Args:
            symbol: Stock symbol
            amount: Dividend amount
            currency: Currency code
            payment_date: Payment date
            description: Optional description

        Returns:
            Routing details dict
        """
        from app.repositories import PositionRepository

        # Find which bucket owns this position
        position_repo = PositionRepository()
        positions = await position_repo.get_all()

        bucket_id = "core"  # Default to core
        for position in positions:
            if position.symbol == symbol:
                bucket_id = getattr(position, "bucket_id", "core")
                break

        logger.info(
            f"Dividend from {symbol}: {amount:.2f} {currency} → bucket {bucket_id}"
        )

        return await self.route_dividend(
            bucket_id=bucket_id,
            amount=amount,
            currency=currency,
            symbol=symbol,
            payment_date=payment_date,
            description=description,
        )

    async def get_dividend_routing_summary(self, bucket_id: str) -> dict:
        """Get summary of how dividends will be routed for a bucket.

        Args:
            bucket_id: Bucket ID

        Returns:
            Dict with routing configuration and stats
        """
        bucket = await self.bucket_service.get_bucket(bucket_id)
        if not bucket:
            return {"error": "Bucket not found"}

        if bucket_id == "core":
            return {
                "bucket_id": "core",
                "dividend_handling": "core_default",
                "destination": "core",
                "description": "Core bucket keeps all dividends",
            }

        settings = await self.bucket_service.get_settings(bucket_id)
        if not settings:
            return {
                "bucket_id": bucket_id,
                "dividend_handling": "send_to_core",
                "destination": "core",
                "description": "No settings - defaults to sending to core",
            }

        handling = settings.dividend_handling
        destination = "core" if handling == "send_to_core" else bucket_id

        descriptions = {
            "reinvest_same": f"Dividends stay in {bucket_id} for reinvestment in same satellite",
            "send_to_core": "Dividends transferred to core bucket",
            "accumulate_cash": f"Dividends accumulated as cash in {bucket_id}",
        }

        return {
            "bucket_id": bucket_id,
            "dividend_handling": handling,
            "destination": destination,
            "description": descriptions.get(
                handling, f"Dividends handled as: {handling}"
            ),
        }
