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
from app.domain.scoring.constants import (
    GEO_ALLOCATION_TOLERANCE,
    IND_ALLOCATION_TOLERANCE,
    MAX_CONCENTRATION,
)


def create_stock(
    symbol: str,
    allow_buy: bool = True,
    allow_sell: bool = True,
    min_lot: int = 0,
    geography: str = "US",
    industry: str = "Consumer Electronics",
) -> Stock:
    """Create a mock Stock object for testing."""
    stock = MagicMock(spec=Stock)
    stock.symbol = symbol
    stock.allow_buy = allow_buy
    stock.allow_sell = allow_sell
    stock.min_lot = min_lot
    stock.geography = geography
    stock.industry = industry
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
    """Test building geography and industry sector constraints."""

    def test_geography_constraints_basic(self):
        """Test basic geography constraint building."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", geography="US"),
            create_stock("SAP", geography="EU"),
        ]
        geo_targets = {"US": 0.60, "EU": 0.40}
        ind_targets = {}

        geo_constraints, ind_constraints = manager.build_sector_constraints(
            stocks, geo_targets, ind_targets
        )

        # Should have 2 geography constraints
        assert len(geo_constraints) == 2
        assert len(ind_constraints) == 0

        # Find US constraint
        us_constraint = next(c for c in geo_constraints if c.name == "US")
        assert us_constraint.target == 0.60
        assert us_constraint.lower == pytest.approx(
            0.60 - GEO_ALLOCATION_TOLERANCE, abs=0.001
        )
        assert us_constraint.upper == pytest.approx(
            0.60 + GEO_ALLOCATION_TOLERANCE, abs=0.001
        )
        assert "AAPL" in us_constraint.symbols

    def test_industry_constraints_basic(self):
        """Test basic industry constraint building."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", industry="Consumer Electronics"),
            create_stock("JPM", industry="Banks - Diversified"),
        ]
        geo_targets = {}
        ind_targets = {"Consumer Electronics": 0.70, "Banks - Diversified": 0.30}

        geo_constraints, ind_constraints = manager.build_sector_constraints(
            stocks, geo_targets, ind_targets
        )

        # Should have 2 industry constraints
        assert len(geo_constraints) == 0
        assert len(ind_constraints) == 2

        # Find Technology constraint
        tech_constraint = next(
            c for c in ind_constraints if c.name == "Consumer Electronics"
        )
        assert tech_constraint.target == 0.70
        assert tech_constraint.lower == pytest.approx(
            0.70 - IND_ALLOCATION_TOLERANCE, abs=0.001
        )
        assert tech_constraint.upper == pytest.approx(
            0.70 + IND_ALLOCATION_TOLERANCE, abs=0.001
        )
        assert "AAPL" in tech_constraint.symbols

    def test_none_geography_grouped_as_other(self):
        """Test stocks with None geography are grouped as OTHER."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", geography="US"),
            create_stock("UNKNOWN", geography=None),
        ]
        geo_targets = {"US": 0.60, "OTHER": 0.40}
        ind_targets = {}

        geo_constraints, ind_constraints = manager.build_sector_constraints(
            stocks, geo_targets, ind_targets
        )

        # Should have constraints for US and OTHER
        assert len(geo_constraints) == 2
        names = {c.name for c in geo_constraints}
        assert "US" in names
        assert "OTHER" in names

        # UNKNOWN should be in OTHER
        other_constraint = next(c for c in geo_constraints if c.name == "OTHER")
        assert "UNKNOWN" in other_constraint.symbols

    def test_none_industry_grouped_as_other(self):
        """Test stocks with None industry are grouped as OTHER."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", industry="Consumer Electronics"),
            create_stock("UNKNOWN", industry=None),
        ]
        geo_targets = {}
        ind_targets = {"Consumer Electronics": 0.70, "OTHER": 0.30}

        geo_constraints, ind_constraints = manager.build_sector_constraints(
            stocks, geo_targets, ind_targets
        )

        # Should have constraints for Technology and OTHER
        assert len(ind_constraints) == 2
        names = {c.name for c in ind_constraints}
        assert "Consumer Electronics" in names
        assert "OTHER" in names

        # UNKNOWN should be in OTHER
        other_constraint = next(c for c in ind_constraints if c.name == "OTHER")
        assert "UNKNOWN" in other_constraint.symbols

    def test_zero_target_excluded_from_constraints(self):
        """Test sectors with zero target weight are excluded."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", geography="US"),
            create_stock("SAP", geography="EU"),
        ]
        # EU has zero target, should be excluded
        geo_targets = {"US": 1.0, "EU": 0.0}
        ind_targets = {}

        geo_constraints, ind_constraints = manager.build_sector_constraints(
            stocks, geo_targets, ind_targets
        )

        # Should only have US constraint
        assert len(geo_constraints) == 1
        assert geo_constraints[0].name == "US"

    def test_missing_target_treated_as_zero(self):
        """Test sectors not in targets are excluded from constraints."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", geography="US"),
            create_stock("SAP", geography="EU"),
        ]
        # EU not in targets
        geo_targets = {"US": 0.60}
        ind_targets = {}

        geo_constraints, ind_constraints = manager.build_sector_constraints(
            stocks, geo_targets, ind_targets
        )

        # Should only have US constraint
        assert len(geo_constraints) == 1
        assert geo_constraints[0].name == "US"

    def test_bounds_clamped_to_zero_and_one(self):
        """Test constraint bounds are clamped to [0, 1]."""
        manager = ConstraintsManager(geo_tolerance=0.30)
        stocks = [create_stock("AAPL", geography="US")]
        # High target that would exceed 1.0 with tolerance
        geo_targets = {"US": 0.95}
        ind_targets = {}

        geo_constraints, ind_constraints = manager.build_sector_constraints(
            stocks, geo_targets, ind_targets
        )

        us_constraint = geo_constraints[0]
        # Lower: 0.95 - 0.30 = 0.65
        assert us_constraint.lower == pytest.approx(0.65, abs=0.001)
        # Upper: min(1.0, 0.95 + 0.30) = 1.0
        assert us_constraint.upper == 1.0

    def test_lower_bound_not_negative(self):
        """Test lower bound doesn't go negative."""
        manager = ConstraintsManager(geo_tolerance=0.30)
        stocks = [create_stock("AAPL", geography="US")]
        # Low target that would go negative with tolerance
        geo_targets = {"US": 0.10}
        ind_targets = {}

        geo_constraints, ind_constraints = manager.build_sector_constraints(
            stocks, geo_targets, ind_targets
        )

        us_constraint = geo_constraints[0]
        # Lower: max(0.0, 0.10 - 0.30) = 0.0
        assert us_constraint.lower == 0.0
        # Upper: 0.10 + 0.30 = 0.40
        assert us_constraint.upper == pytest.approx(0.40, abs=0.001)

    def test_multiple_stocks_same_sector(self):
        """Test multiple stocks in same sector are grouped correctly."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", geography="US", industry="Consumer Electronics"),
            create_stock("GOOGL", geography="US", industry="Consumer Electronics"),
            create_stock("MSFT", geography="US", industry="Consumer Electronics"),
        ]
        geo_targets = {"US": 1.0}
        ind_targets = {"Consumer Electronics": 1.0}

        geo_constraints, ind_constraints = manager.build_sector_constraints(
            stocks, geo_targets, ind_targets
        )

        # US should contain all 3 stocks
        us_constraint = geo_constraints[0]
        assert len(us_constraint.symbols) == 3
        assert set(us_constraint.symbols) == {"AAPL", "GOOGL", "MSFT"}

        # Technology should contain all 3 stocks
        tech_constraint = ind_constraints[0]
        assert len(tech_constraint.symbols) == 3
        assert set(tech_constraint.symbols) == {"AAPL", "GOOGL", "MSFT"}

    def test_mixed_sectors_multiple_constraints(self):
        """Test building constraints with mixed sectors."""
        manager = ConstraintsManager()
        stocks = [
            create_stock("AAPL", geography="US", industry="Consumer Electronics"),
            create_stock("SAP", geography="EU", industry="Consumer Electronics"),
            create_stock("JPM", geography="US", industry="Banks - Diversified"),
        ]
        geo_targets = {"US": 0.60, "EU": 0.40}
        ind_targets = {"Consumer Electronics": 0.70, "Banks - Diversified": 0.30}

        geo_constraints, ind_constraints = manager.build_sector_constraints(
            stocks, geo_targets, ind_targets
        )

        assert len(geo_constraints) == 2
        assert len(ind_constraints) == 2

        # US should have AAPL and JPM
        us_constraint = next(c for c in geo_constraints if c.name == "US")
        assert set(us_constraint.symbols) == {"AAPL", "JPM"}

        # Technology should have AAPL and SAP
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
        geo_constraints = []
        ind_constraints = []

        summary = manager.get_constraint_summary(
            bounds, geo_constraints, ind_constraints
        )

        assert summary["total_stocks"] == 0
        assert summary["locked_positions"] == []
        assert summary["buy_only"] == []
        assert summary["sell_blocked"] == []
        assert summary["geography_constraints"] == []
        assert summary["industry_constraints"] == []

    def test_locked_position_identified(self):
        """Test locked position (lower == upper) is identified."""
        manager = ConstraintsManager()
        # Position where both bounds are equal
        bounds = {"AAPL": (0.25, 0.25)}
        geo_constraints = []
        ind_constraints = []

        summary = manager.get_constraint_summary(
            bounds, geo_constraints, ind_constraints
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
        geo_constraints = []
        ind_constraints = []

        summary = manager.get_constraint_summary(
            bounds, geo_constraints, ind_constraints
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
        geo_constraints = []
        ind_constraints = []

        summary = manager.get_constraint_summary(
            bounds, geo_constraints, ind_constraints
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
        geo_constraints = []
        ind_constraints = []

        summary = manager.get_constraint_summary(
            bounds, geo_constraints, ind_constraints
        )

        assert summary["total_stocks"] == 1
        assert summary["locked_positions"] == []
        assert summary["buy_only"] == []
        assert summary["sell_blocked"] == []

    def test_sector_constraints_included_in_summary(self):
        """Test sector constraints are included in summary."""
        manager = ConstraintsManager()
        bounds = {}
        geo_constraints = [
            SectorConstraint(
                name="US",
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
            bounds, geo_constraints, ind_constraints
        )

        assert len(summary["geography_constraints"]) == 1
        assert summary["geography_constraints"][0]["name"] == "US"
        assert summary["geography_constraints"][0]["target"] == 0.60
        assert summary["geography_constraints"][0]["range"] == (0.50, 0.70)

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
        geo_constraints = []
        ind_constraints = []

        summary = manager.get_constraint_summary(
            bounds, geo_constraints, ind_constraints
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

    def test_empty_targets(self):
        """Test with empty target dictionaries."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL")]

        geo_constraints, ind_constraints = manager.build_sector_constraints(
            stocks=stocks,
            geo_targets={},
            ind_targets={},
        )

        # Should return empty constraint lists
        assert geo_constraints == []
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

    def test_target_exceeds_one(self):
        """Test target weight > 1.0 is handled."""
        manager = ConstraintsManager()
        stocks = [create_stock("AAPL", geography="US")]
        # Invalid target > 1.0
        geo_targets = {"US": 1.5}
        ind_targets = {}

        geo_constraints, ind_constraints = manager.build_sector_constraints(
            stocks, geo_targets, ind_targets
        )

        # Should still create constraint (bounds will be clamped)
        assert len(geo_constraints) == 1
        assert geo_constraints[0].target == 1.5
        # Upper bound should be clamped to 1.0 by tolerance logic
        assert geo_constraints[0].upper <= 1.0

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
