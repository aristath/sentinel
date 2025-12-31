"""Comprehensive tests for scoring_service module.

These tests validate the ScoringService orchestrates scoring operations correctly:
- Calculating and saving security scores
- Handling insufficient data
- Managing errors gracefully
- Processing all active securities in the universe
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import SecurityScore
from app.modules.scoring.domain import CalculatedSecurityScore
from app.modules.scoring.services.scoring_service import (
    ScoringService,
    _to_domain_score,
)


class TestToDomainScore:
    """Test the _to_domain_score conversion function."""

    def test_converts_with_all_group_scores(self):
        """Test conversion when all group scores are present."""
        calc_score = CalculatedSecurityScore(
            symbol="TEST",
            total_score=85.5,
            volatility=0.25,
            calculated_at=datetime(2024, 1, 15, 10, 30),
            group_scores={
                "long_term": 90.0,
                "fundamentals": 80.0,
                "opportunity": 75.0,
                "opinion": 70.0,
                "diversification": 65.0,
                "technicals": 85.0,
            },
            sub_scores={
                "long_term": {"cagr": 92.0, "sharpe": 88.0},
                "fundamentals": {"consistency": 82.0, "strength": 78.0},
            },
        )

        domain_score = _to_domain_score(calc_score)

        assert domain_score.symbol == "TEST"
        assert domain_score.total_score == 85.5
        assert domain_score.volatility == 0.25
        assert domain_score.calculated_at == datetime(2024, 1, 15, 10, 30)
        # Quality score should be average of long_term and fundamentals
        assert domain_score.quality_score == 85.0  # (90 + 80) / 2
        assert domain_score.opportunity_score == 75.0
        assert domain_score.analyst_score == 70.0
        assert domain_score.allocation_fit_score == 65.0
        assert domain_score.technical_score == 85.0
        assert domain_score.fundamental_score == 80.0
        assert domain_score.cagr_score == 92.0
        assert domain_score.consistency_score == 82.0
        assert domain_score.history_years == 5.0

    def test_converts_with_only_long_term_score(self):
        """Test quality_score uses only long_term when fundamentals missing."""
        calc_score = CalculatedSecurityScore(
            symbol="TEST",
            total_score=75.0,
            volatility=0.20,
            calculated_at=datetime(2024, 1, 15, 10, 30),
            group_scores={
                "long_term": 80.0,
            },
            sub_scores={
                "long_term": {"cagr": 85.0},
            },
        )

        domain_score = _to_domain_score(calc_score)

        # Quality score should use only long_term
        assert domain_score.quality_score == 80.0
        assert domain_score.cagr_score == 85.0

    def test_converts_with_only_fundamentals_score(self):
        """Test quality_score uses only fundamentals when long_term missing."""
        calc_score = CalculatedSecurityScore(
            symbol="TEST",
            total_score=70.0,
            volatility=0.18,
            calculated_at=datetime(2024, 1, 15, 10, 30),
            group_scores={
                "fundamentals": 72.0,
            },
            sub_scores={
                "fundamentals": {"consistency": 74.0},
            },
        )

        domain_score = _to_domain_score(calc_score)

        # Quality score should use only fundamentals
        assert domain_score.quality_score == 72.0
        assert domain_score.consistency_score == 74.0

    def test_converts_with_no_group_scores(self):
        """Test conversion when group_scores is None."""
        calc_score = CalculatedSecurityScore(
            symbol="TEST",
            total_score=60.0,
            volatility=0.30,
            calculated_at=datetime(2024, 1, 15, 10, 30),
            group_scores=None,
            sub_scores=None,
        )

        domain_score = _to_domain_score(calc_score)

        assert domain_score.symbol == "TEST"
        assert domain_score.total_score == 60.0
        assert domain_score.quality_score is None
        assert domain_score.opportunity_score is None
        assert domain_score.analyst_score is None
        assert domain_score.cagr_score is None
        assert domain_score.consistency_score is None
        assert domain_score.history_years is None

    def test_converts_with_empty_group_scores(self):
        """Test conversion when group_scores is empty dict."""
        calc_score = CalculatedSecurityScore(
            symbol="TEST",
            total_score=60.0,
            volatility=0.30,
            calculated_at=datetime(2024, 1, 15, 10, 30),
            group_scores={},
            sub_scores={},
        )

        domain_score = _to_domain_score(calc_score)

        assert domain_score.quality_score is None
        assert domain_score.cagr_score is None
        assert domain_score.history_years is None

    def test_history_years_calculated_from_cagr(self):
        """Test history_years is set when CAGR data is present."""
        calc_score = CalculatedSecurityScore(
            symbol="TEST",
            total_score=80.0,
            volatility=0.22,
            calculated_at=datetime(2024, 1, 15, 10, 30),
            group_scores={},
            sub_scores={
                "long_term": {"cagr": 88.0},
            },
        )

        domain_score = _to_domain_score(calc_score)

        # History years should be 5.0 when CAGR is present
        assert domain_score.history_years == 5.0

    def test_history_years_none_without_cagr(self):
        """Test history_years is None when no CAGR data."""
        calc_score = CalculatedSecurityScore(
            symbol="TEST",
            total_score=70.0,
            volatility=0.25,
            calculated_at=datetime(2024, 1, 15, 10, 30),
            group_scores={},
            sub_scores={
                "fundamentals": {"consistency": 75.0},
            },
        )

        domain_score = _to_domain_score(calc_score)

        # No CAGR, so no history_years
        assert domain_score.history_years is None


class TestScoringServiceInit:
    """Test ScoringService initialization."""

    def test_init_sets_dependencies(self):
        """Test that all dependencies are set on initialization."""
        security_repo = AsyncMock()
        score_repo = AsyncMock()
        db_manager = AsyncMock()

        service = ScoringService(security_repo, score_repo, db_manager)

        assert service.security_repo == security_repo
        assert service.score_repo == score_repo
        assert service._db_manager == db_manager


class TestGetPriceData:
    """Test the _get_price_data method."""

    @pytest.mark.asyncio
    async def test_fetches_daily_and_monthly_prices(self):
        """Test that daily and monthly prices are fetched correctly."""
        security_repo = AsyncMock()
        score_repo = AsyncMock()
        db_manager = AsyncMock()

        # Mock history database
        history_db = AsyncMock()
        db_manager.history.return_value = history_db

        # Mock daily prices (simulate sqlite3.Row behavior)
        daily_row1 = MagicMock()
        daily_row1.keys.return_value = ["date", "close", "high", "low", "open"]
        daily_row1.__getitem__.side_effect = lambda k: {
            "date": "2024-01-15",
            "close": 150.0,
            "high": 152.0,
            "low": 148.0,
            "open": 149.0,
        }[k]

        daily_row2 = MagicMock()
        daily_row2.keys.return_value = ["date", "close", "high", "low", "open"]
        daily_row2.__getitem__.side_effect = lambda k: {
            "date": "2024-01-14",
            "close": 148.0,
            "high": 150.0,
            "low": 147.0,
            "open": 147.5,
        }[k]

        # Mock monthly prices
        monthly_row1 = MagicMock()
        monthly_row1.__getitem__.side_effect = lambda i: (
            "2024-01" if i == 0 else 150.0
        )

        monthly_row2 = MagicMock()
        monthly_row2.__getitem__.side_effect = lambda i: (
            "2023-12" if i == 0 else 145.0
        )

        history_db.fetchall.side_effect = [
            [daily_row1, daily_row2],
            [monthly_row1, monthly_row2],
        ]

        service = ScoringService(security_repo, score_repo, db_manager)
        daily_prices, monthly_prices = await service._get_price_data("TEST", "TEST.US")

        # Verify database manager was called
        db_manager.history.assert_called_once_with("TEST")

        # Verify queries were executed
        assert history_db.fetchall.call_count == 2

        # Verify daily prices structure
        assert len(daily_prices) == 2
        assert daily_prices[0]["date"] == "2024-01-15"
        assert daily_prices[0]["close"] == 150.0

        # Verify monthly prices structure
        assert len(monthly_prices) == 2
        assert monthly_prices[0]["year_month"] == "2024-01"
        assert monthly_prices[0]["avg_adj_close"] == 150.0

    @pytest.mark.asyncio
    async def test_handles_empty_results(self):
        """Test handling of empty database results."""
        security_repo = AsyncMock()
        score_repo = AsyncMock()
        db_manager = AsyncMock()

        history_db = AsyncMock()
        db_manager.history.return_value = history_db
        history_db.fetchall.side_effect = [[], []]

        service = ScoringService(security_repo, score_repo, db_manager)
        daily_prices, monthly_prices = await service._get_price_data("TEST", "TEST.US")

        assert daily_prices == []
        assert monthly_prices == []


class TestCalculateAndSaveScore:
    """Test the calculate_and_save_score method."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        security_repo = AsyncMock()
        score_repo = AsyncMock()
        db_manager = AsyncMock()
        return security_repo, score_repo, db_manager

    @pytest.mark.asyncio
    async def test_successful_calculation_and_save(self, mock_services):
        """Test successful score calculation and database save."""
        security_repo, score_repo, db_manager = mock_services

        # Mock price data
        history_db = AsyncMock()
        db_manager.history.return_value = history_db

        # Create sufficient daily prices (50+ days)
        daily_rows = []
        for i in range(100):
            row = MagicMock()
            row.keys.return_value = ["date", "close", "high", "low", "open"]
            row.__getitem__.side_effect = lambda k, idx=i: {
                "date": f"2024-01-{(idx % 28) + 1:02d}",
                "close": 150.0 + idx * 0.5,
                "high": 152.0 + idx * 0.5,
                "low": 148.0 + idx * 0.5,
                "open": 149.0 + idx * 0.5,
            }[k]
            daily_rows.append(row)

        # Create sufficient monthly prices (12+ months)
        monthly_rows = []
        for i in range(24):
            row = MagicMock()
            row.__getitem__.side_effect = lambda idx, month=i: (
                f"2023-{(month % 12) + 1:02d}" if idx == 0 else 150.0 + month * 2
            )
            monthly_rows.append(row)

        history_db.fetchall.side_effect = [daily_rows, monthly_rows]

        # Mock fundamentals
        mock_fundamentals = {"pe_ratio": 15.0, "eps": 5.0}

        # Mock calculate_security_score
        mock_calculated_score = CalculatedSecurityScore(
            symbol="TEST",
            total_score=85.0,
            volatility=0.22,
            calculated_at=datetime(2024, 1, 15, 10, 30),
            group_scores={
                "long_term": 90.0,
                "fundamentals": 80.0,
            },
            sub_scores={
                "long_term": {"cagr": 92.0},
                "fundamentals": {"consistency": 82.0},
            },
        )

        service = ScoringService(security_repo, score_repo, db_manager)

        with (
            patch(
                "app.infrastructure.external.yahoo_finance.get_fundamental_data",
                return_value=mock_fundamentals,
            ),
            patch(
                "app.modules.scoring.services.scoring_service.calculate_security_score",
                return_value=mock_calculated_score,
            ),
        ):
            result = await service.calculate_and_save_score(
                "TEST",
                yahoo_symbol="TEST.US",
                country="United States",
                industry="Consumer Electronics",
            )

        assert result is not None
        assert result.symbol == "TEST"
        assert result.total_score == 85.0

        # Verify score was saved
        score_repo.upsert.assert_called_once()
        saved_score = score_repo.upsert.call_args[0][0]
        assert isinstance(saved_score, SecurityScore)
        assert saved_score.symbol == "TEST"
        assert saved_score.total_score == 85.0

    @pytest.mark.asyncio
    async def test_uses_symbol_as_yahoo_symbol_fallback(self, mock_services):
        """Test that symbol is used when yahoo_symbol is None."""
        security_repo, score_repo, db_manager = mock_services

        history_db = AsyncMock()
        db_manager.history.return_value = history_db

        # Create sufficient data
        daily_rows = [
            MagicMock() for _ in range(100)
        ]  # We'll return this without configuring
        for i, row in enumerate(daily_rows):
            row.keys.return_value = ["date", "close", "high", "low", "open"]
            row.__getitem__.side_effect = lambda k, idx=i: {
                "date": f"2024-01-{(idx % 28) + 1:02d}",
                "close": 150.0,
                "high": 152.0,
                "low": 148.0,
                "open": 149.0,
            }[k]

        monthly_rows = [MagicMock() for _ in range(24)]
        for i, row in enumerate(monthly_rows):
            row.__getitem__.side_effect = lambda idx, month=i: (
                f"2023-{(month % 12) + 1:02d}" if idx == 0 else 150.0
            )

        history_db.fetchall.side_effect = [daily_rows, monthly_rows]

        service = ScoringService(security_repo, score_repo, db_manager)

        with (
            patch(
                "app.infrastructure.external.yahoo_finance.get_fundamental_data",
                return_value={},
            ) as mock_yahoo,
            patch(
                "app.modules.scoring.services.scoring_service.calculate_security_score",
                return_value=None,
            ),
        ):
            await service.calculate_and_save_score("TEST")

            # Yahoo finance should be called with symbol as fallback
            mock_yahoo.assert_called_with("TEST", yahoo_symbol="TEST")

    @pytest.mark.asyncio
    async def test_returns_none_when_insufficient_daily_data(self, mock_services):
        """Test returns None when daily data has less than 50 days."""
        security_repo, score_repo, db_manager = mock_services

        history_db = AsyncMock()
        db_manager.history.return_value = history_db

        # Only 30 days of daily data (insufficient)
        daily_rows = []
        for i in range(30):
            row = MagicMock()
            row.keys.return_value = ["date", "close", "high", "low", "open"]
            row.__getitem__.side_effect = lambda k, idx=i: {
                "date": f"2024-01-{idx + 1:02d}",
                "close": 150.0,
                "high": 152.0,
                "low": 148.0,
                "open": 149.0,
            }[k]
            daily_rows.append(row)

        monthly_rows = [MagicMock() for _ in range(24)]
        for i, row in enumerate(monthly_rows):
            row.__getitem__.side_effect = lambda idx, month=i: (
                f"2023-{month + 1:02d}" if idx == 0 else 150.0
            )

        history_db.fetchall.side_effect = [daily_rows, monthly_rows]

        service = ScoringService(security_repo, score_repo, db_manager)

        result = await service.calculate_and_save_score("TEST")

        assert result is None
        # Should not have saved anything
        score_repo.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_insufficient_monthly_data(self, mock_services):
        """Test returns None when monthly data has less than 12 months."""
        security_repo, score_repo, db_manager = mock_services

        history_db = AsyncMock()
        db_manager.history.return_value = history_db

        # Sufficient daily data
        daily_rows = []
        for i in range(100):
            row = MagicMock()
            row.keys.return_value = ["date", "close", "high", "low", "open"]
            row.__getitem__.side_effect = lambda k, idx=i: {
                "date": f"2024-01-{(idx % 28) + 1:02d}",
                "close": 150.0,
                "high": 152.0,
                "low": 148.0,
                "open": 149.0,
            }[k]
            daily_rows.append(row)

        # Only 8 months of monthly data (insufficient)
        monthly_rows = []
        for i in range(8):
            row = MagicMock()
            row.__getitem__.side_effect = lambda idx, month=i: (
                f"2024-{month + 1:02d}" if idx == 0 else 150.0
            )
            monthly_rows.append(row)

        history_db.fetchall.side_effect = [daily_rows, monthly_rows]

        service = ScoringService(security_repo, score_repo, db_manager)

        result = await service.calculate_and_save_score("TEST")

        assert result is None
        # Should not have saved anything
        score_repo.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_calculation_fails(self, mock_services):
        """Test returns None when score calculation returns None."""
        security_repo, score_repo, db_manager = mock_services

        history_db = AsyncMock()
        db_manager.history.return_value = history_db

        # Sufficient data
        daily_rows = []
        for i in range(100):
            row = MagicMock()
            row.keys.return_value = ["date", "close", "high", "low", "open"]
            row.__getitem__.side_effect = lambda k, idx=i: {
                "date": f"2024-01-{(idx % 28) + 1:02d}",
                "close": 150.0,
                "high": 152.0,
                "low": 148.0,
                "open": 149.0,
            }[k]
            daily_rows.append(row)

        monthly_rows = []
        for i in range(24):
            row = MagicMock()
            row.__getitem__.side_effect = lambda idx, month=i: (
                f"2023-{month + 1:02d}" if idx == 0 else 150.0
            )
            monthly_rows.append(row)

        history_db.fetchall.side_effect = [daily_rows, monthly_rows]

        service = ScoringService(security_repo, score_repo, db_manager)

        with (
            patch(
                "app.infrastructure.external.yahoo_finance.get_fundamental_data",
                return_value={},
            ),
            patch(
                "app.modules.scoring.services.scoring_service.calculate_security_score",
                return_value=None,  # Calculation fails
            ),
        ):
            result = await service.calculate_and_save_score("TEST")

        assert result is None
        # Should not have saved anything since calculation returned None
        score_repo.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self, mock_services):
        """Test that exceptions are caught and logged, returning None."""
        security_repo, score_repo, db_manager = mock_services

        # Make database raise an exception
        db_manager.history.side_effect = Exception("Database connection failed")

        service = ScoringService(security_repo, score_repo, db_manager)

        result = await service.calculate_and_save_score("TEST")

        assert result is None
        # Should not have saved anything
        score_repo.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_default_country_and_industry(self, mock_services):
        """Test defaults when country/industry not provided.

        - country is passed as-is (None when not provided)
        - industry defaults to "UNKNOWN" when not provided
        """
        security_repo, score_repo, db_manager = mock_services

        history_db = AsyncMock()
        db_manager.history.return_value = history_db

        # Create sufficient data
        daily_rows = []
        for i in range(100):
            row = MagicMock()
            row.keys.return_value = ["date", "close", "high", "low", "open"]
            row.__getitem__.side_effect = lambda k, idx=i: {
                "date": f"2024-01-{(idx % 28) + 1:02d}",
                "close": 150.0,
                "high": 152.0,
                "low": 148.0,
                "open": 149.0,
            }[k]
            daily_rows.append(row)

        monthly_rows = []
        for i in range(24):
            row = MagicMock()
            row.__getitem__.side_effect = lambda idx, month=i: (
                f"2023-{month + 1:02d}" if idx == 0 else 150.0
            )
            monthly_rows.append(row)

        history_db.fetchall.side_effect = [daily_rows, monthly_rows]

        service = ScoringService(security_repo, score_repo, db_manager)

        with (
            patch(
                "app.infrastructure.external.yahoo_finance.get_fundamental_data",
                return_value={},
            ),
            patch(
                "app.modules.scoring.services.scoring_service.calculate_security_score",
                return_value=None,
            ) as mock_calc,
        ):
            await service.calculate_and_save_score("TEST")

            # Verify calculate_security_score was called with appropriate defaults
            mock_calc.assert_called_once()
            call_kwargs = mock_calc.call_args[1]
            # country is passed as-is (None when not provided)
            assert call_kwargs["country"] is None
            # industry defaults to "UNKNOWN" when not provided
            assert call_kwargs["industry"] == "UNKNOWN"


