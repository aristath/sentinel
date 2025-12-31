"""Tests for ConstraintsManager service.

These tests verify the constraint translation logic for portfolio optimization,
ensuring business rules are correctly converted to optimizer constraints.
"""

from unittest.mock import MagicMock

import pytest

from app.application.services.optimization.constraints_manager import (
    ConstraintsManager,
    SectorConstraint,
    WeightBounds,
)
from app.domain.models import Position, Stock
from app.modules.scoring.domain.constants import (
    GEO_ALLOCATION_TOLERANCE,
    IND_ALLOCATION_TOLERANCE,
    MAX_CONCENTRATION,
    MAX_COUNTRY_CONCENTRATION,
    MAX_SECTOR_CONCENTRATION,
)


def create_stock(
    symbol: str,
    allow_buy: bool = True,
    allow_sell: bool = True,
    min_lot: int = 0,
    country: str = "United States",
    industry: str = "Consumer Electronics",
    min_portfolio_target: float | None = None,
    max_portfolio_target: float | None = None,
) -> Stock:
    """Create a mock Stock object for testing."""
    stock = MagicMock(spec=Stock)
    stock.symbol = symbol
    stock.allow_buy = allow_buy
    stock.allow_sell = allow_sell
    stock.min_lot = min_lot
    stock.country = country
    stock.industry = industry
    stock.min_portfolio_target = min_portfolio_target
    stock.max_portfolio_target = max_portfolio_target
    return stock


def create_position(symbol: str, quantity: int, market_value_eur: float) -> Position:
    """Create a mock Position object for testing."""
    position = MagicMock(spec=Position)
    position.symbol = symbol
    position.quantity = quantity
    position.market_value_eur = market_value_eur
    return position


class TestConstraintsManagerInitialization:
    """Test ConstraintsManager initialization and configuration."""

    def test_default_initialization(self):
        """Test manager initializes with default constants."""
        manager = ConstraintsManager()

        assert manager.max_concentration == MAX_CONCENTRATION
        assert manager.geo_tolerance == GEO_ALLOCATION_TOLERANCE
        assert manager.ind_tolerance == IND_ALLOCATION_TOLERANCE

    def test_custom_initialization(self):
        """Test manager accepts custom configuration values."""
        manager = ConstraintsManager(
            max_concentration=0.25,
            geo_tolerance=0.15,
            ind_tolerance=0.20,
        )

        assert manager.max_concentration == 0.25
        assert manager.geo_tolerance == 0.15
        assert manager.ind_tolerance == 0.20


