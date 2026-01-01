"""Local Opportunity Service - Domain service wrapper for opportunity identification."""

from typing import List

from app.domain.models import Position, Security
from app.modules.planning.domain.holistic_planner import (
    identify_opportunities,
    identify_opportunities_from_weights,
)
from app.modules.planning.domain.models import ActionCandidate
from app.modules.scoring.domain.models import PortfolioContext
from services.opportunity.models import (
    ActionCandidateModel,
    IdentifyOpportunitiesRequest,
    IdentifyOpportunitiesResponse,
)


class LocalOpportunityService:
    """
    Service for identifying trading opportunities.

    Wraps the opportunity identification logic from holistic_planner.py
    for use by the Opportunity microservice.
    """

    def __init__(self):
        """Initialize the service."""
        pass

    async def identify_opportunities(
        self, request: IdentifyOpportunitiesRequest
    ) -> IdentifyOpportunitiesResponse:
        """
        Identify trading opportunities from portfolio state.

        Uses weight-based identification if target_weights provided,
        otherwise falls back to heuristic-based identification.

        Args:
            request: Portfolio context, positions, securities, and parameters

        Returns:
            Categorized opportunities
        """
        # Convert Pydantic models to domain models
        portfolio_context = self._to_portfolio_context(request)
        positions = self._to_positions(request.positions)
        securities = self._to_securities(request.securities)

        # Convert recently_sold and ineligible_symbols to sets if provided
        recently_sold = set(request.recently_sold) if request.recently_sold else None
        ineligible_symbols = (
            set(request.ineligible_symbols) if request.ineligible_symbols else None
        )

        # Call domain logic
        if request.target_weights:
            opportunities = await identify_opportunities_from_weights(
                target_weights=request.target_weights,
                portfolio_context=portfolio_context,
                positions=positions,
                securities=securities,
                available_cash=request.available_cash,
                current_prices=request.current_prices or {},
                transaction_cost_fixed=request.transaction_cost_fixed,
                transaction_cost_percent=request.transaction_cost_percent,
                recently_sold=recently_sold,
                ineligible_symbols=ineligible_symbols,
            )
        else:
            opportunities = await identify_opportunities(
                portfolio_context=portfolio_context,
                positions=positions,
                securities=securities,
                available_cash=request.available_cash,
            )

        # Convert domain models back to Pydantic
        return IdentifyOpportunitiesResponse(
            profit_taking=[
                self._action_candidate_to_model(a)
                for a in opportunities.get("profit_taking", [])
            ],
            averaging_down=[
                self._action_candidate_to_model(a)
                for a in opportunities.get("averaging_down", [])
            ],
            rebalance_sells=[
                self._action_candidate_to_model(a)
                for a in opportunities.get("rebalance_sells", [])
            ],
            rebalance_buys=[
                self._action_candidate_to_model(a)
                for a in opportunities.get("rebalance_buys", [])
            ],
            opportunity_buys=[
                self._action_candidate_to_model(a)
                for a in opportunities.get("opportunity_buys", [])
            ],
        )

    def _to_portfolio_context(
        self, request: IdentifyOpportunitiesRequest
    ) -> PortfolioContext:
        """Convert request to PortfolioContext domain model."""
        return PortfolioContext(
            total_value=request.portfolio_context.total_value,
            positions=request.portfolio_context.positions,
            country_weights=request.portfolio_context.country_weights,
            industry_weights=request.portfolio_context.industry_weights,
            security_countries=request.portfolio_context.security_countries,
            security_industries=request.portfolio_context.security_industries,
        )

    def _to_positions(self, positions_input: List) -> List[Position]:
        """Convert Pydantic position models to domain Position models."""
        from app.shared.domain.value_objects.currency import Currency

        return [
            Position(
                symbol=p.symbol,
                quantity=p.quantity,
                avg_price=p.avg_price,
                current_price=(
                    p.market_value_eur / p.quantity if p.quantity > 0 else p.avg_price
                ),
                market_value_eur=p.market_value_eur,
                currency=Currency.EUR,
                unrealized_pnl_pct=p.unrealized_pnl_pct,
            )
            for p in positions_input
        ]

    def _to_securities(self, securities_input: List) -> List[Security]:
        """Convert Pydantic security models to domain Security models."""
        from app.domain.value_objects.product_type import ProductType

        return [
            Security(
                symbol=s.symbol,
                name=s.name,
                isin=getattr(s, "isin", None),
                country=getattr(s, "country", None),
                industry=getattr(s, "industry", None),
                allow_buy=getattr(s, "allow_buy", True),
                allow_sell=getattr(s, "allow_sell", True),
                product_type=ProductType.EQUITY,  # Default to EQUITY for planning
            )
            for s in securities_input
        ]

    def _action_candidate_to_model(
        self, action: ActionCandidate
    ) -> ActionCandidateModel:
        """
        Convert domain ActionCandidate to Pydantic model.

        Args:
            action: Domain ActionCandidate

        Returns:
            ActionCandidateModel for API response
        """
        return ActionCandidateModel(
            side=action.side.value if hasattr(action.side, "value") else action.side,
            symbol=action.symbol,
            name=action.name,
            quantity=action.quantity,
            price=action.price,
            value_eur=action.value_eur,
            currency=action.currency,
            priority=action.priority,
            reason=action.reason,
            tags=action.tags if hasattr(action, "tags") else [],
        )