class TestScoreAllStocks:
    """Test the score_all_stocks method."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        security_repo = AsyncMock()
        score_repo = AsyncMock()
        db_manager = AsyncMock()
        return security_repo, score_repo, db_manager

    @pytest.mark.asyncio
    async def test_scores_all_active_stocks(self, mock_services):
        """Test that all active securities are scored."""
        security_repo, score_repo, db_manager = mock_services

        # Mock active securities
        mock_stock1 = MagicMock()
        mock_stock1.symbol = "STOCK1"
        mock_stock1.yahoo_symbol = "STOCK1.US"
        mock_stock1.country = "United States"
        mock_stock1.industry = "Consumer Electronics"

        mock_stock2 = MagicMock()
        mock_stock2.symbol = "STOCK2"
        mock_stock2.yahoo_symbol = "STOCK2.US"
        mock_stock2.country = "Germany"
        mock_stock2.industry = "Banks - Diversified"

        security_repo.get_all_active.return_value = [mock_stock1, mock_stock2]

        service = ScoringService(security_repo, score_repo, db_manager)

        # Mock calculate_and_save_score to return different scores
        score1 = CalculatedSecurityScore(
            symbol="STOCK1",
            total_score=85.0,
            volatility=0.20,
            calculated_at=datetime(2024, 1, 15, 10, 30),
        )
        score2 = CalculatedSecurityScore(
            symbol="STOCK2",
            total_score=90.0,
            volatility=0.18,
            calculated_at=datetime(2024, 1, 15, 10, 30),
        )

        service.calculate_and_save_score = AsyncMock(side_effect=[score1, score2])

        scores = await service.score_all_stocks()

        # Verify all securities were scored
        assert len(scores) == 2
        assert scores[0].symbol == "STOCK1"
        assert scores[0].total_score == 85.0
        assert scores[1].symbol == "STOCK2"
        assert scores[1].total_score == 90.0

        # Verify calculate_and_save_score was called for each security
        assert service.calculate_and_save_score.call_count == 2
        service.calculate_and_save_score.assert_any_call(
            "STOCK1",
            yahoo_symbol="STOCK1.US",
            country="United States",
            industry="Consumer Electronics",
        )
        service.calculate_and_save_score.assert_any_call(
            "STOCK2",
            yahoo_symbol="STOCK2.US",
            country="Germany",
            industry="Banks - Diversified",
        )

    @pytest.mark.asyncio
    async def test_handles_no_active_stocks(self, mock_services):
        """Test handling when no active securities exist."""
        security_repo, score_repo, db_manager = mock_services

        security_repo.get_all_active.return_value = []

        service = ScoringService(security_repo, score_repo, db_manager)
        service.calculate_and_save_score = AsyncMock()

        scores = await service.score_all_stocks()

        assert scores == []
        # Should not have called calculate_and_save_score
        service.calculate_and_save_score.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_failed_calculations(self, mock_services):
        """Test that failed calculations are skipped and don't break the loop."""
        security_repo, score_repo, db_manager = mock_services

        # Mock active securities
        mock_stock1 = MagicMock()
        mock_stock1.symbol = "STOCK1"
        mock_stock1.yahoo_symbol = "STOCK1.US"
        mock_stock1.country = "United States"
        mock_stock1.industry = "Consumer Electronics"

        mock_stock2 = MagicMock()
        mock_stock2.symbol = "STOCK2"
        mock_stock2.yahoo_symbol = "STOCK2.US"
        mock_stock2.country = "Germany"
        mock_stock2.industry = "Banks - Diversified"

        mock_stock3 = MagicMock()
        mock_stock3.symbol = "STOCK3"
        mock_stock3.yahoo_symbol = "STOCK3.US"
        mock_stock3.country = "United States"
        mock_stock3.industry = "Drug Manufacturers"

        security_repo.get_all_active.return_value = [
            mock_stock1,
            mock_stock2,
            mock_stock3,
        ]

        service = ScoringService(security_repo, score_repo, db_manager)

        # Mock calculate_and_save_score: STOCK2 fails, others succeed
        score1 = CalculatedSecurityScore(
            symbol="STOCK1",
            total_score=85.0,
            volatility=0.20,
            calculated_at=datetime(2024, 1, 15, 10, 30),
        )
        score3 = CalculatedSecurityScore(
            symbol="STOCK3",
            total_score=88.0,
            volatility=0.22,
            calculated_at=datetime(2024, 1, 15, 10, 30),
        )

        service.calculate_and_save_score = AsyncMock(
            side_effect=[score1, None, score3]  # STOCK2 returns None (failed)
        )

        scores = await service.score_all_stocks()

        # Should only have 2 scores (STOCK2 failed)
        assert len(scores) == 2
        assert scores[0].symbol == "STOCK1"
        assert scores[1].symbol == "STOCK3"

        # Verify all securities were attempted
        assert service.calculate_and_save_score.call_count == 3

    @pytest.mark.asyncio
    async def test_processes_stocks_with_none_attributes(self, mock_services):
        """Test handling securities with None yahoo_symbol, country, or industry."""
        security_repo, score_repo, db_manager = mock_services

        # Mock security with None attributes
        mock_stock = MagicMock()
        mock_stock.symbol = "TEST"
        mock_stock.yahoo_symbol = None
        mock_stock.country = None
        mock_stock.industry = None

        security_repo.get_all_active.return_value = [mock_stock]

        service = ScoringService(security_repo, score_repo, db_manager)

        score = CalculatedSecurityScore(
            symbol="TEST",
            total_score=75.0,
            volatility=0.25,
            calculated_at=datetime(2024, 1, 15, 10, 30),
        )

        service.calculate_and_save_score = AsyncMock(return_value=score)

        scores = await service.score_all_stocks()

        # Should still process the security
        assert len(scores) == 1
        assert scores[0].symbol == "TEST"

        # Verify None values were passed through
        service.calculate_and_save_score.assert_called_once_with(
            "TEST",
            yahoo_symbol=None,
            country=None,
            industry=None,
        )


class TestScoringServiceEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_empty_daily_prices_list(self):
        """Test handling when daily_prices is an empty list."""
        security_repo = AsyncMock()
        score_repo = AsyncMock()
        db_manager = AsyncMock()

        history_db = AsyncMock()
        db_manager.history.return_value = history_db
        history_db.fetchall.side_effect = [[], []]

        service = ScoringService(security_repo, score_repo, db_manager)

        result = await service.calculate_and_save_score("TEST")

        assert result is None

    @pytest.mark.asyncio
    async def test_score_with_zero_volatility(self):
        """Test handling score with zero volatility."""
        calc_score = CalculatedSecurityScore(
            symbol="TEST",
            total_score=80.0,
            volatility=0.0,  # Zero volatility
            calculated_at=datetime(2024, 1, 15, 10, 30),
        )

        domain_score = _to_domain_score(calc_score)

        assert domain_score.volatility == 0.0
        assert domain_score.total_score == 80.0

    @pytest.mark.asyncio
    async def test_score_with_negative_values(self):
        """Test handling score with negative group scores."""
        calc_score = CalculatedSecurityScore(
            symbol="TEST",
            total_score=50.0,
            volatility=0.30,
            calculated_at=datetime(2024, 1, 15, 10, 30),
            group_scores={
                "long_term": -10.0,  # Negative score
                "fundamentals": 60.0,
            },
        )

        domain_score = _to_domain_score(calc_score)

        # Should handle negative scores
        assert domain_score.quality_score == 25.0  # (-10 + 60) / 2

    @pytest.mark.asyncio
    async def test_score_with_very_high_values(self):
        """Test handling score with values above 100."""
        calc_score = CalculatedSecurityScore(
            symbol="TEST",
            total_score=150.0,  # Above normal range
            volatility=0.15,
            calculated_at=datetime(2024, 1, 15, 10, 30),
            group_scores={
                "long_term": 120.0,
                "fundamentals": 110.0,
            },
        )

        domain_score = _to_domain_score(calc_score)

        # Should preserve the values even if unusual
        assert domain_score.total_score == 150.0
        assert domain_score.quality_score == 115.0  # (120 + 110) / 2