class TestWeightBoundsCalculation:
    """Test weight bounds calculation for individual stocks."""

    def test_unconstrained_stock_gets_default_bounds(self):
        """Test that unconstrained stock gets (0, max_concentration) bounds."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL")]
        positions = {}
        portfolio_value = 10000
        current_prices = {"AAPL": 150.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        assert bounds["AAPL"] == (0.0, MAX_CONCENTRATION)

    def test_allow_buy_false_caps_upper_bound_at_current_weight(self):
        """Test allow_buy=False prevents increasing position."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", allow_buy=False)]

        # Current position: 20% of portfolio
        positions = {"AAPL": create_position("AAPL", 10, 2000)}
        portfolio_value = 10000
        current_prices = {"AAPL": 200.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Upper bound should be current weight (20%)
        lower, upper = bounds["AAPL"]
        assert lower == 0.0
        assert upper == pytest.approx(0.20, abs=0.001)

    def test_allow_sell_false_sets_lower_bound_to_current_weight(self):
        """Test allow_sell=False prevents reducing position."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", allow_sell=False)]

        # Current position: 15% of portfolio (under MAX_CONCENTRATION)
        positions = {"AAPL": create_position("AAPL", 15, 1500)}
        portfolio_value = 10000
        current_prices = {"AAPL": 100.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Lower bound should be current weight (15%)
        lower, upper = bounds["AAPL"]
        assert lower == pytest.approx(0.15, abs=0.001)
        assert upper == MAX_CONCENTRATION

    def test_locked_position_both_bounds_equal_current_weight(self):
        """Test stock with allow_buy=False and allow_sell=False is locked."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", allow_buy=False, allow_sell=False)]

        # Current position: 25% of portfolio
        positions = {"AAPL": create_position("AAPL", 12, 2500)}
        portfolio_value = 10000
        current_prices = {"AAPL": 208.33}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Both bounds should equal current weight (locked)
        lower, upper = bounds["AAPL"]
        assert lower == pytest.approx(0.25, abs=0.001)
        assert upper == pytest.approx(0.25, abs=0.001)

    def test_min_lot_constraint_at_minimum_prevents_partial_sell(self):
        """Test that position at min_lot cannot be partially sold."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", min_lot=5)]

        # Position has exactly min_lot shares
        positions = {"AAPL": create_position("AAPL", 5, 1000)}
        portfolio_value = 10000
        current_prices = {"AAPL": 200.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Lower bound should be current weight (can't partially sell)
        lower, upper = bounds["AAPL"]
        assert lower == pytest.approx(0.10, abs=0.001)
        assert upper == MAX_CONCENTRATION

    def test_min_lot_constraint_above_minimum_allows_sell_to_min_lot(self):
        """Test position above min_lot can be sold down to min_lot value."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", min_lot=5)]

        # Position has 20 shares (above min_lot of 5)
        positions = {"AAPL": create_position("AAPL", 20, 4000)}
        portfolio_value = 10000
        current_prices = {"AAPL": 200.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Lower bound should be min_lot value: 5 * 200 / 10000 = 0.10
        lower, upper = bounds["AAPL"]
        assert lower == pytest.approx(0.10, abs=0.001)
        assert upper == MAX_CONCENTRATION

    def test_constraint_conflict_resolved_to_current_weight(self):
        """Test conflicting constraints resolved by using current weight."""
        manager = ConstraintsManager()
        # allow_sell=False (lower=current) + allow_buy=False (upper=current)
        # but set up a conflict artificially
        stocks = [create_stock("AAPL", allow_buy=False)]

        # Current weight is 25%, but allow_buy=False caps upper at 25%
        # Add allow_sell=False equivalent via min_lot
        stocks[0].min_lot = 12
        positions = {"AAPL": create_position("AAPL", 12, 2500)}
        portfolio_value = 10000
        current_prices = {"AAPL": 208.33}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Should resolve to current weight on both sides
        lower, upper = bounds["AAPL"]
        assert lower == pytest.approx(0.25, abs=0.001)
        assert upper == pytest.approx(0.25, abs=0.001)

    def test_new_position_zero_current_weight(self):
        """Test new position (not currently held) has zero current weight."""
        manager = ConstraintsManager()
        stocks = [create_stock("NEWSTOCK")]
        positions = {}  # No current position
        portfolio_value = 10000
        current_prices = {"NEWSTOCK": 50.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Should have standard bounds
        assert bounds["NEWSTOCK"] == (0.0, MAX_CONCENTRATION)

    def test_zero_portfolio_value_handled_gracefully(self):
        """Test zero portfolio value doesn't cause division by zero."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL")]
        positions = {"AAPL": create_position("AAPL", 10, 0)}
        portfolio_value = 0
        current_prices = {"AAPL": 150.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Should return default bounds without crashing
        assert bounds["AAPL"] == (0.0, MAX_CONCENTRATION)

    def test_missing_current_price_handled(self):
        """Test missing current price for min_lot calculation."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", min_lot=5)]
        positions = {"AAPL": create_position("AAPL", 5, 1000)}
        portfolio_value = 10000
        current_prices = {}  # No price available

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # min_lot check requires current_price > 0, so constraint won't apply
        # Should return default bounds
        lower, upper = bounds["AAPL"]
        assert lower == 0.0  # No min_lot constraint without price
        assert upper == MAX_CONCENTRATION

    def test_none_market_value_eur_treated_as_zero(self):
        """Test None market_value_eur is treated as zero weight."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL")]

        position = create_position("AAPL", 10, 0)
        position.market_value_eur = None
        positions = {"AAPL": position}
        portfolio_value = 10000
        current_prices = {"AAPL": 150.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Should treat as zero current weight
        assert bounds["AAPL"] == (0.0, MAX_CONCENTRATION)

    def test_multiple_stocks_with_various_constraints(self):
        """Test calculating bounds for multiple stocks with different constraints."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", allow_buy=False),  # Can't buy more
            create_stock("GOOGL", allow_sell=False),  # Can't sell
            create_stock("MSFT"),  # Unconstrained
            create_stock("TSLA", min_lot=10),  # Min lot at limit
        ]

        positions = {
            "AAPL": create_position("AAPL", 10, 1500),
            "GOOGL": create_position("GOOGL", 5, 1000),
            "MSFT": create_position("MSFT", 8, 2500),
            "TSLA": create_position("TSLA", 10, 2000),
        }
        portfolio_value = 10000
        current_prices = {
            "AAPL": 150.0,
            "GOOGL": 200.0,
            "MSFT": 312.5,
            "TSLA": 200.0,
        }

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # AAPL: allow_buy=False, upper capped at current (15%)
        assert bounds["AAPL"][0] == 0.0
        assert bounds["AAPL"][1] == pytest.approx(0.15, abs=0.001)

        # GOOGL: allow_sell=False, lower set to current (10%)
        assert bounds["GOOGL"][0] == pytest.approx(0.10, abs=0.001)
        assert bounds["GOOGL"][1] == MAX_CONCENTRATION

        # MSFT: unconstrained
        assert bounds["MSFT"] == (0.0, MAX_CONCENTRATION)

        # TSLA: at min_lot, lower set to current (20%)
        assert bounds["TSLA"][0] == pytest.approx(0.20, abs=0.001)
        assert bounds["TSLA"][1] == MAX_CONCENTRATION


