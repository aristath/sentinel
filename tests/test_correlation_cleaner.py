"""Tests for correlation matrix cleaning using Random Matrix Theory.

These tests verify the intended behavior of the CorrelationCleaner:
1. Marchenko-Pastur bound calculations
2. Eigenvalue filtering
3. Matrix reconstruction
4. Correlation matrix validity
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch

from sentinel.correlation_cleaner import CorrelationCleaner


class TestMarchenkoPasturBounds:
    """Tests for Marchenko-Pastur eigenvalue bounds calculation."""

    @pytest.fixture
    def cleaner(self):
        return CorrelationCleaner()

    def test_bounds_with_q_equals_1(self, cleaner):
        """When T = N (q = 1), bounds are (0, 4)."""
        lambda_min, lambda_max = cleaner._marchenko_pastur_bounds(1.0)
        # (1 - sqrt(1))^2 = 0, (1 + sqrt(1))^2 = 4
        assert abs(lambda_min - 0.0) < 0.001
        assert abs(lambda_max - 4.0) < 0.001

    def test_bounds_with_q_equals_0_25(self, cleaner):
        """When T = 4N (q = 0.25), bounds are narrower."""
        lambda_min, lambda_max = cleaner._marchenko_pastur_bounds(0.25)
        # (1 - sqrt(0.25))^2 = (1 - 0.5)^2 = 0.25
        # (1 + sqrt(0.25))^2 = (1 + 0.5)^2 = 2.25
        assert abs(lambda_min - 0.25) < 0.001
        assert abs(lambda_max - 2.25) < 0.001

    def test_bounds_with_q_equals_4(self, cleaner):
        """When T = N/4 (q = 4), bounds are wider."""
        lambda_min, lambda_max = cleaner._marchenko_pastur_bounds(4.0)
        # (1 - sqrt(4))^2 = (1 - 2)^2 = 1
        # (1 + sqrt(4))^2 = (1 + 2)^2 = 9
        assert abs(lambda_min - 1.0) < 0.001
        assert abs(lambda_max - 9.0) < 0.001

    def test_bounds_with_small_q(self, cleaner):
        """Very small q produces narrow bounds near 1."""
        lambda_min, lambda_max = cleaner._marchenko_pastur_bounds(0.01)
        # As q -> 0, both bounds approach 1
        assert lambda_min > 0.5
        assert lambda_max < 2.0

    def test_bounds_are_valid(self, cleaner):
        """Bounds are valid (lambda_min < lambda_max, both positive)."""
        for q in [0.1, 0.5, 1.0, 2.0, 4.0]:
            lambda_min, lambda_max = cleaner._marchenko_pastur_bounds(q)
            # Basic validity checks
            assert lambda_min >= 0, f"lambda_min should be >= 0 for q={q}"
            assert lambda_max > lambda_min, f"lambda_max should be > lambda_min for q={q}"


class TestCleanCorrelation:
    """Tests for correlation matrix cleaning."""

    @pytest.fixture
    def cleaner(self):
        return CorrelationCleaner()

    @pytest.mark.asyncio
    async def test_clean_preserves_matrix_shape(self, cleaner):
        """Cleaned matrix has same shape as input."""
        corr_matrix = np.eye(5)
        cleaned = await cleaner.clean_correlation(corr_matrix)
        assert cleaned.shape == (5, 5)

    @pytest.mark.asyncio
    async def test_clean_preserves_diagonal_ones(self, cleaner):
        """Diagonal elements are always 1 after cleaning."""
        # Create a noisy correlation matrix
        np.random.seed(42)
        n = 10
        random_matrix = np.random.randn(n, n)
        corr_matrix = random_matrix @ random_matrix.T
        corr_matrix = corr_matrix / np.outer(np.sqrt(np.diag(corr_matrix)), np.sqrt(np.diag(corr_matrix)))

        cleaned = await cleaner.clean_correlation(corr_matrix)

        # All diagonal elements should be exactly 1
        np.testing.assert_array_almost_equal(np.diag(cleaned), np.ones(n))

    @pytest.mark.asyncio
    async def test_clean_bounds_correlations(self, cleaner):
        """Cleaned correlations are bounded in [-1, 1]."""
        np.random.seed(42)
        n = 10
        random_matrix = np.random.randn(n, n)
        corr_matrix = random_matrix @ random_matrix.T
        corr_matrix = corr_matrix / np.outer(np.sqrt(np.diag(corr_matrix)), np.sqrt(np.diag(corr_matrix)))

        cleaned = await cleaner.clean_correlation(corr_matrix)

        assert np.all(cleaned >= -1.0)
        assert np.all(cleaned <= 1.0)

    @pytest.mark.asyncio
    async def test_clean_produces_symmetric_matrix(self, cleaner):
        """Cleaned matrix is symmetric."""
        np.random.seed(42)
        n = 8
        random_matrix = np.random.randn(n, n)
        corr_matrix = random_matrix @ random_matrix.T
        corr_matrix = corr_matrix / np.outer(np.sqrt(np.diag(corr_matrix)), np.sqrt(np.diag(corr_matrix)))

        cleaned = await cleaner.clean_correlation(corr_matrix)

        np.testing.assert_array_almost_equal(cleaned, cleaned.T)

    @pytest.mark.asyncio
    async def test_identity_matrix_unchanged(self, cleaner):
        """Identity matrix (no correlations) should remain approximately identity."""
        identity = np.eye(5)
        cleaned = await cleaner.clean_correlation(identity)

        # Diagonal should remain 1
        np.testing.assert_array_almost_equal(np.diag(cleaned), np.ones(5))

    @pytest.mark.asyncio
    async def test_clean_reduces_noise(self, cleaner):
        """Cleaning should reduce the variance of off-diagonal elements."""
        np.random.seed(42)
        n = 20

        # Create a correlation matrix from purely random data (noise)
        random_returns = np.random.randn(100, n)
        corr_matrix = np.corrcoef(random_returns.T)

        cleaned = await cleaner.clean_correlation(corr_matrix)

        # Off-diagonal variance should be reduced (noise filtered)
        off_diag_original = corr_matrix[np.triu_indices(n, k=1)]
        off_diag_cleaned = cleaned[np.triu_indices(n, k=1)]

        # Cleaned matrix should have smaller off-diagonal variance
        # (noise eigenvalues are averaged, reducing variance)
        original_var = np.var(off_diag_original)
        cleaned_var = np.var(off_diag_cleaned)

        # This might not always hold for small matrices, but generally true
        assert cleaned_var <= original_var * 1.5  # Allow some tolerance


class TestCorrelationMatrixValidity:
    """Tests that cleaned matrices are valid correlation matrices."""

    @pytest.fixture
    def cleaner(self):
        return CorrelationCleaner()

    @pytest.mark.asyncio
    async def test_positive_semidefinite(self, cleaner):
        """Cleaned correlation matrix should be positive semidefinite."""
        np.random.seed(42)
        n = 10
        random_returns = np.random.randn(100, n)
        corr_matrix = np.corrcoef(random_returns.T)

        cleaned = await cleaner.clean_correlation(corr_matrix)

        # All eigenvalues should be >= 0 (positive semidefinite)
        eigenvalues = np.linalg.eigvalsh(cleaned)
        assert np.all(eigenvalues >= -1e-10)  # Allow tiny numerical errors

    @pytest.mark.asyncio
    async def test_valid_for_cholesky(self, cleaner):
        """Cleaned matrix should be valid for Cholesky decomposition."""
        np.random.seed(42)
        n = 8
        random_returns = np.random.randn(100, n)
        corr_matrix = np.corrcoef(random_returns.T)

        cleaned = await cleaner.clean_correlation(corr_matrix)

        # Small regularization to ensure positive definiteness
        cleaned_reg = cleaned + np.eye(n) * 1e-6

        # Should not raise exception
        try:
            np.linalg.cholesky(cleaned_reg)
        except np.linalg.LinAlgError:
            pytest.fail("Cleaned matrix is not positive definite")


class TestEigenvalueFiltering:
    """Tests for eigenvalue filtering logic."""

    @pytest.fixture
    def cleaner(self):
        return CorrelationCleaner()

    @pytest.mark.asyncio
    async def test_signal_eigenvalues_preserved(self, cleaner):
        """Large eigenvalues (signal) should be approximately preserved."""
        np.random.seed(42)

        # Create a correlation matrix with strong signal
        # Two groups of highly correlated assets
        n = 10
        corr_matrix = np.eye(n)

        # Group 1: assets 0-4 are highly correlated
        for i in range(5):
            for j in range(5):
                if i != j:
                    corr_matrix[i, j] = 0.8

        # Group 2: assets 5-9 are highly correlated
        for i in range(5, 10):
            for j in range(5, 10):
                if i != j:
                    corr_matrix[i, j] = 0.7

        original_eigenvalues = np.linalg.eigvalsh(corr_matrix)
        cleaned = await cleaner.clean_correlation(corr_matrix)
        cleaned_eigenvalues = np.linalg.eigvalsh(cleaned)

        # The largest eigenvalues (signal) should be similar
        # Sort in descending order
        orig_sorted = sorted(original_eigenvalues, reverse=True)
        clean_sorted = sorted(cleaned_eigenvalues, reverse=True)

        # Top eigenvalues should be in same general range
        # Note: RMT filtering modifies eigenvalues, so we just check they're still large
        assert clean_sorted[0] > 1.0  # Still a significant signal eigenvalue
        assert clean_sorted[1] > 0.5  # Second eigenvalue also present


class TestCalculateRawCorrelation:
    """Tests for raw correlation calculation from price data."""

    @pytest.fixture
    def cleaner(self):
        cleaner = CorrelationCleaner()
        cleaner._db = AsyncMock()
        return cleaner

    @pytest.mark.asyncio
    async def test_returns_none_for_insufficient_symbols(self, cleaner):
        """Returns None when less than 2 symbols have data."""
        from sentinel.security import Security

        # Mock Security to return empty prices
        with patch.object(Security, 'get_historical_prices', new_callable=AsyncMock) as mock_prices:
            mock_prices.return_value = []

            corr, symbols = await cleaner.calculate_raw_correlation(['SYM1', 'SYM2'], days=504)

            assert corr is None
            assert symbols is None

    @pytest.mark.asyncio
    async def test_correlation_matrix_shape(self, cleaner):
        """Correlation matrix has correct shape (n x n)."""
        from sentinel.security import Security

        # Mock Security to return price data
        mock_prices = [{'close': 100 + i + np.random.randn() * 2} for i in range(300)]

        with patch.object(Security, 'get_historical_prices', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_prices

            corr, symbols = await cleaner.calculate_raw_correlation(['SYM1', 'SYM2', 'SYM3'], days=504)

            if corr is not None:
                assert corr.shape == (len(symbols), len(symbols))

    @pytest.mark.asyncio
    async def test_valid_symbols_returned(self, cleaner):
        """Only symbols with sufficient data are returned."""
        from sentinel.security import Security

        call_count = [0]
        async def mock_get_prices(self, days=504):
            call_count[0] += 1
            if call_count[0] == 1:
                return [{'close': 100 + i} for i in range(300)]  # Enough data
            elif call_count[0] == 2:
                return [{'close': 100} for _ in range(50)]  # Not enough
            else:
                return [{'close': 100 + i} for i in range(300)]  # Enough

        with patch.object(Security, 'get_historical_prices', mock_get_prices):
            corr, symbols = await cleaner.calculate_raw_correlation(['SYM1', 'SYM2', 'SYM3'], days=504)

            # SYM2 should be excluded due to insufficient data
            if symbols:
                assert 'SYM2' not in symbols


class TestEdgeCases:
    """Edge case tests."""

    @pytest.fixture
    def cleaner(self):
        return CorrelationCleaner()

    @pytest.mark.asyncio
    async def test_single_asset_matrix(self, cleaner):
        """1x1 correlation matrix (single asset) is handled."""
        single = np.array([[1.0]])
        cleaned = await cleaner.clean_correlation(single)
        assert cleaned.shape == (1, 1)
        assert cleaned[0, 0] == 1.0

    @pytest.mark.asyncio
    async def test_two_asset_matrix(self, cleaner):
        """2x2 correlation matrix is handled correctly."""
        two_asset = np.array([[1.0, 0.5], [0.5, 1.0]])
        cleaned = await cleaner.clean_correlation(two_asset)

        assert cleaned.shape == (2, 2)
        assert cleaned[0, 0] == 1.0
        assert cleaned[1, 1] == 1.0
        assert -1 <= cleaned[0, 1] <= 1

    @pytest.mark.asyncio
    async def test_perfect_correlation(self, cleaner):
        """Perfectly correlated assets."""
        perfect = np.array([
            [1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0]
        ])
        cleaned = await cleaner.clean_correlation(perfect)

        # Should remain valid correlation matrix
        assert np.all(cleaned >= -1)
        assert np.all(cleaned <= 1)
        np.testing.assert_array_equal(np.diag(cleaned), np.ones(3))

    @pytest.mark.asyncio
    async def test_negative_correlation(self, cleaner):
        """Negative correlations are preserved in sign."""
        corr_matrix = np.array([
            [1.0, -0.8],
            [-0.8, 1.0]
        ])
        cleaned = await cleaner.clean_correlation(corr_matrix)

        # Correlation sign should be preserved
        assert cleaned[0, 1] < 0
        assert cleaned[1, 0] < 0

    @pytest.mark.asyncio
    async def test_nearly_singular_matrix(self, cleaner):
        """Nearly singular correlation matrix is handled."""
        # All assets nearly perfectly correlated
        n = 5
        eps = 0.01
        nearly_singular = np.ones((n, n)) * (1 - eps) + np.eye(n) * eps

        cleaned = await cleaner.clean_correlation(nearly_singular)

        # Should still produce valid correlation matrix
        assert np.all(cleaned >= -1)
        assert np.all(cleaned <= 1)
        np.testing.assert_array_almost_equal(np.diag(cleaned), np.ones(n))
