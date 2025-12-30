"""Tests for API Pydantic models.

These tests validate Pydantic model validation, field constraints,
serialization, and deserialization for all API request/response models.
"""

import pytest
from pydantic import ValidationError

from app.api.models import (
    AttributionData,
    CashBalance,
    CashBreakdownResponse,
    DailyReturn,
    DatabaseSize,
    DatabaseStatsResponse,
    DiskUsageResponse,
    JobsStatusResponse,
    JobStatus,
    MarketsStatusResponse,
    MarketStatus,
    MonthlyReturn,
    PeriodInfo,
    PortfolioAnalyticsErrorResponse,
    PortfolioAnalyticsResponse,
    PortfolioPosition,
    PortfolioSummary,
    ReturnsData,
    RiskMetrics,
    StatusResponse,
    TurnoverInfo,
)


class TestPortfolioPosition:
    """Test PortfolioPosition model."""

    def test_valid_creation(self):
        """Test valid PortfolioPosition creation."""
        position = PortfolioPosition(
            symbol="AAPL.US",
            name="Apple Inc.",
            quantity=10.0,
            avg_price=150.0,
            current_price=160.0,
            market_value=1600.0,
            market_value_eur=1680.0,
            unrealized_pnl=100.0,
            currency="USD",
            currency_rate=1.05,
        )

        assert position.symbol == "AAPL.US"
        assert position.name == "Apple Inc."
        assert position.quantity == 10.0
        assert position.avg_price == 150.0

    def test_validates_required_fields(self):
        """Test that all required fields are validated."""
        with pytest.raises(ValidationError) as exc_info:
            PortfolioPosition(
                symbol="AAPL.US",
                # Missing required fields
            )

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_accepts_zero_quantity(self):
        """Test that zero quantity is accepted."""
        position = PortfolioPosition(
            symbol="AAPL.US",
            name="Apple Inc.",
            quantity=0.0,
            avg_price=150.0,
            current_price=160.0,
            market_value=0.0,
            market_value_eur=0.0,
            unrealized_pnl=0.0,
            currency="USD",
            currency_rate=1.05,
        )

        assert position.quantity == 0.0

    def test_handles_negative_values(self):
        """Test handling of negative values (e.g., unrealized_pnl can be negative)."""
        position = PortfolioPosition(
            symbol="AAPL.US",
            name="Apple Inc.",
            quantity=10.0,
            avg_price=150.0,
            current_price=140.0,
            market_value=1400.0,
            market_value_eur=1470.0,
            unrealized_pnl=-100.0,  # Negative PnL
            currency="USD",
            currency_rate=1.05,
        )

        assert position.unrealized_pnl == -100.0


class TestPortfolioSummary:
    """Test PortfolioSummary model."""

    def test_valid_creation(self):
        """Test valid PortfolioSummary creation."""
        summary = PortfolioSummary(
            total_value=10000.0,
            invested_value=9000.0,
            unrealized_pnl=1000.0,
            cash_balance=5000.0,
            position_count=5,
        )

        assert summary.total_value == 10000.0
        assert summary.position_count == 5

    def test_validates_required_fields(self):
        """Test that all required fields are validated."""
        with pytest.raises(ValidationError):
            PortfolioSummary(
                total_value=10000.0,
                # Missing required fields
            )


class TestCashBalance:
    """Test CashBalance model."""

    def test_valid_creation(self):
        """Test valid CashBalance creation."""
        balance = CashBalance(currency="EUR", amount=1000.0)

        assert balance.currency == "EUR"
        assert balance.amount == 1000.0

    def test_accepts_negative_amount(self):
        """Test that negative amounts are accepted (for negative balances)."""
        balance = CashBalance(currency="USD", amount=-100.0)

        assert balance.amount == -100.0


class TestCashBreakdownResponse:
    """Test CashBreakdownResponse model."""

    def test_valid_creation(self):
        """Test valid CashBreakdownResponse creation."""
        response = CashBreakdownResponse(
            balances=[
                CashBalance(currency="EUR", amount=1000.0),
                CashBalance(currency="USD", amount=500.0),
            ],
            total_eur=1500.0,
        )

        assert len(response.balances) == 2
        assert response.total_eur == 1500.0

    def test_accepts_empty_balances(self):
        """Test that empty balances list is accepted."""
        response = CashBreakdownResponse(balances=[], total_eur=0.0)

        assert len(response.balances) == 0
        assert response.total_eur == 0.0


class TestDailyReturn:
    """Test DailyReturn model."""

    def test_valid_creation(self):
        """Test valid DailyReturn creation."""
        daily_return = DailyReturn(date="2024-01-15", return_=0.05)

        assert daily_return.date == "2024-01-15"
        assert daily_return.return_ == 0.05

    def test_accepts_negative_returns(self):
        """Test that negative returns are accepted."""
        daily_return = DailyReturn(date="2024-01-15", return_=-0.03)

        assert daily_return.return_ == -0.03

    def test_serializes_with_alias(self):
        """Test that serialization uses 'return' alias."""
        daily_return = DailyReturn(date="2024-01-15", return_=0.05)
        data = daily_return.model_dump(by_alias=True)

        assert "return" in data
        assert data["return"] == 0.05
        assert "return_" not in data