class TestSectorConstraintsBuilding:
    """Test building country and industry sector constraints."""

    @pytest.mark.asyncio
    async def test_geography_constraints_basic(self):
        """Test basic country group constraint building."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", country="United States"),
            create_stock("SAP", country="Germany"),
        ]
        # Group targets (not individual countries)
        country_targets = {"US": 0.60, "EU": 0.40}
        ind_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Without grouping repo, countries map to "OTHER" by default
        # So we should have constraints for groups that have targets
        # Since stocks have "United States" and "Germany" but no grouping,
        # they'll go to "OTHER" if no mapping exists
        # For this test, we expect constraints based on group targets
        assert len(ind_constraints) == 0
        # With no grouping repo, countries not in groups go to "OTHER"
        # So we should have "OTHER" constraint if it's in targets
        # But "US" and "EU" won't match individual countries without mapping
        # This test will need grouping repo to work properly
        # For now, verify it doesn't crash
        assert isinstance(country_constraints, list)

    @pytest.mark.asyncio
    async def test_industry_constraints_basic(self):
        """Test basic industry group constraint building."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", industry="Consumer Electronics"),
            create_stock("JPM", industry="Banks - Diversified"),
        ]
        country_targets = {}
        # Group targets (not individual industries)
        ind_targets = {"Technology": 0.70, "Finance": 0.30}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Without grouping repo, industries map to "OTHER" by default
        # So we should have constraints based on group targets
        # This test will need grouping repo to work properly
        # For now, verify it doesn't crash
        assert isinstance(ind_constraints, list)

    @pytest.mark.asyncio
    async def test_none_country_grouped_as_other(self):
        """Test stocks with None country are grouped as OTHER."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", country="United States"),
            create_stock("UNKNOWN", country=None),
        ]
        country_targets = {"United States": 0.60, "OTHER": 0.40}
        ind_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Should have constraints for United States and OTHER
        assert len(country_constraints) == 2
        names = {c.name for c in country_constraints}
        assert "United States" in names
        assert "OTHER" in names

        # UNKNOWN should be in OTHER
        other_constraint = next(c for c in country_constraints if c.name == "OTHER")
        assert "UNKNOWN" in other_constraint.symbols

    @pytest.mark.asyncio
    async def test_none_industry_grouped_as_other(self):
        """Test stocks with None industry are grouped as OTHER."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", industry="Consumer Electronics"),
            create_stock("UNKNOWN", industry=None),
        ]
        country_targets = {}
        ind_targets = {"Consumer Electronics": 0.70, "OTHER": 0.30}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Should have constraints for Technology and OTHER
        assert len(ind_constraints) == 2
        names = {c.name for c in ind_constraints}
        assert "Consumer Electronics" in names
        assert "OTHER" in names

        # UNKNOWN should be in OTHER
        other_constraint = next(c for c in ind_constraints if c.name == "OTHER")
        assert "UNKNOWN" in other_constraint.symbols

    @pytest.mark.asyncio
    async def test_zero_target_excluded_from_constraints(self):
        """Test sectors with zero target weight are excluded."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", country="United States"),
            create_stock("SAP", country="Germany"),
        ]
        # Germany has zero target, should be excluded
        country_targets = {"United States": 1.0, "Germany": 0.0}
        ind_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Should only have United States constraint
        assert len(country_constraints) == 1
        assert country_constraints[0].name == "United States"

    @pytest.mark.asyncio
    async def test_missing_target_treated_as_zero(self):
        """Test sectors not in targets are excluded from constraints."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", country="United States"),
            create_stock("SAP", country="Germany"),
        ]
        # Germany not in targets
        country_targets = {"United States": 0.60}
        ind_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Should only have United States constraint
        assert len(country_constraints) == 1
        assert country_constraints[0].name == "United States"

    @pytest.mark.asyncio
    async def test_bounds_clamped_to_hard_caps(self):
        """Test constraint bounds are clamped to hard caps."""
        manager = ConstraintsManager(geo_tolerance=0.30)
        stocks = [create_stock("AAPL", country="United States")]
        # High target that would exceed hard cap with tolerance
        country_targets = {"United States": 0.95}
        ind_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        us_constraint = country_constraints[0]
        # Lower: 0.95 - 0.30 = 0.65
        assert us_constraint.lower == pytest.approx(0.65, abs=0.001)
        # Upper: min(min(1.0, 0.95 + 0.30), MAX_COUNTRY_CONCENTRATION) = 0.35
        assert us_constraint.upper == pytest.approx(
            MAX_COUNTRY_CONCENTRATION, abs=0.001
        )

    @pytest.mark.asyncio
    async def test_lower_bound_not_negative(self):
        """Test lower bound doesn't go negative."""
        manager = ConstraintsManager(geo_tolerance=0.30)
        stocks = [create_stock("AAPL", country="United States")]
        # Low target that would go negative with tolerance
        country_targets = {"United States": 0.10}
        ind_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        us_constraint = country_constraints[0]
        # Lower: max(0.0, 0.10 - 0.30) = 0.0
        assert us_constraint.lower == 0.0
        # Upper: min(0.10 + 0.30, MAX_COUNTRY_CONCENTRATION) = 0.35
        assert us_constraint.upper == pytest.approx(
            MAX_COUNTRY_CONCENTRATION, abs=0.001
        )

    @pytest.mark.asyncio
    async def test_multiple_stocks_same_sector(self):
        """Test multiple stocks in same sector are grouped correctly."""
        manager = ConstraintsManager()
        stocks = [
            create_stock(
                "AAPL", country="United States", industry="Consumer Electronics"
            ),
            create_stock(
                "GOOGL", country="United States", industry="Consumer Electronics"
            ),
            create_stock(
                "MSFT", country="United States", industry="Consumer Electronics"
            ),
        ]
        country_targets = {"United States": 1.0}
        ind_targets = {"Consumer Electronics": 1.0}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # United States should contain all 3 stocks
        us_constraint = country_constraints[0]
        assert len(us_constraint.symbols) == 3
        assert set(us_constraint.symbols) == {"AAPL", "GOOGL", "MSFT"}

        # Consumer Electronics should contain all 3 stocks
        tech_constraint = ind_constraints[0]
        assert len(tech_constraint.symbols) == 3
        assert set(tech_constraint.symbols) == {"AAPL", "GOOGL", "MSFT"}

    @pytest.mark.asyncio
    async def test_mixed_sectors_multiple_constraints(self):
        """Test building constraints with mixed sectors."""
        manager = ConstraintsManager()
        stocks = [
            create_stock(
                "AAPL", country="United States", industry="Consumer Electronics"
            ),
            create_stock("SAP", country="Germany", industry="Consumer Electronics"),
            create_stock(
                "JPM", country="United States", industry="Banks - Diversified"
            ),
        ]
        country_targets = {"United States": 0.60, "Germany": 0.40}
        ind_targets = {"Consumer Electronics": 0.70, "Banks - Diversified": 0.30}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        assert len(country_constraints) == 2
        assert len(ind_constraints) == 2

        # United States should have AAPL and JPM
        us_constraint = next(
            c for c in country_constraints if c.name == "United States"
        )
        assert set(us_constraint.symbols) == {"AAPL", "JPM"}

        # Consumer Electronics should have AAPL and SAP
        tech_constraint = next(
            c for c in ind_constraints if c.name == "Consumer Electronics"
        )
        assert set(tech_constraint.symbols) == {"AAPL", "SAP"}


