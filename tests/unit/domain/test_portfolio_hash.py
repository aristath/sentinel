"""Tests for portfolio hash generation functions.

These tests validate the hash generation functions for portfolio state, settings, and allocations.
"""

from app.domain.models import Stock
from app.domain.portfolio_hash import (
    apply_pending_orders_to_portfolio,
    generate_allocations_hash,
    generate_portfolio_hash,
    generate_recommendation_cache_key,
    generate_settings_hash,
)


class TestApplyPendingOrdersToPortfolio:
    """Test apply_pending_orders_to_portfolio function."""

    def test_apply_buy_order(self):
        """Test applying a pending BUY order."""
        positions = [{"symbol": "AAPL", "quantity": 10}]
        cash = {"EUR": 1500.0}
        orders = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 5,
                "price": 100.0,
                "currency": "EUR",
            }
        ]

        adjusted_pos, adjusted_cash = apply_pending_orders_to_portfolio(
            positions, cash, orders
        )

        # Position should increase
        assert len(adjusted_pos) == 1
        assert adjusted_pos[0]["symbol"] == "AAPL"
        assert adjusted_pos[0]["quantity"] == 15

        # Cash should decrease
        assert adjusted_cash["EUR"] == 1000.0

    def test_apply_sell_order(self):
        """Test applying a pending SELL order."""
        positions = [{"symbol": "AAPL", "quantity": 10}]
        cash = {"EUR": 1500.0}
        orders = [
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 3,
                "price": 100.0,
                "currency": "EUR",
            }
        ]

        adjusted_pos, adjusted_cash = apply_pending_orders_to_portfolio(
            positions, cash, orders
        )

        # Position should decrease
        assert len(adjusted_pos) == 1
        assert adjusted_pos[0]["symbol"] == "AAPL"
        assert adjusted_pos[0]["quantity"] == 7

        # Cash should remain unchanged (SELL orders don't generate cash until executed)
        assert adjusted_cash["EUR"] == 1500.0

    def test_apply_multiple_orders(self):
        """Test applying multiple pending orders."""
        positions = [{"symbol": "AAPL", "quantity": 10}]
        cash = {"EUR": 2000.0, "USD": 500.0}
        orders = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 5,
                "price": 100.0,
                "currency": "EUR",
            },
            {
                "symbol": "MSFT",
                "side": "buy",
                "quantity": 3,
                "price": 200.0,
                "currency": "USD",
            },
        ]

        adjusted_pos, adjusted_cash = apply_pending_orders_to_portfolio(
            positions, cash, orders
        )

        # AAPL position should increase
        aapl_pos = next((p for p in adjusted_pos if p["symbol"] == "AAPL"), None)
        assert aapl_pos is not None
        assert aapl_pos["quantity"] == 15

        # MSFT position should be created
        msft_pos = next((p for p in adjusted_pos if p["symbol"] == "MSFT"), None)
        assert msft_pos is not None
        assert msft_pos["quantity"] == 3

        # Cash should decrease
        assert adjusted_cash["EUR"] == 1500.0
        assert adjusted_cash["USD"] == -100.0  # Can go negative in hypothetical state

    def test_apply_sell_order_removes_position_if_zero(self):
        """Test that SELL order removes position if quantity becomes zero."""
        positions = [{"symbol": "AAPL", "quantity": 5}]
        cash = {"EUR": 1500.0}
        orders = [
            {
                "symbol": "AAPL",
                "side": "sell",
                "quantity": 5,
                "price": 100.0,
                "currency": "EUR",
            }
        ]

        adjusted_pos, _ = apply_pending_orders_to_portfolio(positions, cash, orders)

        # Position should be removed (quantity <= 0)
        assert len(adjusted_pos) == 0

    def test_skip_invalid_orders(self):
        """Test that invalid orders are skipped."""
        positions = [{"symbol": "AAPL", "quantity": 10}]
        cash = {"EUR": 1500.0}
        orders = [
            {
                "symbol": "",
                "side": "buy",
                "quantity": 5,
                "price": 100.0,
                "currency": "EUR",
            },
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 0,
                "price": 100.0,
                "currency": "EUR",
            },
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 5,
                "price": 0,
                "currency": "EUR",
            },
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 5,
                "price": 100.0,
                "currency": "EUR",
            },
        ]

        adjusted_pos, adjusted_cash = apply_pending_orders_to_portfolio(
            positions, cash, orders
        )

        # Only the last valid order should be applied
        assert adjusted_pos[0]["quantity"] == 15
        assert adjusted_cash["EUR"] == 1000.0

    def test_case_insensitive_symbols(self):
        """Test that symbols are case-insensitive."""
        positions = [{"symbol": "aapl", "quantity": 10}]
        cash = {"EUR": 1500.0}
        orders = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 5,
                "price": 100.0,
                "currency": "EUR",
            }
        ]

        adjusted_pos, _ = apply_pending_orders_to_portfolio(positions, cash, orders)

        assert adjusted_pos[0]["symbol"] == "AAPL"
        assert adjusted_pos[0]["quantity"] == 15