class TestMonthlyReturn:
    """Test MonthlyReturn model."""

    def test_valid_creation(self):
        """Test valid MonthlyReturn creation."""
        monthly_return = MonthlyReturn(month="2024-01", return_=0.15)

        assert monthly_return.month == "2024-01"
        assert monthly_return.return_ == 0.15


class TestReturnsData:
    """Test ReturnsData model."""

    def test_valid_creation(self):
        """Test valid ReturnsData creation."""
        returns_data = ReturnsData(
            daily=[
                DailyReturn(date="2024-01-15", return_=0.05),
                DailyReturn(date="2024-01-16", return_=-0.02),
            ],
            monthly=[
                MonthlyReturn(month="2024-01", return_=0.15),
            ],
            annual=0.25,
        )

        assert len(returns_data.daily) == 2
        assert len(returns_data.monthly) == 1
        assert returns_data.annual == 0.25


class TestRiskMetrics:
    """Test RiskMetrics model."""

    def test_valid_creation(self):
        """Test valid RiskMetrics creation."""
        risk = RiskMetrics(
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=0.8,
            volatility=0.20,
            max_drawdown=0.15,
        )

        assert risk.sharpe_ratio == 1.5
        assert risk.max_drawdown == 0.15

    def test_accepts_negative_ratios(self):
        """Test that negative ratios are accepted."""
        risk = RiskMetrics(
            sharpe_ratio=-0.5,
            sortino_ratio=-0.3,
            calmar_ratio=-0.2,
            volatility=0.25,
            max_drawdown=0.20,
        )

        assert risk.sharpe_ratio == -0.5


class TestAttributionData:
    """Test AttributionData model."""

    def test_valid_creation(self):
        """Test valid AttributionData creation."""
        attribution = AttributionData(
            country={"US": 0.5, "EU": 0.3},
            industry={"Tech": 0.4, "Finance": 0.2},
        )

        assert attribution.country["US"] == 0.5
        assert attribution.industry["Tech"] == 0.4


class TestPeriodInfo:
    """Test PeriodInfo model."""

    def test_valid_creation(self):
        """Test valid PeriodInfo creation."""
        period = PeriodInfo(
            start_date="2024-01-01",
            end_date="2024-12-31",
            days=365,
        )

        assert period.start_date == "2024-01-01"
        assert period.days == 365

    def test_accepts_zero_days(self):
        """Test that zero days is accepted."""
        period = PeriodInfo(
            start_date="2024-01-01",
            end_date="2024-01-01",
            days=0,
        )

        assert period.days == 0


class TestTurnoverInfo:
    """Test TurnoverInfo model."""

    def test_valid_creation_with_turnover(self):
        """Test valid TurnoverInfo creation with turnover."""
        turnover = TurnoverInfo(
            annual_turnover=0.5,
            turnover_display="50%",
            status="normal",
            reason="Within normal range",
        )

        assert turnover.annual_turnover == 0.5
        assert turnover.status == "normal"

    def test_valid_creation_without_turnover(self):
        """Test valid TurnoverInfo creation without turnover (None)."""
        turnover = TurnoverInfo(
            annual_turnover=None,
            turnover_display="N/A",
            status="insufficient_data",
            reason="Not enough data",
        )

        assert turnover.annual_turnover is None
        assert turnover.status == "insufficient_data"

    def test_validates_required_fields(self):
        """Test that required fields are validated."""
        with pytest.raises(ValidationError):
            TurnoverInfo(
                annual_turnover=0.5,
                # Missing required fields
            )


class TestPortfolioAnalyticsResponse:
    """Test PortfolioAnalyticsResponse model."""

    def test_valid_creation(self):
        """Test valid PortfolioAnalyticsResponse creation."""
        response = PortfolioAnalyticsResponse(
            returns=ReturnsData(
                daily=[],
                monthly=[],
                annual=0.25,
            ),
            risk_metrics=RiskMetrics(
                sharpe_ratio=1.5,
                sortino_ratio=2.0,
                calmar_ratio=0.8,
                volatility=0.20,
                max_drawdown=0.15,
            ),
            attribution=AttributionData(
                country={},
                industry={},
            ),
            period=PeriodInfo(
                start_date="2024-01-01",
                end_date="2024-12-31",
                days=365,
            ),
        )

        assert response.returns.annual == 0.25
        assert response.turnover is None

    def test_accepts_optional_turnover(self):
        """Test that optional turnover is accepted."""
        response = PortfolioAnalyticsResponse(
            returns=ReturnsData(
                daily=[],
                monthly=[],
                annual=0.25,
            ),
            risk_metrics=RiskMetrics(
                sharpe_ratio=1.5,
                sortino_ratio=2.0,
                calmar_ratio=0.8,
                volatility=0.20,
                max_drawdown=0.15,
            ),
            attribution=AttributionData(
                country={},
                industry={},
            ),
            period=PeriodInfo(
                start_date="2024-01-01",
                end_date="2024-12-31",
                days=365,
            ),
            turnover=TurnoverInfo(
                annual_turnover=0.5,
                turnover_display="50%",
                status="normal",
                reason="OK",
            ),
        )

        assert response.turnover is not None
        assert response.turnover.annual_turnover == 0.5