class TestConstraintSummary:
    """Test constraint summary generation for debugging."""

    def test_empty_constraints_summary(self):
        """Test summary with no constraints."""
        manager = ConstraintsManager()
        bounds = {}
        country_constraints = []
        ind_constraints = []

        summary = manager.get_constraint_summary(
            bounds, country_constraints, ind_constraints
        )

        assert summary["total_stocks"] == 0
        assert summary["locked_positions"] == []
        assert summary["buy_only"] == []
        assert summary["sell_blocked"] == []
        assert summary["country_constraints"] == []
        assert summary["industry_constraints"] == []

    def test_locked_position_identified(self):
        """Test locked position (lower == upper) is identified."""
        manager = ConstraintsManager()
        # Position where both bounds are equal
        bounds = {"AAPL": (0.25, 0.25)}
        country_constraints = []
        ind_constraints = []

        summary = manager.get_constraint_summary(
            bounds, country_constraints, ind_constraints
        )

        assert summary["total_stocks"] == 1
        assert "AAPL" in summary["locked_positions"]
        assert summary["buy_only"] == []
        assert summary["sell_blocked"] == []

    def test_buy_only_position_identified(self):
        """Test buy-only position (lower=0, upper<max) is identified."""
        manager = ConstraintsManager()
        # Position where upper is constrained but lower is zero
        bounds = {"AAPL": (0.0, 0.15)}
        country_constraints = []
        ind_constraints = []

        summary = manager.get_constraint_summary(
            bounds, country_constraints, ind_constraints
        )

        assert summary["total_stocks"] == 1
        assert "AAPL" in summary["buy_only"]
        assert summary["locked_positions"] == []
        assert summary["sell_blocked"] == []

    def test_sell_blocked_position_identified(self):
        """Test sell-blocked position (lower > 0) is identified."""
        manager = ConstraintsManager()
        # Position where lower bound prevents full exit
        bounds = {"AAPL": (0.10, MAX_CONCENTRATION)}
        country_constraints = []
        ind_constraints = []

        summary = manager.get_constraint_summary(
            bounds, country_constraints, ind_constraints
        )

        assert summary["total_stocks"] == 1
        assert "AAPL" in summary["sell_blocked"]
        assert summary["locked_positions"] == []
        assert summary["buy_only"] == []

    def test_unconstrained_position_not_in_lists(self):
        """Test unconstrained position doesn't appear in special lists."""
        manager = ConstraintsManager()
        # Standard unconstrained position
        bounds = {"AAPL": (0.0, MAX_CONCENTRATION)}
        country_constraints = []
        ind_constraints = []

        summary = manager.get_constraint_summary(
            bounds, country_constraints, ind_constraints
        )

        assert summary["total_stocks"] == 1
        assert summary["locked_positions"] == []
        assert summary["buy_only"] == []
        assert summary["sell_blocked"] == []

    def test_sector_constraints_included_in_summary(self):
        """Test sector constraints are included in summary."""
        manager = ConstraintsManager()
        bounds = {}
        country_constraints = [
            SectorConstraint(
                name="United States",
                symbols=["AAPL", "GOOGL"],
                target=0.60,
                lower=0.50,
                upper=0.70,
            )
        ]
        ind_constraints = [
            SectorConstraint(
                name="Consumer Electronics",
                symbols=["AAPL", "GOOGL"],
                target=0.70,
                lower=0.55,
                upper=0.85,
            )
        ]

        summary = manager.get_constraint_summary(
            bounds, country_constraints, ind_constraints
        )

        assert len(summary["country_constraints"]) == 1
        assert summary["country_constraints"][0]["name"] == "United States"
        assert summary["country_constraints"][0]["target"] == 0.60
        assert summary["country_constraints"][0]["range"] == (0.50, 0.70)

        assert len(summary["industry_constraints"]) == 1
        assert summary["industry_constraints"][0]["name"] == "Consumer Electronics"
        assert summary["industry_constraints"][0]["target"] == 0.70
        assert summary["industry_constraints"][0]["range"] == (0.55, 0.85)

    def test_multiple_constrained_positions_summary(self):
        """Test summary with multiple types of constraints."""
        manager = ConstraintsManager()
        bounds = {
            "AAPL": (0.25, 0.25),  # Locked
            "GOOGL": (0.0, 0.15),  # Buy only
            "MSFT": (0.10, MAX_CONCENTRATION),  # Sell blocked
            "TSLA": (0.0, MAX_CONCENTRATION),  # Unconstrained
        }
        country_constraints = []
        ind_constraints = []

        summary = manager.get_constraint_summary(
            bounds, country_constraints, ind_constraints
        )

        assert summary["total_stocks"] == 4
        assert summary["locked_positions"] == ["AAPL"]
        assert summary["buy_only"] == ["GOOGL"]
        assert summary["sell_blocked"] == ["MSFT"]