class TestGeneratePortfolioHash:
    """Test generate_portfolio_hash function."""

    def test_generate_hash_with_positions(self):
        """Test generating hash with positions only."""
        positions = [
            {"symbol": "AAPL", "quantity": 10},
            {"symbol": "MSFT", "quantity": 5},
        ]

        hash1 = generate_portfolio_hash(positions)
        hash2 = generate_portfolio_hash(positions)

        # Should be deterministic
        assert hash1 == hash2
        assert len(hash1) == 8  # 8-character hex hash

    def test_generate_hash_with_stocks_universe(self):
        """Test generating hash with stocks universe."""
        positions = [{"symbol": "AAPL", "quantity": 10}]
        stocks = [
            Stock(
                symbol="AAPL",
                allow_buy=True,
                allow_sell=False,
                min_portfolio_target=None,
                max_portfolio_target=None,
                country="US",
                industry="Technology",
            ),
            Stock(
                symbol="MSFT",
                allow_buy=True,
                allow_sell=True,
                min_portfolio_target=0.05,
                max_portfolio_target=0.15,
                country="US",
                industry="Technology",
            ),
        ]

        hash1 = generate_portfolio_hash(positions, stocks=stocks)
        hash2 = generate_portfolio_hash(positions, stocks=stocks)

        # Should be deterministic
        assert hash1 == hash2

    def test_generate_hash_with_cash_balances(self):
        """Test generating hash with cash balances."""
        positions = [{"symbol": "AAPL", "quantity": 10}]
        cash = {"EUR": 1500.0, "USD": 200.0}

        hash1 = generate_portfolio_hash(positions, cash_balances=cash)
        hash2 = generate_portfolio_hash(positions, cash_balances=cash)

        # Should be deterministic
        assert hash1 == hash2

        # Hash should change when cash changes
        cash2 = {"EUR": 1500.0, "USD": 300.0}
        hash3 = generate_portfolio_hash(positions, cash_balances=cash2)
        assert hash1 != hash3

    def test_generate_hash_with_pending_orders(self):
        """Test generating hash with pending orders."""
        positions = [{"symbol": "AAPL", "quantity": 10}]
        cash = {"EUR": 1500.0}
        orders = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 5,
                "price": 100.0,
                "currency": "EUR",
            }
        ]

        hash1 = generate_portfolio_hash(
            positions, cash_balances=cash, pending_orders=orders
        )
        hash2 = generate_portfolio_hash(
            positions, cash_balances=cash, pending_orders=orders
        )

        # Should be deterministic
        assert hash1 == hash2

        # Hash should differ from hash without orders
        hash_no_orders = generate_portfolio_hash(positions, cash_balances=cash)
        assert hash1 != hash_no_orders

    def test_generate_hash_excludes_zero_cash(self):
        """Test that zero cash balances are excluded from hash."""
        positions = [{"symbol": "AAPL", "quantity": 10}]
        cash1 = {"EUR": 1500.0, "USD": 0.0}
        cash2 = {"EUR": 1500.0}

        hash1 = generate_portfolio_hash(positions, cash_balances=cash1)
        hash2 = generate_portfolio_hash(positions, cash_balances=cash2)

        # Should be the same (zero balances excluded)
        assert hash1 == hash2

    def test_generate_hash_deterministic_ordering(self):
        """Test that hash is deterministic regardless of input order."""
        positions1 = [
            {"symbol": "AAPL", "quantity": 10},
            {"symbol": "MSFT", "quantity": 5},
        ]
        positions2 = [
            {"symbol": "MSFT", "quantity": 5},
            {"symbol": "AAPL", "quantity": 10},
        ]

        hash1 = generate_portfolio_hash(positions1)
        hash2 = generate_portfolio_hash(positions2)

        # Should be the same (sorted by symbol)
        assert hash1 == hash2


