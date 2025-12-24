"""Funding service for generating sell options to fund buy recommendations.

Provides 3-4 funding strategies when a buy recommendation can't be executed
due to insufficient cash. Each strategy shows which positions to sell with
warnings for rule overrides and net portfolio score impact.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from app.domain.repositories import (
    StockRepository,
    PositionRepository,
    AllocationRepository,
    PortfolioRepository,
)
from app.services.sell_scorer import (
    calculate_all_sell_scores,
    SellScore,
    TechnicalData,
    get_sell_settings,
    DEFAULT_MIN_HOLD_DAYS,
    DEFAULT_SELL_COOLDOWN_DAYS,
    DEFAULT_MAX_LOSS_THRESHOLD,
)
from app.services.scorer import (
    calculate_portfolio_score,
    calculate_post_transaction_score,
    PortfolioContext,
)
from app.services.tradernet import get_exchange_rate

logger = logging.getLogger(__name__)


@dataclass
class FundingSell:
    """A single sell in a funding plan."""
    symbol: str
    name: str
    quantity: int
    sell_pct: float  # e.g., 0.15 = 15% of position
    value_eur: float
    currency: str
    current_price: float
    avg_price: float
    profit_pct: float
    warnings: List[str] = field(default_factory=list)


@dataclass
class FundingOption:
    """A complete funding plan."""
    strategy: str  # "score_based", "minimal_sells", "overweight", "currency_match"
    description: str  # Human-readable description
    sells: List[FundingSell]
    total_sell_value: float
    buy_symbol: str
    buy_amount: float
    current_score: float
    new_score: float
    net_score_change: float
    has_warnings: bool


class FundingService:
    """Service for generating funding options to enable buy recommendations."""

    def __init__(
        self,
        stock_repo: StockRepository,
        position_repo: PositionRepository,
        allocation_repo: AllocationRepository,
        portfolio_repo: PortfolioRepository,
    ):
        self._stock_repo = stock_repo
        self._position_repo = position_repo
        self._allocation_repo = allocation_repo
        self._portfolio_repo = portfolio_repo

    async def get_funding_options(
        self,
        buy_symbol: str,
        buy_amount_eur: float,
        available_cash: float,
    ) -> List[FundingOption]:
        """
        Generate 3-4 funding options for a buy recommendation.

        Strategies:
        1. Score-based: Use sell scorer to pick best candidates
        2. Minimal sells: Fewest positions, larger chunks
        3. Overweight first: Prioritize overweight positions
        4. Currency match: Prefer same-currency sells (if applicable)

        Args:
            buy_symbol: Symbol of stock to buy
            buy_amount_eur: Amount needed in EUR
            available_cash: Current cash available in EUR

        Returns:
            List of FundingOption with different strategies
        """
        cash_needed = max(0, buy_amount_eur - available_cash)
        if cash_needed <= 0:
            logger.info(f"No funding needed for {buy_symbol}, cash available")
            return []

        # Add 5% buffer for safety
        cash_needed_with_buffer = cash_needed * 1.05

        # Get portfolio context
        portfolio_context = await self._build_portfolio_context()
        if not portfolio_context:
            logger.warning("Could not build portfolio context")
            return []

        # Get buy stock info
        buy_stock = await self._stock_repo.get_by_symbol(buy_symbol)
        if not buy_stock:
            logger.warning(f"Buy stock {buy_symbol} not found")
            return []

        buy_currency = self._determine_currency(buy_stock)

        # Get all positions with sell scores
        positions = await self._position_repo.get_with_stock_info()
        if not positions:
            logger.info("No positions available for selling")
            return []

        # Calculate sell scores for context (but we'll also consider blocked positions)
        sell_scores = await self._calculate_sell_scores(positions, portfolio_context)

        # Generate each strategy
        options = []

        # Strategy 1: Score-based (use sell scorer ranking)
        score_based = await self._generate_score_based_option(
            positions, sell_scores, cash_needed_with_buffer, buy_symbol, buy_amount_eur,
            portfolio_context, buy_stock
        )
        if score_based:
            options.append(score_based)

        # Strategy 2: Minimal sells (fewer positions, larger chunks)
        minimal = await self._generate_minimal_sells_option(
            positions, sell_scores, cash_needed_with_buffer, buy_symbol, buy_amount_eur,
            portfolio_context, buy_stock
        )
        if minimal:
            options.append(minimal)

        # Strategy 3: Overweight first (prioritize overweight positions)
        overweight = await self._generate_overweight_option(
            positions, sell_scores, cash_needed_with_buffer, buy_symbol, buy_amount_eur,
            portfolio_context, buy_stock
        )
        if overweight:
            options.append(overweight)

        # Strategy 4: Currency match (prefer same-currency sells)
        if buy_currency != "EUR":
            currency_match = await self._generate_currency_match_option(
                positions, sell_scores, cash_needed_with_buffer, buy_symbol, buy_amount_eur,
                portfolio_context, buy_stock, buy_currency
            )
            if currency_match:
                options.append(currency_match)

        # Sort by net score change (best improvement first)
        options.sort(key=lambda x: x.net_score_change, reverse=True)

        return options

    async def _build_portfolio_context(self) -> Optional[PortfolioContext]:
        """Build portfolio context for scoring calculations."""
        from app.application.services.portfolio_service import PortfolioService

        portfolio_service = PortfolioService(
            self._portfolio_repo,
            self._position_repo,
            self._allocation_repo,
        )
        summary = await portfolio_service.get_portfolio_summary()

        if not summary or summary.total_value <= 0:
            return None

        # Build weight maps
        geo_weights = {a.name: a.target_pct for a in summary.geographic_allocations}
        industry_weights = {a.name: a.target_pct for a in summary.industry_allocations}

        # Get stock data for portfolio context
        stocks_data = await self._stock_repo.get_with_scores()

        positions = {}
        stock_geographies = {}
        stock_industries = {}
        stock_scores = {}
        stock_dividends = {}

        for stock in stocks_data:
            symbol = stock["symbol"]
            position_value = stock.get("position_value") or 0
            if position_value > 0:
                positions[symbol] = position_value
            stock_geographies[symbol] = stock.get("geography", "")
            stock_industries[symbol] = stock.get("industry")
            stock_scores[symbol] = stock.get("quality_score") or stock.get("total_score") or 0.5
            stock_dividends[symbol] = stock.get("dividend_yield") or 0

        return PortfolioContext(
            geo_weights=geo_weights,
            industry_weights=industry_weights,
            positions=positions,
            total_value=summary.total_value,
            stock_geographies=stock_geographies,
            stock_industries=stock_industries,
            stock_scores=stock_scores,
            stock_dividends=stock_dividends,
        )

    async def _calculate_sell_scores(
        self,
        positions: List[dict],
        portfolio_context: PortfolioContext
    ) -> Dict[str, SellScore]:
        """Calculate sell scores for all positions."""
        from app.application.services.portfolio_service import PortfolioService

        portfolio_service = PortfolioService(
            self._portfolio_repo,
            self._position_repo,
            self._allocation_repo,
        )
        summary = await portfolio_service.get_portfolio_summary()

        geo_allocations = {a.name: a.current_pct for a in summary.geographic_allocations}
        ind_allocations = {a.name: a.current_pct for a in summary.industry_allocations}

        # Load settings from database
        settings = await get_sell_settings()

        scores = calculate_all_sell_scores(
            positions=positions,
            total_portfolio_value=portfolio_context.total_value,
            geo_allocations=geo_allocations,
            ind_allocations=ind_allocations,
            settings=settings,
        )

        return {s.symbol: s for s in scores}

    def _determine_currency(self, stock) -> str:
        """Determine currency for a stock (Stock object or dict)."""
        # Handle both Stock objects and dicts
        if hasattr(stock, 'geography'):
            # Stock object
            geography = (stock.geography or "").upper()
            yahoo_symbol = stock.yahoo_symbol or ""
        else:
            # Dict (from get_with_scores)
            currency = stock.get("currency")
            if currency:
                return currency
            geography = stock.get("geography", "").upper()
            yahoo_symbol = stock.get("yahoo_symbol", "")

        if geography == "EU":
            return "EUR"
        elif geography == "US":
            return "USD"
        elif geography == "ASIA":
            if yahoo_symbol and ".HK" in yahoo_symbol:
                return "HKD"
            return "HKD"
        return "EUR"

    def _get_warnings_for_position(self, pos: dict) -> List[str]:
        """Check for sell rule violations and generate warnings."""
        warnings = []

        # Check allow_sell flag
        if not pos.get("allow_sell", False):
            warnings.append("Position marked as 'do not sell'")

        # Check minimum hold time
        first_bought_at = pos.get("first_bought_at")
        if first_bought_at:
            try:
                bought_date = datetime.fromisoformat(first_bought_at.replace('Z', '+00:00'))
                if bought_date.tzinfo:
                    bought_date = bought_date.replace(tzinfo=None)
                days_held = (datetime.now() - bought_date).days
                if days_held < DEFAULT_MIN_HOLD_DAYS:
                    warnings.append(f"Held only {days_held} days (min: {DEFAULT_MIN_HOLD_DAYS})")
            except (ValueError, TypeError):
                pass

        # Check sell cooldown
        last_sold_at = pos.get("last_sold_at")
        if last_sold_at:
            try:
                sold_date = datetime.fromisoformat(last_sold_at.replace('Z', '+00:00'))
                if sold_date.tzinfo:
                    sold_date = sold_date.replace(tzinfo=None)
                days_since_sell = (datetime.now() - sold_date).days
                if days_since_sell < DEFAULT_SELL_COOLDOWN_DAYS:
                    warnings.append(f"Sold {days_since_sell} days ago (cooldown: {DEFAULT_SELL_COOLDOWN_DAYS})")
            except (ValueError, TypeError):
                pass

        # Check loss threshold
        avg_price = pos.get("avg_price", 0)
        current_price = pos.get("current_price", 0)
        if avg_price > 0 and current_price > 0:
            profit_pct = (current_price - avg_price) / avg_price
            if profit_pct < DEFAULT_MAX_LOSS_THRESHOLD:
                warnings.append(f"Loss of {profit_pct*100:.1f}% exceeds {DEFAULT_MAX_LOSS_THRESHOLD*100:.0f}% threshold")

        return warnings

    def _create_funding_sell(
        self,
        pos: dict,
        quantity: int,
        sell_pct: float,
    ) -> FundingSell:
        """Create a FundingSell from position data."""
        currency = pos.get("currency", "EUR")
        current_price = pos.get("current_price") or pos.get("avg_price", 0)
        avg_price = pos.get("avg_price", 0)

        # Calculate value in EUR
        value_native = quantity * current_price
        if currency != "EUR":
            exchange_rate = get_exchange_rate(currency, "EUR")
            value_eur = value_native / exchange_rate if exchange_rate > 0 else value_native
        else:
            value_eur = value_native

        profit_pct = (current_price - avg_price) / avg_price if avg_price > 0 else 0
        warnings = self._get_warnings_for_position(pos)

        return FundingSell(
            symbol=pos["symbol"],
            name=pos.get("name", pos["symbol"]),
            quantity=quantity,
            sell_pct=sell_pct,
            value_eur=round(value_eur, 2),
            currency=currency,
            current_price=current_price,
            avg_price=avg_price,
            profit_pct=round(profit_pct, 4),
            warnings=warnings,
        )

    def _calculate_net_score_change(
        self,
        sells: List[FundingSell],
        buy_symbol: str,
        buy_amount_eur: float,
        portfolio_context: PortfolioContext,
        buy_stock: dict,
    ) -> tuple[float, float, float]:
        """
        Calculate net portfolio score change for sells + buy.

        Returns:
            (current_score, new_score, net_change)
        """
        current_score = calculate_portfolio_score(portfolio_context)

        # Create modified context after sells
        modified_positions = dict(portfolio_context.positions)
        for sell in sells:
            if sell.symbol in modified_positions:
                modified_positions[sell.symbol] -= sell.value_eur
                if modified_positions[sell.symbol] <= 0:
                    del modified_positions[sell.symbol]

        total_sell_value = sum(s.value_eur for s in sells)
        new_total_value = portfolio_context.total_value - total_sell_value + buy_amount_eur

        modified_context = PortfolioContext(
            geo_weights=portfolio_context.geo_weights,
            industry_weights=portfolio_context.industry_weights,
            positions=modified_positions,
            total_value=new_total_value,
            stock_geographies=portfolio_context.stock_geographies,
            stock_industries=portfolio_context.stock_industries,
            stock_scores=portfolio_context.stock_scores,
            stock_dividends=portfolio_context.stock_dividends,
        )

        # Calculate post-transaction score (with buy)
        # buy_stock is a Stock object, access attributes directly
        buy_geography = buy_stock.geography or ""
        buy_industry = buy_stock.industry
        # Get quality score and dividend from portfolio context if available
        buy_quality = portfolio_context.stock_scores.get(buy_symbol, 0.5)
        buy_dividend = portfolio_context.stock_dividends.get(buy_symbol, 0)

        new_score, score_change = calculate_post_transaction_score(
            symbol=buy_symbol,
            geography=buy_geography,
            industry=buy_industry,
            proposed_value=buy_amount_eur,
            stock_quality=buy_quality,
            stock_dividend=buy_dividend,
            portfolio_context=modified_context,
        )

        return current_score.total, new_score.total, new_score.total - current_score.total

    async def _generate_score_based_option(
        self,
        positions: List[dict],
        sell_scores: Dict[str, SellScore],
        cash_needed: float,
        buy_symbol: str,
        buy_amount_eur: float,
        portfolio_context: PortfolioContext,
        buy_stock: dict,
    ) -> Optional[FundingOption]:
        """Generate option using sell scorer ranking."""
        # Sort positions by sell score (highest first)
        sorted_positions = sorted(
            positions,
            key=lambda p: sell_scores.get(p["symbol"], SellScore(
                symbol=p["symbol"], eligible=False, block_reason="", underperformance_score=0,
                time_held_score=0, portfolio_balance_score=0, instability_score=0, total_score=0,
                suggested_sell_pct=0, suggested_sell_quantity=0, suggested_sell_value=0,
                profit_pct=0, days_held=0
            )).total_score,
            reverse=True
        )

        sells = []
        total_value = 0.0

        for pos in sorted_positions:
            if pos["symbol"] == buy_symbol:
                continue  # Don't sell what we're trying to buy

            if total_value >= cash_needed:
                break

            score = sell_scores.get(pos["symbol"])
            quantity = pos.get("quantity", 0)
            min_lot = pos.get("min_lot", 1)
            current_price = pos.get("current_price") or pos.get("avg_price", 0)

            if quantity <= 0 or current_price <= 0:
                continue

            # Use suggested sell quantity from scorer, or calculate 15-25%
            if score and score.eligible and score.suggested_sell_quantity > 0:
                sell_qty = score.suggested_sell_quantity
            else:
                # Calculate 20% of position, rounded to min_lot
                sell_pct = 0.20
                sell_qty = int((quantity * sell_pct) // min_lot) * min_lot
                if sell_qty < min_lot:
                    sell_qty = min_lot

            # Don't sell entire position
            if sell_qty >= quantity:
                sell_qty = int((quantity - min_lot) // min_lot) * min_lot
                if sell_qty <= 0:
                    continue

            sell_pct = sell_qty / quantity
            funding_sell = self._create_funding_sell(pos, sell_qty, sell_pct)
            sells.append(funding_sell)
            total_value += funding_sell.value_eur

        if not sells or total_value < cash_needed * 0.9:  # Need at least 90% of target
            return None

        current_score, new_score, net_change = self._calculate_net_score_change(
            sells, buy_symbol, buy_amount_eur, portfolio_context, buy_stock
        )

        return FundingOption(
            strategy="score_based",
            description="Sell based on underperformance scoring",
            sells=sells,
            total_sell_value=round(total_value, 2),
            buy_symbol=buy_symbol,
            buy_amount=buy_amount_eur,
            current_score=round(current_score, 1),
            new_score=round(new_score, 1),
            net_score_change=round(net_change, 2),
            has_warnings=any(s.warnings for s in sells),
        )

    async def _generate_minimal_sells_option(
        self,
        positions: List[dict],
        sell_scores: Dict[str, SellScore],
        cash_needed: float,
        buy_symbol: str,
        buy_amount_eur: float,
        portfolio_context: PortfolioContext,
        buy_stock: dict,
    ) -> Optional[FundingOption]:
        """Generate option with fewest positions, larger chunks."""
        # Sort positions by value (largest first for fewer transactions)
        sorted_positions = sorted(
            positions,
            key=lambda p: (p.get("current_price", 0) or p.get("avg_price", 0)) * p.get("quantity", 0),
            reverse=True
        )

        sells = []
        total_value = 0.0

        for pos in sorted_positions:
            if pos["symbol"] == buy_symbol:
                continue

            if total_value >= cash_needed:
                break

            quantity = pos.get("quantity", 0)
            min_lot = pos.get("min_lot", 1)
            current_price = pos.get("current_price") or pos.get("avg_price", 0)

            if quantity <= 0 or current_price <= 0:
                continue

            # Sell up to 40% of position (larger chunks for minimal sells)
            remaining_needed = cash_needed - total_value

            # Calculate position value in EUR
            currency = pos.get("currency", "EUR")
            if currency != "EUR":
                exchange_rate = get_exchange_rate(currency, "EUR")
                price_eur = current_price / exchange_rate if exchange_rate > 0 else current_price
            else:
                price_eur = current_price

            position_value = quantity * price_eur

            # How much of this position do we need?
            needed_pct = min(0.40, remaining_needed / position_value) if position_value > 0 else 0.40

            sell_qty = int((quantity * needed_pct) // min_lot) * min_lot
            if sell_qty < min_lot:
                sell_qty = min_lot

            # Don't sell entire position
            if sell_qty >= quantity:
                sell_qty = int((quantity - min_lot) // min_lot) * min_lot
                if sell_qty <= 0:
                    continue

            sell_pct = sell_qty / quantity
            funding_sell = self._create_funding_sell(pos, sell_qty, sell_pct)
            sells.append(funding_sell)
            total_value += funding_sell.value_eur

        if not sells or total_value < cash_needed * 0.9:
            return None

        current_score, new_score, net_change = self._calculate_net_score_change(
            sells, buy_symbol, buy_amount_eur, portfolio_context, buy_stock
        )

        return FundingOption(
            strategy="minimal_sells",
            description="Minimize number of sell transactions",
            sells=sells,
            total_sell_value=round(total_value, 2),
            buy_symbol=buy_symbol,
            buy_amount=buy_amount_eur,
            current_score=round(current_score, 1),
            new_score=round(new_score, 1),
            net_score_change=round(net_change, 2),
            has_warnings=any(s.warnings for s in sells),
        )

    async def _generate_overweight_option(
        self,
        positions: List[dict],
        sell_scores: Dict[str, SellScore],
        cash_needed: float,
        buy_symbol: str,
        buy_amount_eur: float,
        portfolio_context: PortfolioContext,
        buy_stock: dict,
    ) -> Optional[FundingOption]:
        """Generate option prioritizing overweight positions."""
        # Sort by portfolio balance score (overweight first)
        sorted_positions = sorted(
            positions,
            key=lambda p: sell_scores.get(p["symbol"], SellScore(
                symbol=p["symbol"], eligible=False, block_reason="", underperformance_score=0,
                time_held_score=0, portfolio_balance_score=0, instability_score=0, total_score=0,
                suggested_sell_pct=0, suggested_sell_quantity=0, suggested_sell_value=0,
                profit_pct=0, days_held=0
            )).portfolio_balance_score,
            reverse=True
        )

        sells = []
        total_value = 0.0

        for pos in sorted_positions:
            if pos["symbol"] == buy_symbol:
                continue

            if total_value >= cash_needed:
                break

            score = sell_scores.get(pos["symbol"])
            quantity = pos.get("quantity", 0)
            min_lot = pos.get("min_lot", 1)
            current_price = pos.get("current_price") or pos.get("avg_price", 0)

            if quantity <= 0 or current_price <= 0:
                continue

            # For overweight positions, sell more aggressively (up to 35%)
            sell_pct = 0.35 if score and score.portfolio_balance_score >= 0.7 else 0.20
            sell_qty = int((quantity * sell_pct) // min_lot) * min_lot
            if sell_qty < min_lot:
                sell_qty = min_lot

            # Don't sell entire position
            if sell_qty >= quantity:
                sell_qty = int((quantity - min_lot) // min_lot) * min_lot
                if sell_qty <= 0:
                    continue

            actual_pct = sell_qty / quantity
            funding_sell = self._create_funding_sell(pos, sell_qty, actual_pct)
            sells.append(funding_sell)
            total_value += funding_sell.value_eur

        if not sells or total_value < cash_needed * 0.9:
            return None

        current_score, new_score, net_change = self._calculate_net_score_change(
            sells, buy_symbol, buy_amount_eur, portfolio_context, buy_stock
        )

        return FundingOption(
            strategy="overweight",
            description="Reduce overweight positions first",
            sells=sells,
            total_sell_value=round(total_value, 2),
            buy_symbol=buy_symbol,
            buy_amount=buy_amount_eur,
            current_score=round(current_score, 1),
            new_score=round(new_score, 1),
            net_score_change=round(net_change, 2),
            has_warnings=any(s.warnings for s in sells),
        )

    async def _generate_currency_match_option(
        self,
        positions: List[dict],
        sell_scores: Dict[str, SellScore],
        cash_needed: float,
        buy_symbol: str,
        buy_amount_eur: float,
        portfolio_context: PortfolioContext,
        buy_stock: dict,
        target_currency: str,
    ) -> Optional[FundingOption]:
        """Generate option preferring same-currency sells."""
        # Separate positions by currency
        matching_currency = [p for p in positions if p.get("currency", "EUR") == target_currency]
        other_currency = [p for p in positions if p.get("currency", "EUR") != target_currency]

        # Sort each group by sell score
        matching_currency.sort(
            key=lambda p: sell_scores.get(p["symbol"], SellScore(
                symbol=p["symbol"], eligible=False, block_reason="", underperformance_score=0,
                time_held_score=0, portfolio_balance_score=0, instability_score=0, total_score=0,
                suggested_sell_pct=0, suggested_sell_quantity=0, suggested_sell_value=0,
                profit_pct=0, days_held=0
            )).total_score,
            reverse=True
        )

        # Prioritize matching currency, then fall back to others
        sorted_positions = matching_currency + other_currency

        sells = []
        total_value = 0.0

        for pos in sorted_positions:
            if pos["symbol"] == buy_symbol:
                continue

            if total_value >= cash_needed:
                break

            score = sell_scores.get(pos["symbol"])
            quantity = pos.get("quantity", 0)
            min_lot = pos.get("min_lot", 1)
            current_price = pos.get("current_price") or pos.get("avg_price", 0)

            if quantity <= 0 or current_price <= 0:
                continue

            # Use standard 20% or suggested amount
            if score and score.eligible and score.suggested_sell_quantity > 0:
                sell_qty = score.suggested_sell_quantity
            else:
                sell_qty = int((quantity * 0.20) // min_lot) * min_lot
                if sell_qty < min_lot:
                    sell_qty = min_lot

            # Don't sell entire position
            if sell_qty >= quantity:
                sell_qty = int((quantity - min_lot) // min_lot) * min_lot
                if sell_qty <= 0:
                    continue

            sell_pct = sell_qty / quantity
            funding_sell = self._create_funding_sell(pos, sell_qty, sell_pct)
            sells.append(funding_sell)
            total_value += funding_sell.value_eur

        if not sells or total_value < cash_needed * 0.9:
            return None

        current_score, new_score, net_change = self._calculate_net_score_change(
            sells, buy_symbol, buy_amount_eur, portfolio_context, buy_stock
        )

        return FundingOption(
            strategy="currency_match",
            description=f"Prefer selling {target_currency} positions",
            sells=sells,
            total_sell_value=round(total_value, 2),
            buy_symbol=buy_symbol,
            buy_amount=buy_amount_eur,
            current_score=round(current_score, 1),
            new_score=round(new_score, 1),
            net_score_change=round(net_change, 2),
            has_warnings=any(s.warnings for s in sells),
        )