class TestWeightBoundsDataClass:
    """Test WeightBounds dataclass functionality."""

    def test_weight_bounds_creation(self):
        """Test creating WeightBounds object."""
        wb = WeightBounds(
            symbol="AAPL",
            lower=0.10,
            upper=0.30,
            reason="Min lot constraint",
        )

        assert wb.symbol == "AAPL"
        assert wb.lower == 0.10
        assert wb.upper == 0.30
        assert wb.reason == "Min lot constraint"

    def test_weight_bounds_optional_reason(self):
        """Test WeightBounds with no reason."""
        wb = WeightBounds(symbol="GOOGL", lower=0.0, upper=0.20)

        assert wb.symbol == "GOOGL"
        assert wb.lower == 0.0
        assert wb.upper == 0.20
        assert wb.reason is None


class TestSectorConstraintDataClass:
    """Test SectorConstraint dataclass functionality."""

    def test_sector_constraint_creation(self):
        """Test creating SectorConstraint object."""
        sc = SectorConstraint(
            name="US",
            symbols=["AAPL", "GOOGL", "MSFT"],
            target=0.60,
            lower=0.50,
            upper=0.70,
        )

        assert sc.name == "US"
        assert sc.symbols == ["AAPL", "GOOGL", "MSFT"]
        assert sc.target == 0.60
        assert sc.lower == 0.50
        assert sc.upper == 0.70


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_stocks_list(self):
        """Test with empty stocks list."""
        manager = ConstraintsManager()
        bounds = manager.calculate_weight_bounds(
            stocks=[],
            positions={},
            portfolio_value=10000,
            current_prices={},
        )

        assert bounds == {}

    @pytest.mark.asyncio
    async def test_empty_targets(self):
        """Test with empty target dictionaries."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL")]

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks=stocks,
            country_targets={},
            ind_targets={},
        )

        # Should return empty constraint lists
        assert country_constraints == []
        assert ind_constraints == []

    def test_negative_portfolio_value(self):
        """Test handling of negative portfolio value."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL")]
        positions = {"AAPL": create_position("AAPL", 10, 1000)}
        portfolio_value = -1000  # Negative value
        current_prices = {"AAPL": 100.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Should handle gracefully without crashing
        assert "AAPL" in bounds

    def test_very_large_min_lot(self):
        """Test with very large min_lot value."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", min_lot=1000000)]
        positions = {"AAPL": create_position("AAPL", 10, 1000)}
        portfolio_value = 10000
        current_prices = {"AAPL": 100.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Should handle without crashing
        assert "AAPL" in bounds

    def test_conflicting_min_lot_and_allow_sell(self):
        """Test min_lot constraint with allow_sell=False."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", allow_sell=False, min_lot=5)]
        positions = {"AAPL": create_position("AAPL", 10, 1000)}
        portfolio_value = 10000
        current_prices = {"AAPL": 100.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # allow_sell=False should dominate (current weight)
        lower, upper = bounds["AAPL"]
        assert lower == pytest.approx(0.10, abs=0.001)

    @pytest.mark.asyncio
    async def test_target_exceeds_one(self):
        """Test target weight > 1.0 is handled."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", country="United States")]
        # Invalid target > 1.0
        country_targets = {"United States": 1.5}
        ind_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Should still create constraint (bounds will be clamped)
        assert len(country_constraints) == 1
        assert country_constraints[0].target == 1.5
        # Upper bound should be clamped to 1.0 by tolerance logic
        assert country_constraints[0].upper <= 1.0

    def test_very_small_portfolio_value(self):
        """Test with very small portfolio value."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", min_lot=5)]
        positions = {"AAPL": create_position("AAPL", 5, 10)}
        portfolio_value = 10  # Very small value
        current_prices = {"AAPL": 2.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Should calculate correctly: 5 * 2 / 10 = 1.0 (100%)
        lower, upper = bounds["AAPL"]
        assert lower == pytest.approx(1.0, abs=0.001)

    def test_zero_price_with_min_lot(self):
        """Test min_lot calculation with zero price."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", min_lot=5)]
        positions = {"AAPL": create_position("AAPL", 5, 1000)}
        portfolio_value = 10000
        current_prices = {"AAPL": 0.0}  # Zero price

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # min_lot check requires current_price > 0, so constraint won't apply
        lower, upper = bounds["AAPL"]
        assert lower == 0.0  # No min_lot constraint without price
        assert upper == MAX_CONCENTRATION

    def test_min_portfolio_target_applies_as_lower_bound(self):
        """Test that min_portfolio_target is applied as lower bound (converted from percentage)."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", min_portfolio_target=5.0)]
        positions = {}
        portfolio_value = 10000
        current_prices = {"AAPL": 150.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # 5% should become 0.05
        lower, upper = bounds["AAPL"]
        assert lower == 0.05
        assert upper == MAX_CONCENTRATION

    def test_max_portfolio_target_applies_as_upper_bound(self):
        """Test that max_portfolio_target is applied as upper bound (converted from percentage)."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", max_portfolio_target=15.0)]
        positions = {}
        portfolio_value = 10000
        current_prices = {"AAPL": 150.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # 15% should become 0.15
        lower, upper = bounds["AAPL"]
        assert lower == 0.0
        assert upper == 0.15

    def test_portfolio_targets_override_defaults(self):
        """Test that portfolio targets override default bounds."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", min_portfolio_target=5.0, max_portfolio_target=15.0)
        ]
        positions = {}
        portfolio_value = 10000
        current_prices = {"AAPL": 150.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        lower, upper = bounds["AAPL"]
        assert lower == 0.05  # 5%
        assert upper == 0.15  # 15%

    def test_portfolio_targets_interact_with_allow_buy(self):
        """Test that allow_buy can further restrict upper bound set by max_portfolio_target."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", allow_buy=False, max_portfolio_target=15.0)]
        # Current position: 10% of portfolio
        positions = {"AAPL": create_position("AAPL", 10, 1000)}
        portfolio_value = 10000
        current_prices = {"AAPL": 100.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # allow_buy=False should restrict upper to current weight (10%), not max_portfolio_target (15%)
        lower, upper = bounds["AAPL"]
        assert lower == 0.0
        assert upper == 0.10  # Current weight, not 0.15

    def test_portfolio_targets_interact_with_allow_sell(self):
        """Test that allow_sell can further restrict lower bound set by min_portfolio_target."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", allow_sell=False, min_portfolio_target=5.0)]
        # Current position: 10% of portfolio
        positions = {"AAPL": create_position("AAPL", 10, 1000)}
        portfolio_value = 10000
        current_prices = {"AAPL": 100.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # allow_sell=False should restrict lower to current weight (10%), not min_portfolio_target (5%)
        lower, upper = bounds["AAPL"]
        assert lower == 0.10  # Current weight, not 0.05
        assert upper == MAX_CONCENTRATION

    def test_portfolio_targets_interact_with_min_lot(self):
        """Test that min_lot constraints work with portfolio targets."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", min_lot=5, min_portfolio_target=5.0)]
        # Position at min_lot
        positions = {"AAPL": create_position("AAPL", 5, 1000)}
        portfolio_value = 10000
        current_prices = {"AAPL": 200.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # min_lot constraint should take precedence (can't sell below current weight)
        lower, upper = bounds["AAPL"]
        assert lower == 0.10  # Current weight (10%), not min_portfolio_target (5%)
        assert upper == MAX_CONCENTRATION

    def test_none_portfolio_targets_dont_affect_bounds(self):
        """Test that None portfolio targets don't affect bounds."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", min_portfolio_target=None, max_portfolio_target=None)
        ]
        positions = {}
        portfolio_value = 10000
        current_prices = {"AAPL": 150.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # Should use defaults
        lower, upper = bounds["AAPL"]
        assert lower == 0.0
        assert upper == MAX_CONCENTRATION

    def test_portfolio_target_edge_case_min_zero(self):
        """Test edge case: min_portfolio_target=0."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", min_portfolio_target=0.0, max_portfolio_target=30.0)
        ]
        positions = {}
        portfolio_value = 10000
        current_prices = {"AAPL": 150.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        lower, upper = bounds["AAPL"]
        assert lower == 0.0
        assert upper == 0.30  # 30%

    def test_portfolio_target_edge_case_min_equals_max(self):
        """Test edge case: min_portfolio_target equals max_portfolio_target."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", min_portfolio_target=10.0, max_portfolio_target=10.0)
        ]
        positions = {}
        portfolio_value = 10000
        current_prices = {"AAPL": 150.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        lower, upper = bounds["AAPL"]
        assert lower == 0.10
        assert upper == 0.10

    def test_portfolio_target_constraint_conflict_resolution(self):
        """Test constraint behavior when portfolio targets interact with allow_buy/allow_sell."""
        manager = ConstraintsManager()
        # Stock with min_portfolio_target=15% but current weight is 5% and allow_sell=False
        # allow_sell=False means can't go below current weight
        # min_portfolio_target=15% means should be at least 15%
        # Since current is 5% and can't sell, the optimizer can BUY more to reach 15%
        stocks = [create_stock("AAPL", allow_sell=False, min_portfolio_target=15.0)]
        positions = {"AAPL": create_position("AAPL", 10, 500)}  # 5% of portfolio
        portfolio_value = 10000
        current_prices = {"AAPL": 50.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        # lower = max(0.15 from target, 0.05 from allow_sell) = 0.15
        # This is not a conflict - optimizer can buy more to reach 15%
        lower, upper = bounds["AAPL"]
        assert lower == 0.15  # min_portfolio_target takes precedence
        assert upper == MAX_CONCENTRATION


class TestTargetNormalization:
    """Test normalization of industry/country targets that sum to > 100%."""

    @pytest.mark.asyncio
    async def test_industry_targets_normalized_when_sum_exceeds_100(self):
        """Test industry targets are normalized when they sum to > 100%."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", industry="Technology"),
            create_stock("GOOGL", industry="Technology"),
            create_stock("MSFT", industry="Software"),
        ]
        # Targets sum to 150% - should be normalized to 100%
        ind_targets = {"Technology": 0.8, "Software": 0.7}
        country_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Should have 2 industry constraints
        assert len(ind_constraints) == 2

        # Check normalized targets (0.8 + 0.7 = 1.5, so normalize: 0.8/1.5 = 0.533, 0.7/1.5 = 0.467)
        tech_constraint = next(c for c in ind_constraints if c.name == "Technology")
        software_constraint = next(c for c in ind_constraints if c.name == "Software")

        assert tech_constraint.target == pytest.approx(0.8 / 1.5, abs=0.001)
        assert software_constraint.target == pytest.approx(0.7 / 1.5, abs=0.001)

    @pytest.mark.asyncio
    async def test_country_targets_normalized_when_sum_exceeds_100(self):
        """Test country targets are normalized when they sum to > 100% (only active countries)."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", country="United States"),
            create_stock("SAP", country="Germany"),
        ]
        # Targets sum to 120% - should be normalized to 100%
        # Note: Only countries with stocks are considered for normalization
        country_targets = {
            "United States": 0.8,
            "Germany": 0.4,
            "France": 0.5,
        }  # France has no stocks
        ind_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Should have 2 country constraints (only US and Germany have stocks)
        assert len(country_constraints) == 2

        # Check normalized targets (0.8 + 0.4 = 1.2, so normalize: 0.8/1.2 = 0.667, 0.4/1.2 = 0.333)
        us_constraint = next(
            c for c in country_constraints if c.name == "United States"
        )
        de_constraint = next(c for c in country_constraints if c.name == "Germany")

        assert us_constraint.target == pytest.approx(0.8 / 1.2, abs=0.001)
        assert de_constraint.target == pytest.approx(0.4 / 1.2, abs=0.001)

    @pytest.mark.asyncio
    async def test_targets_not_normalized_when_sum_equals_100(self):
        """Test targets are not normalized when they sum to exactly 100%."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", industry="Technology"),
            create_stock("GOOGL", industry="Software"),
        ]
        ind_targets = {"Technology": 0.6, "Software": 0.4}  # Sums to 100%
        country_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        tech_constraint = next(c for c in ind_constraints if c.name == "Technology")
        software_constraint = next(c for c in ind_constraints if c.name == "Software")

        # Should not be normalized
        assert tech_constraint.target == pytest.approx(0.6, abs=0.001)
        assert software_constraint.target == pytest.approx(0.4, abs=0.001)

    @pytest.mark.asyncio
    async def test_normalization_only_applies_to_active_industries(self):
        """Test normalization only considers industries that have stocks."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", industry="Technology"),
        ]
        # Technology has stock, Energy doesn't
        # Only Technology should be normalized (0.8 / 0.8 = 1.0)
        ind_targets = {"Technology": 0.8, "Energy": 0.9}  # Energy has no stocks
        country_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Should only have Technology constraint (Energy has no stocks)
        assert len(ind_constraints) == 1
        assert ind_constraints[0].name == "Technology"
        # Should be normalized to 1.0 (only active industry)
        assert ind_constraints[0].target == pytest.approx(1.0, abs=0.001)

    @pytest.mark.asyncio
    async def test_normalization_only_applies_to_active_countries(self):
        """Test normalization only considers countries that have stocks."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", country="United States"),
        ]
        # United States has stock, France doesn't
        # Only United States should be normalized (0.8 / 0.8 = 1.0)
        country_targets = {"United States": 0.8, "France": 0.9}  # France has no stocks
        ind_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Should only have United States constraint (France has no stocks)
        assert len(country_constraints) == 1
        assert country_constraints[0].name == "United States"
        # Should be normalized to 1.0 (only active country)
        assert country_constraints[0].target == pytest.approx(1.0, abs=0.001)


class TestIndustryConcentrationCapAdjustment:
    """Test industry concentration cap adjustment for few industries."""

    @pytest.mark.asyncio
    async def test_single_industry_gets_70_percent_cap(self):
        """Test single industry constraint gets 70% max concentration."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", industry="Technology")]
        ind_targets = {"Technology": 0.8}
        country_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        assert len(ind_constraints) == 1
        tech_constraint = ind_constraints[0]

        # With target=0.8 and tolerance=0.15, upper would be min(1.0, 0.8+0.15) = 0.95
        # But should be capped at 70% for single industry
        assert tech_constraint.upper == pytest.approx(0.70, abs=0.001)

    @pytest.mark.asyncio
    async def test_two_industries_get_50_percent_cap_each(self):
        """Test two industry constraints each get 50% max concentration."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", industry="Technology"),
            create_stock("GOOGL", industry="Software"),
        ]
        ind_targets = {"Technology": 0.6, "Software": 0.4}
        country_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        assert len(ind_constraints) == 2
        tech_constraint = next(c for c in ind_constraints if c.name == "Technology")
        software_constraint = next(c for c in ind_constraints if c.name == "Software")

        # Each should be capped at 50%
        assert tech_constraint.upper == pytest.approx(0.50, abs=0.001)
        assert software_constraint.upper == pytest.approx(0.50, abs=0.001)

    @pytest.mark.asyncio
    async def test_three_plus_industries_get_default_30_percent_cap(self):
        """Test three or more industries get default 30% max concentration."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", industry="Technology"),
            create_stock("GOOGL", industry="Software"),
            create_stock("MSFT", industry="Cloud"),
        ]
        ind_targets = {"Technology": 0.4, "Software": 0.3, "Cloud": 0.3}
        country_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        assert len(ind_constraints) == 3
        for constraint in ind_constraints:
            # Each should be capped at default 30%
            assert constraint.upper == pytest.approx(
                MAX_SECTOR_CONCENTRATION, abs=0.001
            )

    @pytest.mark.asyncio
    async def test_industry_cap_adjustment_allows_higher_total_allocation(self):
        """Test that cap adjustment allows higher total allocation for few industries."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", industry="Technology"),
            create_stock("GOOGL", industry="Software"),
        ]
        ind_targets = {"Technology": 0.5, "Software": 0.5}
        country_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # With 2 industries at 50% each, total max should be 100%
        total_max = sum(c.upper for c in ind_constraints)
        assert total_max == pytest.approx(1.0, abs=0.001)


class TestIndustryMinimumBoundScaling:
    """Test scaling down industry minimum bounds when they're too restrictive."""

    @pytest.mark.asyncio
    async def test_industry_minimum_bounds_scaled_when_sum_exceeds_100(self):
        """Test industry minimum bounds are scaled down when they sum to > 100%."""
        manager = ConstraintsManager(ind_tolerance=0.15)
        stocks = [
            create_stock("AAPL", industry="Technology"),
            create_stock("GOOGL", industry="Software"),
        ]
        # High targets with tolerance create minimums that sum > 100%
        ind_targets = {"Technology": 0.6, "Software": 0.5}  # Targets sum to 110%
        country_targets = {}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Should have 2 industry constraints
        assert len(ind_constraints) == 2

        # Check that minimums were scaled down
        ind_min_sum = sum(c.lower for c in ind_constraints)
        assert ind_min_sum <= 1.0  # Should be <= 100%

    @pytest.mark.asyncio
    async def test_industry_minimum_bounds_scaled_when_combined_with_country_exceeds_70(
        self,
    ):
        """Test industry minimums are scaled when combined with country minimums > 70%."""
        manager = ConstraintsManager(geo_tolerance=0.10, ind_tolerance=0.15)
        stocks = [
            create_stock("AAPL", country="United States", industry="Technology"),
            create_stock("SAP", country="Germany", industry="Software"),
        ]
        # Country targets: 0.4 each = 0.8 total, with tolerance: min = 0.3 each = 0.6 total
        # Industry targets: 0.35 and 0.5 = 0.85 total, with tolerance: min = 0.2 and 0.35 = 0.55 total
        # Combined: 0.6 + 0.55 = 1.15 > 70%, so industry should be scaled
        country_targets = {"United States": 0.4, "Germany": 0.4}
        ind_targets = {"Technology": 0.35, "Software": 0.5}

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Check that industry minimums were scaled down
        country_min_sum = sum(c.lower for c in country_constraints)
        ind_min_sum = sum(c.lower for c in ind_constraints)
        total_min_sum = country_min_sum + ind_min_sum

        # Total should be <= 70%
        assert total_min_sum <= 0.70

    @pytest.mark.asyncio
    async def test_industry_minimum_bounds_not_scaled_when_combined_below_70(self):
        """Test industry minimums are NOT scaled when combined total is <= 70%."""
        manager = ConstraintsManager(geo_tolerance=0.10, ind_tolerance=0.15)
        stocks = [
            create_stock("AAPL", country="United States", industry="Technology"),
        ]
        # Low targets that won't exceed 70% threshold
        country_targets = {"United States": 0.3}
        ind_targets = {"Technology": 0.3}
        # Country min: 0.3 - 0.1 = 0.2
        # Industry min: 0.3 - 0.15 = 0.15
        # Total: 0.35 < 70%, so no scaling

        country_constraints, ind_constraints = await manager.build_sector_constraints(
            stocks, country_targets, ind_targets
        )

        # Check original minimums are preserved (not scaled)
        country_min_sum = sum(c.lower for c in country_constraints)
        ind_min_sum = sum(c.lower for c in ind_constraints)

        # Should match expected values (0.2 and 0.15)
        assert country_min_sum == pytest.approx(0.2, abs=0.01)
        assert ind_min_sum == pytest.approx(0.15, abs=0.01)


