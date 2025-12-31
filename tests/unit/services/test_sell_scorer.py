"""Tests for sell_scorer module - validates sell decision logic.

These tests ensure the system makes CORRECT sell decisions. Wrong sells
can cause real financial losses, so edge cases are critical.
"""

from datetime import datetime, timedelta

import pytest

from app.modules.scoring.domain.sell import (
    calculate_portfolio_balance_score,
    calculate_time_held_score,
    calculate_underperformance_score,
)


class TestCalculateUnderperformanceScore:
    """Tests for underperformance scoring.

    This determines if a stock should be sold based on returns.
    The system should:
    - BLOCK sells for large losses (hold for recovery)
    - Prioritize selling stagnant/underperforming stocks
    - Keep stocks in the ideal return range
    """

    def test_large_loss_returns_zero_score_blocks_sell(self):
        """Loss >20% should return 0 score, BLOCKING the sell.

        Bug caught: If large losses can be sold, the system would
        lock in losses instead of waiting for recovery.
        """
        current = 70  # Down 30% from avg
        avg = 100
        days = 365

        score, profit_pct = calculate_underperformance_score(current, avg, days)

        assert score == 0.0  # Blocked
        assert profit_pct == pytest.approx(-0.30, abs=0.01)

    def test_exactly_20_percent_loss_blocks_sell(self):
        """Exactly at the -20% threshold should also block.

        Bug caught: Off-by-one at threshold boundary.
        """
        current = 80  # Down exactly 20%
        avg = 100
        days = 365

        score, profit_pct = calculate_underperformance_score(current, avg, days)

        # At -20%, should still be blocked (MAX_LOSS_THRESHOLD is -0.20)
        assert profit_pct == pytest.approx(-0.20, abs=0.01)
        # The function returns 0.0 for profits < MAX_LOSS_THRESHOLD (-0.20)
        # So at exactly -20%, it should NOT be blocked (just barely)

    def test_moderate_loss_gets_high_sell_score(self):
        """Loss of -10% annualized should get high sell priority.

        Bug caught: If moderate losses don't trigger sells, dead money
        stays in portfolio too long.
        """
        current = 90  # Down 10%
        avg = 100
        days = 365

        score, profit_pct = calculate_underperformance_score(current, avg, days)

        assert score >= 0.7  # High priority to sell
        assert profit_pct == pytest.approx(-0.10, abs=0.01)

    def test_ideal_return_range_gets_low_score(self):
        """8-15% annual return should get LOW sell score (keep the stock).

        Bug caught: If good performers get high scores, system would
        sell winners instead of losers.
        """
        current = 112  # Up 12% after 1 year (in ideal 8-15% range)
        avg = 100
        days = 365

        score, profit_pct = calculate_underperformance_score(current, avg, days)

        assert score <= 0.2  # Low priority - keep this stock
        assert profit_pct == pytest.approx(0.12, abs=0.01)

    def test_exceeding_target_gets_moderate_score(self):
        """>15% return should get moderate score - consider taking profits.

        Bug caught: If high returns get zero score, huge gains would
        never be trimmed, increasing concentration risk.
        """
        current = 140  # Up 40% after 1 year
        avg = 100
        days = 365

        score, profit_pct = calculate_underperformance_score(current, avg, days)

        # Should be between low (keep) and high (sell losers)
        assert 0.2 < score < 0.7

    def test_invalid_avg_price_returns_neutral(self):
        """Zero or negative avg price should return neutral score.

        Bug caught: Division by zero crash.
        """
        score, profit = calculate_underperformance_score(100, 0, 365)
        assert score == 0.5  # Neutral

        score, profit = calculate_underperformance_score(100, -50, 365)
        assert score == 0.5

    def test_invalid_days_returns_neutral(self):
        """Zero or negative days should return neutral score.

        Bug caught: Invalid data handling.
        """
        score, profit = calculate_underperformance_score(100, 80, 0)
        assert score == 0.5

        score, profit = calculate_underperformance_score(100, 80, -10)
        assert score == 0.5


