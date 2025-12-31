"""Reconciliation service - ensures virtual balances match actual brokerage balances."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from app.modules.satellites.database.balance_repository import BalanceRepository
from app.modules.satellites.database.bucket_repository import BucketRepository
from app.modules.satellites.domain.enums import TransactionType
from app.modules.satellites.domain.models import BucketTransaction

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationResult:
    """Result of a reconciliation check or operation."""

    currency: str
    virtual_total: float
    actual_total: float
    difference: float
    is_reconciled: bool
    adjustments_made: Dict[str, float]  # bucket_id -> adjustment
    timestamp: str

    @property
    def difference_pct(self) -> float:
        """Get difference as percentage of actual."""
        if self.actual_total == 0:
            return 0.0 if self.virtual_total == 0 else float("inf")
        return abs(self.difference) / self.actual_total


class ReconciliationService:
    """Service for reconciling virtual balances with brokerage reality.

    The critical invariant this service maintains:
    SUM(bucket_balances for currency X) == Actual brokerage balance for currency X

    Reconciliation can happen:
    1. On startup - verify state
    2. Periodically - catch drift
    3. After significant operations - immediate verification
    """

    # Threshold below which differences are auto-corrected (rounding errors)
    # Increased to €5 to handle accumulated rounding across multiple trades
    AUTO_CORRECT_THRESHOLD = 5.0  # 5 EUR/USD

    def __init__(
        self,
        balance_repo: Optional[BalanceRepository] = None,
        bucket_repo: Optional[BucketRepository] = None,
    ):
        self._balance_repo = balance_repo or BalanceRepository()
        self._bucket_repo = bucket_repo or BucketRepository()

    async def check_invariant(
        self,
        currency: str,
        actual_balance: float,
    ) -> ReconciliationResult:
        """Check if virtual balances match actual brokerage balance.

        Args:
            currency: Currency to check
            actual_balance: Actual balance from brokerage

        Returns:
            ReconciliationResult with check details
        """
        virtual_total = await self._balance_repo.get_total_by_currency(currency)
        difference = virtual_total - actual_balance

        return ReconciliationResult(
            currency=currency.upper(),
            virtual_total=virtual_total,
            actual_total=actual_balance,
            difference=difference,
            is_reconciled=abs(difference) < 0.01,  # Allow 1 cent tolerance
            adjustments_made={},
            timestamp=datetime.now().isoformat(),
        )

    async def reconcile(
        self,
        currency: str,
        actual_balance: float,
        auto_correct_threshold: Optional[float] = None,
    ) -> ReconciliationResult:
        """Reconcile virtual balances with actual brokerage balance.

        If there's a discrepancy:
        1. Small differences (< threshold) are auto-corrected to core
        2. Large differences log a warning and require manual intervention

        Args:
            currency: Currency to reconcile
            actual_balance: Actual balance from brokerage
            auto_correct_threshold: Max difference to auto-correct (default: 1.0)

        Returns:
            ReconciliationResult with reconciliation details
        """
        threshold = (
            auto_correct_threshold
            if auto_correct_threshold is not None
            else self.AUTO_CORRECT_THRESHOLD
        )

        # Check current state
        result = await self.check_invariant(currency, actual_balance)

        if result.is_reconciled:
            logger.debug(f"Reconciliation check passed for {currency}")
            return result

        difference = result.difference
        adjustments = {}

        if abs(difference) <= threshold:
            # Auto-correct small differences by adjusting core
            adjustment = -difference  # If virtual > actual, reduce core

            await self._balance_repo.adjust_balance("core", currency, adjustment)

            # Record adjustment transaction
            tx = BucketTransaction(
                bucket_id="core",
                type=TransactionType.REALLOCATION,
                amount=adjustment,
                currency=currency.upper(),
                description=f"Reconciliation adjustment ({difference:+.2f} discrepancy)",
            )
            await self._balance_repo.record_transaction(tx)

            adjustments["core"] = adjustment
            logger.info(
                f"Auto-corrected {currency} discrepancy of {difference:+.2f} "
                f"by adjusting core balance"
            )

            result.adjustments_made = adjustments
            result.is_reconciled = True
        else:
            # Large discrepancy - log warning
            logger.warning(
                f"Large {currency} discrepancy detected: "
                f"virtual={result.virtual_total:.2f}, "
                f"actual={result.actual_total:.2f}, "
                f"diff={difference:+.2f}. "
                f"Manual intervention required."
            )

        return result

    async def reconcile_all(
        self,
        actual_balances: Dict[str, float],
        auto_correct_threshold: Optional[float] = None,
    ) -> List[ReconciliationResult]:
        """Reconcile all currencies.

        Args:
            actual_balances: Dict of currency -> actual balance
            auto_correct_threshold: Max difference to auto-correct

        Returns:
            List of reconciliation results
        """
        results = []
        for currency, actual_balance in actual_balances.items():
            result = await self.reconcile(
                currency, actual_balance, auto_correct_threshold
            )
            results.append(result)
        return results

    async def get_balance_breakdown(self, currency: str) -> Dict[str, float]:
        """Get breakdown of virtual balances by bucket.

        Useful for debugging reconciliation issues.

        Args:
            currency: Currency to break down

        Returns:
            Dict of bucket_id -> balance
        """
        buckets = await self._bucket_repo.get_all()
        breakdown = {}

        for bucket in buckets:
            balance = await self._balance_repo.get_balance_amount(bucket.id, currency)
            if balance != 0:
                breakdown[bucket.id] = balance

        return breakdown

    async def initialize_from_brokerage(
        self,
        actual_balances: Dict[str, float],
    ) -> List[ReconciliationResult]:
        """Initialize virtual balances from actual brokerage state.

        Used on first startup or after a reset. All balances go to core.

        Args:
            actual_balances: Dict of currency -> actual balance

        Returns:
            List of reconciliation results showing initial state
        """
        results = []

        for currency, actual_balance in actual_balances.items():
            # Check if we have any virtual balances
            virtual_total = await self._balance_repo.get_total_by_currency(currency)

            if virtual_total == 0 and actual_balance > 0:
                # Initialize core with full balance
                await self._balance_repo.set_balance("core", currency, actual_balance)

                tx = BucketTransaction(
                    bucket_id="core",
                    type=TransactionType.DEPOSIT,
                    amount=actual_balance,
                    currency=currency.upper(),
                    description="Initial balance from brokerage",
                )
                await self._balance_repo.record_transaction(tx)

                logger.info(
                    f"Initialized core {currency} balance to {actual_balance:.2f}"
                )

            # Verify reconciliation
            result = await self.check_invariant(currency, actual_balance)
            results.append(result)

        return results

    async def force_reconcile_to_core(
        self,
        currency: str,
        actual_balance: float,
    ) -> ReconciliationResult:
        """Force reconciliation by adjusting core balance.

        WARNING: This should only be used when you're certain the
        actual brokerage balance is correct and virtual balances
        have drifted. It will overwrite core balance.

        Args:
            currency: Currency to force reconcile
            actual_balance: Actual brokerage balance

        Returns:
            ReconciliationResult
        """
        # Get sum of all non-core balances
        buckets = await self._bucket_repo.get_all()
        non_core_total = 0.0

        for bucket in buckets:
            if bucket.id != "core":
                balance = await self._balance_repo.get_balance_amount(
                    bucket.id, currency
                )
                non_core_total += balance

        # Core should be actual minus all satellites
        core_should_be = actual_balance - non_core_total

        # Get current core balance
        current_core = await self._balance_repo.get_balance_amount("core", currency)
        adjustment = core_should_be - current_core

        if abs(adjustment) > 0.01:
            await self._balance_repo.set_balance("core", currency, core_should_be)

            tx = BucketTransaction(
                bucket_id="core",
                type=TransactionType.REALLOCATION,
                amount=adjustment,
                currency=currency.upper(),
                description=f"Force reconciliation (adjusted from {current_core:.2f})",
            )
            await self._balance_repo.record_transaction(tx)

            logger.warning(
                f"Force reconciled {currency}: "
                f"adjusted core from {current_core:.2f} to {core_should_be:.2f}"
            )

        return ReconciliationResult(
            currency=currency.upper(),
            virtual_total=actual_balance,
            actual_total=actual_balance,
            difference=0.0,
            is_reconciled=True,
            adjustments_made={"core": adjustment} if abs(adjustment) > 0.01 else {},
            timestamp=datetime.now().isoformat(),
        )

    async def diagnose_discrepancy(
        self,
        currency: str,
        actual_balance: float,
    ) -> Dict:
        """Diagnose a balance discrepancy.

        Provides detailed information for debugging.

        Args:
            currency: Currency with discrepancy
            actual_balance: Actual brokerage balance

        Returns:
            Dict with diagnostic information
        """
        # Get breakdown
        breakdown = await self.get_balance_breakdown(currency)
        virtual_total = sum(breakdown.values())

        # Get recent transactions
        all_transactions = []
        for bucket_id in breakdown.keys():
            txs = await self._balance_repo.get_recent_transactions(bucket_id, days=7)
            for tx in txs:
                all_transactions.append(
                    {
                        "bucket_id": tx.bucket_id,
                        "type": tx.type.value,
                        "amount": tx.amount,
                        "currency": tx.currency,
                        "created_at": tx.created_at,
                        "description": tx.description,
                    }
                )

        # Sort by time
        all_transactions.sort(key=lambda x: x["created_at"] or "", reverse=True)

        return {
            "currency": currency,
            "actual_balance": actual_balance,
            "virtual_total": virtual_total,
            "difference": virtual_total - actual_balance,
            "breakdown": breakdown,
            "recent_transactions": all_transactions[:20],  # Last 20
            "timestamp": datetime.now().isoformat(),
        }