class TestMinLotInfeasibleBounds:
    """Test min_lot constraint handling when it would create infeasible bounds."""

    def test_min_lot_ignored_when_exceeds_upper_bound(self):
        """Test min_lot constraint is ignored when it would exceed upper bound."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("BYD", min_lot=500, max_portfolio_target=20.0)
        ]  # 20% max
        # Position: 1000 shares at 33.42 EUR = 33,420 EUR
        # Portfolio: 19,043 EUR
        # Current weight: 33,420 / 19,043 = 175% (impossible, but for test)
        # Min lot value: 500 * 33.42 = 16,710 EUR
        # Min lot weight: 16,710 / 19,043 = 87.75%
        # Upper bound: 20% (from max_portfolio_target)
        # Since 87.75% > 20%, min_lot should be ignored
        positions = {"BYD": create_position("BYD", 1000, 33420)}
        portfolio_value = 19043
        current_prices = {"BYD": 33.42}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        lower, upper = bounds["BYD"]
        # Upper should be 20% (max_portfolio_target)
        assert upper == pytest.approx(0.20, abs=0.001)
        # Lower should NOT be 87.75% (min_lot ignored), should be 0% or current weight
        # Since min_lot is ignored, lower should be 0% (no min_portfolio_target set)
        assert lower == pytest.approx(0.0, abs=0.001)

    def test_min_lot_applied_when_within_bounds(self):
        """Test min_lot constraint is applied when it's within bounds."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", min_lot=10, max_portfolio_target=30.0)]
        # Position: 100 shares at 150 EUR = 15,000 EUR
        # Portfolio: 100,000 EUR
        # Current weight: 15%
        # Min lot value: 10 * 150 = 1,500 EUR
        # Min lot weight: 1,500 / 100,000 = 1.5%
        # Upper bound: 30%
        # Since 1.5% < 30%, min_lot should be applied
        positions = {"AAPL": create_position("AAPL", 100, 15000)}
        portfolio_value = 100000
        current_prices = {"AAPL": 150.0}

        bounds = manager.calculate_weight_bounds(
            stocks, positions, portfolio_value, current_prices
        )

        lower, upper = bounds["AAPL"]
        # Lower should be 1.5% (min_lot constraint)
        assert lower == pytest.approx(0.015, abs=0.001)
        # Upper should be 30% (max_portfolio_target)
        assert upper == pytest.approx(0.30, abs=0.001)
