"""Tests for DepositHistoryHelper rolling deposit average (real method body)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sentinel.planner.deposit_history import DepositHistoryHelper


def _make_helper(cashflows, rate_eur=1.0, window_months=12):
    """Build a helper with mocked db + currency that exercise the real method."""
    db = MagicMock()
    db.get_cash_flows = AsyncMock(return_value=cashflows)
    currency = MagicMock()
    # Mirror the real conversion: EUR passes through, others use a flat rate.
    currency.to_eur_for_date = AsyncMock(
        side_effect=lambda amount, currency, date: amount if currency == "EUR" else amount * rate_eur
    )
    settings = MagicMock()
    settings.get = AsyncMock(return_value=window_months)
    return DepositHistoryHelper(db=db, currency=currency, settings=settings), db, currency


@pytest.mark.asyncio
async def test_monthly_average_uses_configured_window():
    cashflows = [
        {"amount": 400.0, "currency": "EUR", "date": "2026-01-10"},
        {"amount": 600.0, "currency": "EUR", "date": "2026-02-10"},
    ]
    helper, db, _ = _make_helper(cashflows)

    avg = await helper.get_rolling_avg_deposit(as_of_date="2026-06-09")

    # Monthly RATE = total deposits divided by the configured number of months.
    assert avg == pytest.approx(1000.0 / 12.0)
    db.get_cash_flows.assert_awaited_once_with(type_id="card", start_date="2025-06-14", end_date="2026-06-09")


@pytest.mark.asyncio
async def test_custom_window_changes_range_and_divisor():
    helper, db, _ = _make_helper(
        [{"amount": 600.0, "currency": "EUR", "date": "2026-02-10"}],
        window_months=6,
    )

    avg = await helper.get_rolling_avg_deposit(as_of_date="2026-06-09")

    assert avg == pytest.approx(100.0)
    db.get_cash_flows.assert_awaited_once_with(type_id="card", start_date="2025-12-11", end_date="2026-06-09")


@pytest.mark.asyncio
async def test_converts_foreign_currency_via_rate():
    cashflows = [
        {"amount": 1000.0, "currency": "USD", "date": "2026-03-01"},
        {"amount": 500.0, "currency": "EUR", "date": "2026-03-02"},
    ]
    helper, _, currency = _make_helper(cashflows, rate_eur=0.9)

    avg = await helper.get_rolling_avg_deposit(as_of_date="2026-06-09")

    assert avg == pytest.approx((1000.0 * 0.9 + 500.0) / 12.0)
    # Conversion is called with the historical cashflow date.
    currency.to_eur_for_date.assert_any_await(amount=1000.0, currency="USD", date="2026-03-01")


@pytest.mark.asyncio
async def test_no_deposits_returns_zero():
    helper, _, currency = _make_helper([])

    avg = await helper.get_rolling_avg_deposit(as_of_date="2026-06-09")

    assert avg == 0.0
    # No conversion attempted when there are no cashflows.
    currency.to_eur_for_date.assert_not_awaited()


@pytest.mark.asyncio
async def test_monthly_net_deposit_subtracts_withdrawals():
    cashflows = [
        {"type_id": "card", "amount": 3000.0, "currency": "EUR", "date": "2026-01-10"},
        {"type_id": "card", "amount": 3000.0, "currency": "EUR", "date": "2026-02-10"},
        {"type_id": "card_payout", "amount": -1000.0, "currency": "EUR", "date": "2026-01-20"},
        {"type_id": "card_payout", "amount": 1000.0, "currency": "EUR", "date": "2026-02-20"},
        {"type_id": "dividend", "amount": 999.0, "currency": "EUR", "date": "2026-03-01"},
    ]
    helper, db, _ = _make_helper(cashflows)

    avg = await helper.get_rolling_avg_net_deposit(as_of_date="2026-06-09")

    assert avg == pytest.approx((3000.0 + 3000.0 - 1000.0 - 1000.0) / 12.0)
    db.get_cash_flows.assert_awaited_once_with(start_date="2025-06-14", end_date="2026-06-09")


@pytest.mark.asyncio
async def test_accepts_iso_datetime_as_of_date():
    cashflows = [{"amount": 300.0, "currency": "EUR", "date": "2026-04-01"}]
    helper, db, _ = _make_helper(cashflows)

    avg = await helper.get_rolling_avg_deposit(as_of_date="2026-06-09T14:30:00")

    assert avg == pytest.approx(300.0 / 12.0)
    # ISO datetime is collapsed to its date for the window.
    db.get_cash_flows.assert_awaited_once_with(type_id="card", start_date="2025-06-14", end_date="2026-06-09")


@pytest.mark.asyncio
async def test_defaults_to_today_when_no_date():
    helper, db, _ = _make_helper([])

    await helper.get_rolling_avg_deposit()

    # Window is anchored on a real date (today) — just assert the call shape.
    db.get_cash_flows.assert_awaited_once()
    kwargs = db.get_cash_flows.await_args.kwargs
    assert kwargs["type_id"] == "card"
    assert kwargs["start_date"] < kwargs["end_date"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_value", [True, 0, 37, 1.5, "12"])
async def test_invalid_stored_window_falls_back_to_default(stored_value):
    helper, _, _ = _make_helper([], window_months=stored_value)

    assert await helper.get_window_months() == 12
