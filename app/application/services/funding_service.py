"""Funding service for generating sell options to fund buy recommendations.

Provides multiple funding strategies when a buy recommendation can't be executed
due to insufficient cash. Each strategy shows which positions to sell with
warnings for rule overrides and net portfolio score impact.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Callable

from app.repositories import (
    StockRepository,
    PositionRepository,
    AllocationRepository,
    PortfolioRepository,
)
from app.domain.scoring import (
    calculate_all_sell_scores,
    calculate_portfolio_score,
    calculate_post_transaction_score,
    get_sell_settings,
    SellScore,
    PortfolioContext,
    DEFAULT_MIN_HOLD_DAYS,
    DEFAULT_SELL_COOLDOWN_DAYS,
    DEFAULT_MAX_LOSS_THRESHOLD,
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
    strategy: str
    description: str
    sells: List[FundingSell]
    total_sell_value: float
    buy_symbol: str
    buy_amount: float
    current_score: float
    new_score: float
    net_score_change: float
    has_warnings: bool
    signature: str = ""


@dataclass
class StrategyConfig:
    """Configuration for a funding strategy."""
    name: str
    description: str
    sort_key: Callable[[dict, Dict[str, 'SellScore']], tuple]
    sell_pct: float = 0.20  # Default sell percentage
    max_sell_pct: float = 0.40  # Cap for dynamic sell calculation
    include_blocked: bool = True  # Whether to fall back to blocked positions
    use_scorer_suggestion: bool = True  # Use sell scorer's suggested quantity


def _default_sell_score() -> SellScore:
    """Create a default SellScore for positions without scores."""
    return SellScore(
        symbol="", eligible=False, block_reason="",
        underperformance_score=0, time_held_score=0,
        portfolio_balance_score=0, instability_score=0, total_score=0,
        suggested_sell_pct=0, suggested_sell_quantity=0, suggested_sell_value=0,
        profit_pct=0, days_held=0
    )


def _get_option_signature(sells: List[FundingSell]) -> str:
    """Create unique signature from sells to detect duplicates."""
    sells_key = tuple(sorted((s.symbol, round(s.sell_pct, 2)) for s in sells))
    return str(sells_key)


def _partition_positions(
    positions: List[dict],
    sell_scores: Dict[str, 'SellScore']
) -> tuple[List[dict], List[dict]]:
    """Partition positions into eligible and blocked."""
    eligible = []
    blocked = []
    for pos in positions:
        score = sell_scores.get(pos["symbol"])
        if score and score.eligible:
            eligible.append(pos)
        else:
            blocked.append(pos)
    return eligible, blocked


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
        exclude_signatures: Optional[List[str]] = None,
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
            exclude_signatures: List of signatures to exclude (for pagination)

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

        # Define strategies using StrategyConfig
        strategies = [
            StrategyConfig(
                name="score_based",
                description="Sell lowest-scoring positions first",
                sort_key=self._sort_by_score_asc,
                sell_pct=0.20,
            ),
            StrategyConfig(
                name="minimal_sells",
                description="Minimize number of sell transactions",
                sort_key=self._sort_by_value_desc,
                sell_pct=0.20,
                max_sell_pct=0.40,
                use_scorer_suggestion=False,
            ),
            StrategyConfig(
                name="overweight",
                description="Reduce overweight positions first",
                sort_key=self._sort_by_overweight,
                sell_pct=0.20,
                max_sell_pct=0.35,
            ),
            StrategyConfig(
                name="eligible_only",
                description="Only sell positions with no restrictions",
                sort_key=self._sort_by_score_asc,
                sell_pct=0.25,
                include_blocked=False,
            ),
            StrategyConfig(
                name="spread_thin",
                description="Sell small amounts from many positions",
                sort_key=self._sort_by_score_asc,
                sell_pct=0.12,
                use_scorer_suggestion=False,
            ),
        ]

        # Add currency match strategy if applicable
        if buy_currency != "EUR":
            strategies.insert(3, StrategyConfig(
                name="currency_match",
                description=f"Prefer selling {buy_currency} positions",
                sort_key=self._sort_by_currency_then_score(buy_currency),
                sell_pct=0.20,
            ))

        # Generate options for all strategies
        options = []
        for config in strategies:
            option = await self._generate_option(
                positions, sell_scores, cash_needed_with_buffer, buy_symbol,
                buy_amount_eur, portfolio_context, buy_stock, config
            )
            if option:
                options.append(option)

        # Assign signatures and deduplicate (including excluded from previous pages)
        seen_signatures = set(exclude_signatures or [])
        unique_options = []
        for option in options:
            sig = _get_option_signature(option.sells)
            option.signature = sig
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                unique_options.append(option)

        # Sort by net score change (best improvement first)
        unique_options.sort(key=lambda x: x.net_score_change, reverse=True)

        return unique_options

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

        scores = await calculate_all_sell_scores(
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

    def _calculate_sell_quantity(
        self,
        pos: dict,
        sell_scores: Dict[str, SellScore],
        config: StrategyConfig,
        cash_needed: float,
        total_value: float,
    ) -> Optional[int]:
        """Calculate sell quantity for a position based on strategy config."""
        quantity = pos.get("quantity", 0)
        min_lot = pos.get("min_lot", 1)
        current_price = pos.get("current_price") or pos.get("avg_price", 0)

        if quantity <= 0 or current_price <= 0:
            return None

        score = sell_scores.get(pos["symbol"])

        # Use scorer suggestion if enabled and available
        if config.use_scorer_suggestion and score and score.eligible and score.suggested_sell_quantity > 0:
            sell_qty = score.suggested_sell_quantity
        else:
            # Calculate based on strategy's sell_pct or dynamically based on need
            if config.max_sell_pct > config.sell_pct:
                # Dynamic calculation (for minimal_sells strategy)
                currency = pos.get("currency", "EUR")
                if currency != "EUR":
                    exchange_rate = get_exchange_rate(currency, "EUR")
                    price_eur = current_price / exchange_rate if exchange_rate > 0 else current_price
                else:
                    price_eur = current_price
                position_value = quantity * price_eur
                remaining_needed = cash_needed - total_value
                needed_pct = min(config.max_sell_pct, remaining_needed / position_value) if position_value > 0 else config.sell_pct
                sell_pct = max(config.sell_pct, needed_pct)
            else:
                sell_pct = config.sell_pct

            # For overweight strategy, sell more aggressively
            if score and score.portfolio_balance_score >= 0.7 and config.sell_pct < 0.35:
                sell_pct = min(0.35, config.max_sell_pct)

            sell_qty = int((quantity * sell_pct) // min_lot) * min_lot
            if sell_qty < min_lot:
                sell_qty = min_lot

        # Don't sell entire position
        if sell_qty >= quantity:
            sell_qty = int((quantity - min_lot) // min_lot) * min_lot
            if sell_qty <= 0:
                return None

        return sell_qty

    async def _generate_option(
        self,
        positions: List[dict],
        sell_scores: Dict[str, SellScore],
        cash_needed: float,
        buy_symbol: str,
        buy_amount_eur: float,
        portfolio_context: PortfolioContext,
        buy_stock: dict,
        config: StrategyConfig,
    ) -> Optional[FundingOption]:
        """
        Generate a funding option using the given strategy configuration.

        This is the single implementation for all funding strategies.
        Strategy-specific behavior is controlled via StrategyConfig.
        """
        # Partition into eligible and blocked positions
        eligible, blocked = _partition_positions(positions, sell_scores)

        # Sort eligible positions using strategy's sort key
        eligible.sort(key=lambda p: config.sort_key(p, sell_scores))

        sells = []
        total_value = 0.0

        # First pass: try eligible positions only
        for pos in eligible:
            if pos["symbol"] == buy_symbol:
                continue
            if total_value >= cash_needed:
                break

            sell_qty = self._calculate_sell_quantity(pos, sell_scores, config, cash_needed, total_value)
            if sell_qty is None:
                continue

            quantity = pos.get("quantity", 0)
            sell_pct = sell_qty / quantity
            funding_sell = self._create_funding_sell(pos, sell_qty, sell_pct)
            sells.append(funding_sell)
            total_value += funding_sell.value_eur

        # Second pass: if not enough and include_blocked is True, add blocked positions
        if config.include_blocked and total_value < cash_needed * 0.9:
            # Sort blocked positions the same way
            blocked.sort(key=lambda p: config.sort_key(p, sell_scores))
            for pos in blocked:
                if pos["symbol"] == buy_symbol:
                    continue
                if total_value >= cash_needed:
                    break

                sell_qty = self._calculate_sell_quantity(pos, sell_scores, config, cash_needed, total_value)
                if sell_qty is None:
                    continue

                quantity = pos.get("quantity", 0)
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
            strategy=config.name,
            description=config.description,
            sells=sells,
            total_sell_value=round(total_value, 2),
            buy_symbol=buy_symbol,
            buy_amount=buy_amount_eur,
            current_score=round(current_score, 1),
            new_score=round(new_score, 1),
            net_score_change=round(net_change, 2),
            has_warnings=any(s.warnings for s in sells),
        )

    # Strategy sort key functions
    @staticmethod
    def _sort_by_score_asc(pos: dict, sell_scores: Dict[str, SellScore]) -> tuple:
        """Sort by total score ascending (worst performers first)."""
        score = sell_scores.get(pos["symbol"], _default_sell_score())
        return (score.total_score,)

    @staticmethod
    def _sort_by_value_desc(pos: dict, sell_scores: Dict[str, SellScore]) -> tuple:
        """Sort by position value descending (largest first)."""
        value = (pos.get("current_price", 0) or pos.get("avg_price", 0)) * pos.get("quantity", 0)
        return (-value,)

    @staticmethod
    def _sort_by_overweight(pos: dict, sell_scores: Dict[str, SellScore]) -> tuple:
        """Sort by portfolio balance score descending (most overweight first)."""
        score = sell_scores.get(pos["symbol"], _default_sell_score())
        return (-score.portfolio_balance_score,)

    def _sort_by_currency_then_score(self, target_currency: str):
        """Create sort key that prefers matching currency, then sorts by score."""
        def sort_key(pos: dict, sell_scores: Dict[str, SellScore]) -> tuple:
            currency_match = 0 if pos.get("currency", "EUR") == target_currency else 1
            score = sell_scores.get(pos["symbol"], _default_sell_score())
            return (currency_match, score.total_score)
        return sort_key