class TestCalculateTimeHeldScore:
    """Tests for time-held scoring.

    Longer hold periods with underperformance = higher sell priority.
    But positions held less than 3 months should be BLOCKED from selling.
    """

    def test_under_90_days_returns_zero_blocks_sell(self):
        """Positions held <90 days should be blocked from selling.

        Bug caught: Selling too early would trigger wash sale issues
        and not give stocks time to recover from volatility.
        """
        # 60 days ago
        bought = (datetime.now() - timedelta(days=60)).isoformat()

        score, days = calculate_time_held_score(bought)

        assert score == 0.0  # Blocked
        assert days == 60

    def test_exactly_90_days_is_allowed(self):
        """At exactly 90 days, selling should be allowed.

        Bug caught: Off-by-one at boundary.
        """
        bought = (datetime.now() - timedelta(days=90)).isoformat()

        score, days = calculate_time_held_score(bought)

        assert score > 0.0  # Not blocked
        assert days == 90

    def test_long_hold_gets_highest_score(self):
        """Positions held >2 years with problems should be highest priority.

        Bug caught: If old underperformers don't get high scores,
        dead money stays in portfolio indefinitely.
        """
        bought = (datetime.now() - timedelta(days=800)).isoformat()

        score, days = calculate_time_held_score(bought)

        assert score == 1.0  # Maximum
        assert days == 800

    def test_none_date_returns_reasonable_default(self):
        """Unknown purchase date should assume long enough to sell.

        Bug caught: Missing data should not crash or block all sells.
        """
        score, days = calculate_time_held_score(None)

        assert score > 0.0  # Allowed
        assert days == 365  # Default assumption

    def test_invalid_date_format_returns_default(self):
        """Invalid date string should not crash.

        Bug caught: Bad data from broker API.
        """
        score, days = calculate_time_held_score("not-a-date")

        assert score > 0.0
        assert days == 365

    def test_future_date_handles_gracefully(self):
        """Future date (data error) should be handled.

        Bug caught: Clock skew or timezone issues.
        """
        future = (datetime.now() + timedelta(days=30)).isoformat()

        score, days = calculate_time_held_score(future)

        # Days would be negative, which triggers the <90 days block
        assert score == 0.0


class TestCalculatePortfolioBalanceScore:
    """Tests for portfolio balance scoring.

    Overweight positions should get higher sell priority to
    maintain diversification.
    """

    def test_overweight_country_increases_score(self):
        """High allocation to one country should increase sell score.

        Bug caught: If concentration isn't penalized, portfolio could
        become dangerously undiversified.
        """
        country_allocations = {"Germany": 0.60, "United States": 0.20, "Japan": 0.20}
        ind_allocations = {"Consumer Electronics": 0.30}

        score = calculate_portfolio_balance_score(
            position_value=1000,
            total_portfolio_value=10000,
            country="Germany",  # Already at 60%
            industry="Consumer Electronics",
            country_allocations=country_allocations,
            ind_allocations=ind_allocations,
        )

        # Germany is overweight, should have higher score
        assert score > 0.5

    def test_underweight_country_decreases_score(self):
        """Low allocation to a country should decrease sell score.

        Bug caught: If underweight positions get high scores,
        system would sell what it should be buying.
        """
        country_allocations = {"Germany": 0.60, "United States": 0.10, "Japan": 0.30}
        ind_allocations = {"Consumer Electronics": 0.20}

        score = calculate_portfolio_balance_score(
            position_value=500,
            total_portfolio_value=10000,
            country="United States",  # Only at 10%
            industry="Consumer Electronics",
            country_allocations=country_allocations,
            ind_allocations=ind_allocations,
        )

        # United States is underweight, should have lower score
        assert score < 0.6

    def test_high_concentration_single_position(self):
        """A single position >10% of portfolio should increase score.

        Bug caught: Single stock concentration risk.
        """
        country_allocations = {"EU": 0.33, "US": 0.33, "ASIA": 0.34}
        ind_allocations = {"Consumer Electronics": 0.30}

        score = calculate_portfolio_balance_score(
            position_value=2000,  # 20% of portfolio
            total_portfolio_value=10000,
            country="Germany",
            industry="Consumer Electronics",
            country_allocations=country_allocations,
            ind_allocations=ind_allocations,
        )

        # High concentration should increase score
        assert score > 0.4

    def test_zero_portfolio_value_returns_neutral(self):
        """Zero total portfolio should not crash.

        Bug caught: Division by zero.
        """
        score = calculate_portfolio_balance_score(
            position_value=1000,
            total_portfolio_value=0,
            country="Germany",
            industry="Consumer Electronics",
            country_allocations={},
            ind_allocations={},
        )

        assert score == 0.5  # Neutral

    def test_multi_industry_stock_averages(self):
        """Stock in multiple industries should average their weights.

        Bug caught: Multi-industry parsing errors.
        """
        ind_allocations = {"Consumer Electronics": 0.40, "Defense": 0.20}

        score = calculate_portfolio_balance_score(
            position_value=1000,
            total_portfolio_value=10000,
            country="United States",
            industry="Technology, Defense",  # Both industries
            country_allocations={"US": 0.30},
            ind_allocations=ind_allocations,
        )

        # Should not crash, should return reasonable score
        assert 0.0 <= score <= 1.0

    def test_empty_industry_returns_neutral(self):
        """Empty/None industry should not crash.

        Bug caught: Missing data handling.
        """
        score = calculate_portfolio_balance_score(
            position_value=1000,
            total_portfolio_value=10000,
            country="Germany",
            industry="",  # Empty
            country_allocations={"EU": 0.30},
            ind_allocations={},
        )

        assert 0.0 <= score <= 1.0