class TestGenerateSettingsHash:
    """Test generate_settings_hash function."""

    def test_generate_hash_with_settings(self):
        """Test generating hash with settings."""
        settings = {
            "min_stock_score": 0.5,
            "min_hold_days": 90,
            "sell_cooldown_days": 180,
            "max_loss_threshold": -0.20,
            "target_annual_return": 0.11,
            "optimizer_blend": 0.5,
            "optimizer_target_return": 0.11,
            "transaction_cost_fixed": 2.0,
            "transaction_cost_percent": 0.002,
            "min_cash_reserve": 500.0,
            "max_plan_depth": 5,
        }

        hash1 = generate_settings_hash(settings)
        hash2 = generate_settings_hash(settings)

        # Should be deterministic
        assert hash1 == hash2
        assert len(hash1) == 8

    def test_generate_hash_with_missing_settings(self):
        """Test generating hash with missing settings (uses empty string)."""
        settings = {"min_stock_score": 0.5}

        hash1 = generate_settings_hash(settings)
        hash2 = generate_settings_hash({})

        # Should differ
        assert hash1 != hash2

    def test_generate_hash_changes_with_settings(self):
        """Test that hash changes when settings change."""
        settings1 = {"min_stock_score": 0.5, "min_hold_days": 90}
        settings2 = {"min_stock_score": 0.6, "min_hold_days": 90}

        hash1 = generate_settings_hash(settings1)
        hash2 = generate_settings_hash(settings2)

        assert hash1 != hash2


class TestGenerateAllocationsHash:
    """Test generate_allocations_hash function."""

    def test_generate_hash_with_allocations(self):
        """Test generating hash with allocations."""
        allocations = {"country:United States": 0.6, "industry:Technology": 0.3}

        hash1 = generate_allocations_hash(allocations)
        hash2 = generate_allocations_hash(allocations)

        # Should be deterministic
        assert hash1 == hash2
        assert len(hash1) == 8

    def test_generate_hash_empty_allocations(self):
        """Test generating hash with empty allocations."""
        hash1 = generate_allocations_hash({})
        hash2 = generate_allocations_hash({})

        # Should return fixed hash for empty allocations
        assert hash1 == "00000000"
        assert hash2 == "00000000"

    def test_generate_hash_deterministic_ordering(self):
        """Test that hash is deterministic regardless of input order."""
        allocations1 = {"country:United States": 0.6, "industry:Technology": 0.3}
        allocations2 = {"industry:Technology": 0.3, "country:United States": 0.6}

        hash1 = generate_allocations_hash(allocations1)
        hash2 = generate_allocations_hash(allocations2)

        # Should be the same (sorted by key)
        assert hash1 == hash2

    def test_generate_hash_changes_with_allocations(self):
        """Test that hash changes when allocations change."""
        allocations1 = {"country:United States": 0.6}
        allocations2 = {"country:United States": 0.7}

        hash1 = generate_allocations_hash(allocations1)
        hash2 = generate_allocations_hash(allocations2)

        assert hash1 != hash2


class TestGenerateRecommendationCacheKey:
    """Test generate_recommendation_cache_key function."""

    def test_generate_cache_key(self):
        """Test generating cache key with all parameters."""
        positions = [{"symbol": "AAPL", "quantity": 10}]
        settings = {"min_stock_score": 0.5}
        stocks = [
            Stock(
                symbol="AAPL",
                allow_buy=True,
                allow_sell=False,
                min_portfolio_target=None,
                max_portfolio_target=None,
                country="US",
                industry="Technology",
            )
        ]
        cash = {"EUR": 1500.0}
        allocations = {"country:United States": 0.6}
        orders = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 5,
                "price": 100.0,
                "currency": "EUR",
            }
        ]

        key1 = generate_recommendation_cache_key(
            positions, settings, stocks, cash, allocations, orders
        )
        key2 = generate_recommendation_cache_key(
            positions, settings, stocks, cash, allocations, orders
        )

        # Should be deterministic
        assert key1 == key2

        # Should be in format "portfolio_hash:settings_hash:allocations_hash"
        parts = key1.split(":")
        assert len(parts) == 3
        assert len(parts[0]) == 8  # portfolio_hash
        assert len(parts[1]) == 8  # settings_hash
        assert len(parts[2]) == 8  # allocations_hash

    def test_generate_cache_key_with_optional_parameters(self):
        """Test generating cache key with optional parameters as None."""
        positions = [{"symbol": "AAPL", "quantity": 10}]
        settings = {"min_stock_score": 0.5}

        key1 = generate_recommendation_cache_key(positions, settings)
        key2 = generate_recommendation_cache_key(
            positions, settings, None, None, None, None
        )

        # Should be the same
        assert key1 == key2

    def test_generate_cache_key_changes_with_portfolio(self):
        """Test that cache key changes when portfolio changes."""
        positions1 = [{"symbol": "AAPL", "quantity": 10}]
        positions2 = [{"symbol": "AAPL", "quantity": 11}]
        settings = {"min_stock_score": 0.5}

        key1 = generate_recommendation_cache_key(positions1, settings)
        key2 = generate_recommendation_cache_key(positions2, settings)

        assert key1 != key2