class TestPortfolioAnalyticsErrorResponse:
    """Test PortfolioAnalyticsErrorResponse model."""

    def test_valid_creation(self):
        """Test valid PortfolioAnalyticsErrorResponse creation."""
        response = PortfolioAnalyticsErrorResponse(
            error="Calculation failed",
            returns={},
            risk_metrics={},
            attribution={},
        )

        assert response.error == "Calculation failed"
        assert response.returns == {}


class TestStatusResponse:
    """Test StatusResponse model."""

    def test_valid_creation(self):
        """Test valid StatusResponse creation."""
        response = StatusResponse(
            status="ok",
            last_sync="2024-01-15T10:00:00",
            stock_universe_count=100,
            active_positions=5,
            cash_balance=5000.0,
            check_interval_minutes=5,
        )

        assert response.status == "ok"
        assert response.stock_universe_count == 100

    def test_accepts_none_last_sync(self):
        """Test that None last_sync is accepted."""
        response = StatusResponse(
            status="ok",
            last_sync=None,
            stock_universe_count=0,
            active_positions=0,
            cash_balance=0.0,
            check_interval_minutes=5,
        )

        assert response.last_sync is None


class TestDatabaseSize:
    """Test DatabaseSize model."""

    def test_valid_creation(self):
        """Test valid DatabaseSize creation."""
        db_size = DatabaseSize(name="config.db", size_mb=1.5)

        assert db_size.name == "config.db"
        assert db_size.size_mb == 1.5

    def test_accepts_zero_size(self):
        """Test that zero size is accepted."""
        db_size = DatabaseSize(name="empty.db", size_mb=0.0)

        assert db_size.size_mb == 0.0


class TestDatabaseStatsResponse:
    """Test DatabaseStatsResponse model."""

    def test_valid_creation(self):
        """Test valid DatabaseStatsResponse creation with extra fields."""
        response = DatabaseStatsResponse(
            status="ok",
            total_size=100.0,
            db_count=5,
        )

        assert response.status == "ok"
        assert response.total_size == 100.0  # Extra field allowed
        assert response.db_count == 5  # Extra field allowed


class TestMarketStatus:
    """Test MarketStatus model."""

    def test_valid_creation(self):
        """Test valid MarketStatus creation."""
        market = MarketStatus(
            geography="US",
            is_open=True,
            timezone="America/New_York",
        )

        assert market.geography == "US"
        assert market.is_open is True

    def test_accepts_closed_market(self):
        """Test that closed market status is accepted."""
        market = MarketStatus(
            geography="EU",
            is_open=False,
            timezone="Europe/London",
        )

        assert market.is_open is False


class TestMarketsStatusResponse:
    """Test MarketsStatusResponse model."""

    def test_valid_creation(self):
        """Test valid MarketsStatusResponse creation."""
        response = MarketsStatusResponse(
            status="ok",
            open_markets=["US", "EU"],
            markets={
                "US": {"is_open": True, "timezone": "America/New_York"},
                "EU": {"is_open": False, "timezone": "Europe/London"},
            },
        )

        assert response.status == "ok"
        assert len(response.open_markets) == 2
        assert "US" in response.markets


class TestDiskUsageResponse:
    """Test DiskUsageResponse model."""

    def test_valid_creation(self):
        """Test valid DiskUsageResponse creation."""
        response = DiskUsageResponse(
            status="ok",
            disk={"total": 1000.0, "used": 500.0},
            databases={"config.db": 1.5},
            data_directory={"size": 100.0},
            backups={"count": 5},
        )

        assert response.status == "ok"
        assert response.disk["total"] == 1000.0


class TestJobStatus:
    """Test JobStatus model."""

    def test_valid_creation(self):
        """Test valid JobStatus creation."""
        job = JobStatus(
            name="sync_cycle",
            next_run="2024-01-15T10:05:00",
            enabled=True,
        )

        assert job.name == "sync_cycle"
        assert job.enabled is True

    def test_accepts_none_next_run(self):
        """Test that None next_run is accepted."""
        job = JobStatus(
            name="disabled_job",
            next_run=None,
            enabled=False,
        )

        assert job.next_run is None
        assert job.enabled is False


class TestJobsStatusResponse:
    """Test JobsStatusResponse model."""

    def test_valid_creation(self):
        """Test valid JobsStatusResponse creation."""
        response = JobsStatusResponse(
            status="ok",
            jobs=[
                {"name": "sync_cycle", "enabled": True},
                {"name": "stocks_data_sync", "enabled": False},
            ],
        )

        assert response.status == "ok"
        assert len(response.jobs) == 2

    def test_accepts_empty_jobs_list(self):
        """Test that empty jobs list is accepted."""
        response = JobsStatusResponse(status="ok", jobs=[])

        assert len(response.jobs) == 0
