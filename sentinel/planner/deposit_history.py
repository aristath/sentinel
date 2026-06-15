"""Helper for calculating rolling cashflow averages."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sentinel.currency import Currency
from sentinel.database import Database


class DepositHistoryHelper:
    """Calculates rolling averages of contribution cashflows."""

    def __init__(self, db: Database | None = None, currency: Currency | None = None):
        """Initialize with database and currency service.

        Args:
            db: Database instance (uses singleton if None)
            currency: Currency service (uses singleton if None)
        """
        self._db = db or Database()
        self._currency = currency or Currency()

    WINDOW_MONTHS = 6

    @staticmethod
    def _resolve_window(as_of_date: Optional[str]) -> tuple[date, date]:
        if as_of_date is None:
            end_date = date.today()
        elif len(as_of_date) > 10:
            end_date = datetime.fromisoformat(as_of_date).date()
        else:
            end_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()
        return end_date - timedelta(days=30 * DepositHistoryHelper.WINDOW_MONTHS), end_date

    async def get_rolling_6m_avg_deposit(self, as_of_date: Optional[str] = None) -> float:
        """Average **monthly** deposit (EUR) across the trailing 6 months.

        This is total deposits in the window divided by 6 months — a deposit *rate*, not
        the average size of a single deposit. Callers divide a EUR amount by this to get a
        number of months (e.g. months-to-fund), so the unit must be EUR/month regardless of
        how many individual deposits landed.

        Args:
            as_of_date: Optional date string (YYYY-MM-DD or ISO datetime). Uses current date if None.

        Returns:
            float: Average monthly deposit in EUR, or 0.0 if no deposits found in the window.
        """
        start_date, end_date = self._resolve_window(as_of_date)

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
        return total_eur / self.WINDOW_MONTHS

    async def get_rolling_6m_avg_net_deposit(self, as_of_date: Optional[str] = None) -> float:
        """Average monthly net contribution (deposits minus withdrawals) in EUR.

        This is the contribution rate the planner can reasonably project forward:
        card deposits add to the account, card_payout withdrawals reduce the future
        capital base. Dividends, taxes, and fees are intentionally excluded because
        they are already reflected in portfolio value/cash.
        """
        start_date, end_date = self._resolve_window(as_of_date)
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

        return total_eur / self.WINDOW_MONTHS
