"""Helper for calculating rolling cashflow averages."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sentinel.currency import Currency
from sentinel.database import Database
from sentinel.settings import (
    STRATEGY_DEPOSIT_HISTORY_MONTHS_DEFAULT,
    STRATEGY_DEPOSIT_HISTORY_MONTHS_KEY,
    Settings,
    parse_strategy_deposit_history_months,
)


class DepositHistoryHelper:
    """Calculates rolling averages of contribution cashflows."""

    def __init__(
        self,
        db: Database | None = None,
        currency: Currency | None = None,
        settings: Settings | None = None,
    ):
        """Initialize with database and currency service.

        Args:
            db: Database instance (uses singleton if None)
            currency: Currency service (uses singleton if None)
            settings: Settings service (uses singleton if None)
        """
        self._db = db or Database()
        self._currency = currency or Currency()
        self._settings = settings or Settings()

    async def get_window_months(self) -> int:
        """Return the validated contribution-history window."""
        value = await self._settings.get(
            STRATEGY_DEPOSIT_HISTORY_MONTHS_KEY,
            STRATEGY_DEPOSIT_HISTORY_MONTHS_DEFAULT,
        )
        return parse_strategy_deposit_history_months(value) or STRATEGY_DEPOSIT_HISTORY_MONTHS_DEFAULT

    @staticmethod
    def _resolve_window(as_of_date: Optional[str], window_months: int) -> tuple[date, date]:
        if as_of_date is None:
            end_date = date.today()
        elif len(as_of_date) > 10:
            end_date = datetime.fromisoformat(as_of_date).date()
        else:
            end_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()
        return end_date - timedelta(days=30 * window_months), end_date

    async def get_rolling_avg_deposit(
        self,
        as_of_date: Optional[str] = None,
        window_months: int | None = None,
    ) -> float:
        """Average monthly deposit in EUR across the configured history window.

        This is total deposits in the window divided by its number of months — a
        deposit *rate*, not the average size of a single deposit.

        Args:
            as_of_date: Optional date string (YYYY-MM-DD or ISO datetime). Uses current date if None.

        Returns:
            float: Average monthly deposit in EUR, or 0.0 if no deposits found in the window.
        """
        resolved_months = window_months or await self.get_window_months()
        start_date, end_date = self._resolve_window(as_of_date, resolved_months)

        # Fetch cashflows of type 'card' (deposits) in the date range
        cashflows = await self._db.get_cash_flows(
            type_id="card", start_date=start_date.isoformat(), end_date=end_date.isoformat()
        )

        if not cashflows:
            return 0.0

        # Sum all deposits in the window, converted to EUR at each deposit's date.
        total_eur = 0.0
        for cashflow in cashflows:
            amount_eur = await self._currency.to_eur_for_date(
                amount=cashflow["amount"], currency=cashflow["currency"], date=cashflow["date"]
            )
            total_eur += amount_eur

        # Average monthly deposit = total over the window ÷ number of months in the window.
        return total_eur / resolved_months

    async def get_rolling_avg_net_deposit(
        self,
        as_of_date: Optional[str] = None,
        window_months: int | None = None,
    ) -> float:
        """Average monthly net contribution (deposits minus withdrawals) in EUR.

        This is the contribution rate the planner can reasonably project forward:
        card deposits add to the account, card_payout withdrawals reduce the future
        capital base. Dividends, taxes, and fees are intentionally excluded because
        they are already reflected in portfolio value/cash.
        """
        resolved_months = window_months or await self.get_window_months()
        start_date, end_date = self._resolve_window(as_of_date, resolved_months)
        cashflows = await self._db.get_cash_flows(start_date=start_date.isoformat(), end_date=end_date.isoformat())

        total_eur = 0.0
        for cashflow in cashflows:
            type_id = cashflow.get("type_id")
            if type_id not in ("card", "card_payout"):
                continue
            amount_eur = await self._currency.to_eur_for_date(
                amount=cashflow["amount"], currency=cashflow["currency"], date=cashflow["date"]
            )
            if type_id == "card":
                total_eur += amount_eur
            else:
                total_eur -= abs(amount_eur)

        return total_eur / resolved_months

    async def get_rolling_6m_avg_deposit(self, as_of_date: Optional[str] = None) -> float:
        """Compatibility alias for the now-configurable gross contribution rate."""
        return await self.get_rolling_avg_deposit(as_of_date)

    async def get_rolling_6m_avg_net_deposit(self, as_of_date: Optional[str] = None) -> float:
        """Compatibility alias for the now-configurable net contribution rate."""
        return await self.get_rolling_avg_net_deposit(as_of_date)
