"""
Planner - Generate trade recommendations based on expected returns.

The planner:
1. Calculates the ideal portfolio (allocated by expected returns)
2. Compares current vs ideal allocations
3. Generates trade recommendations to move toward the ideal

Usage:
    planner = Planner()
    trades = await planner.get_recommendations()
    ideal = await planner.calculate_ideal_portfolio()
"""

import asyncio
from dataclasses import dataclass, asdict
from typing import Optional
from sentinel.database import Database
from sentinel.portfolio import Portfolio
from sentinel.analyzer import Analyzer
from sentinel.settings import Settings
from sentinel.currency import Currency
from sentinel.broker import Broker
from sentinel.price_validator import check_trade_blocking, PriceValidator
from sentinel.ml_predictor import MLPredictor
from sentinel.ml_features import FeatureExtractor
import pandas as pd
import json


@dataclass
class TradeRecommendation:
    """A recommended trade to move toward ideal portfolio."""
    symbol: str
    action: str  # 'buy' or 'sell'
    current_allocation: float  # Current % of portfolio
    target_allocation: float  # Target % of portfolio
    allocation_delta: float  # Target - Current (positive = underweight)
    current_value_eur: float
    target_value_eur: float
    value_delta_eur: float  # Amount to buy (+) or sell (-)
    quantity: int  # Number of shares/units to trade (rounded to lot size)
    price: float  # Current price per share
    currency: str  # Security's trading currency
    lot_size: int  # Minimum lot size
    expected_return: float  # The security's expected return score
    priority: float  # Higher = more urgent to act on
    reason: str  # Human-readable explanation


class Planner:
    """Generates trade recommendations based on expected returns."""

    def __init__(self, db=None, broker=None, portfolio=None):
        """
        Initialize planner with optional dependency injection.

        Args:
            db: Database instance (uses singleton if None)
            broker: Broker instance (uses singleton if None)
            portfolio: Portfolio instance (uses singleton if None)
        """
        self._db = db or Database()
        self._broker = broker or Broker()
        self._portfolio = portfolio or Portfolio()
        self._analyzer = Analyzer(db=self._db)
        self._settings = Settings()
        self._currency = Currency()
        self._ml_predictor = MLPredictor()
        self._feature_extractor = FeatureExtractor(db=self._db)

    def _calculate_diversification_score(
        self,
        security: dict,
        current_allocs: dict,
        target_allocs: dict,
    ) -> float:
        """
        Calculate diversification score for a security.

        Returns a value from -1 (heavily overweight categories) to +1 (heavily underweight).
        Securities with multiple categories get averaged scores.

        Args:
            security: Security dict with geography/industry fields
            current_allocs: Current allocations from portfolio.get_allocations()
            target_allocs: Target allocations from portfolio.get_target_allocations()

        Returns:
            float: Diversification score clamped to [-1, +1]
        """
        deviations = []

        # Parse comma-separated geographies
        geo_str = security.get('geography', '') or ''
        geos = [g.strip() for g in geo_str.split(',') if g.strip()]

        # Parse comma-separated industries
        ind_str = security.get('industry', '') or ''
        inds = [i.strip() for i in ind_str.split(',') if i.strip()]

        # Calculate deviation for each geography
        for geo in geos:
            target = target_allocs.get('geography', {}).get(geo, 0)
            current = current_allocs.get('by_geography', {}).get(geo, 0)
            # Positive deviation = underweight = good
            deviation = target - current
            deviations.append(deviation)

        # Calculate deviation for each industry
        for ind in inds:
            target = target_allocs.get('industry', {}).get(ind, 0)
            current = current_allocs.get('by_industry', {}).get(ind, 0)
            deviation = target - current
            deviations.append(deviation)

        # Average all deviations
        if not deviations:
            return 0.0

        avg_deviation = sum(deviations) / len(deviations)

        # Clamp to [-1, +1]
        return max(-1.0, min(1.0, avg_deviation))

    async def calculate_ideal_portfolio(self) -> dict[str, float]:
        """
        Calculate ideal portfolio allocations.

        Method determined by 'optimization_method' setting:
        - 'classic': Current wavelet-based approach
        - 'entropy': Entropy-based optimization
        - 'skfolio_mv': Mean-variance (skfolio)
        - 'skfolio_hrp': Hierarchical Risk Parity
        - 'skfolio_rp': Risk Parity

        The user_multiplier is applied to each security's score:
        - 1.0 = neutral (default)
        - 2.0 = user is very bullish (doubles the score weight)
        - 0.5 = user is bearish (halves the score weight)
        - 0.0 = user wants to exit entirely

        Diversification adjustment:
        - Securities in underweight categories get a boost
        - Securities in overweight categories get a reduction
        - Max impact is configurable via diversification_impact_pct setting

        Returns:
            dict: symbol -> target allocation percentage (0-1)
        """
        # Check cache first (10 minute TTL)
        cached = await self._db.cache_get('planner:ideal_portfolio')
        if cached is not None:
            return json.loads(cached)

        # Get optimization method from settings
        optimization_method = await self._settings.get('optimization_method', 'classic')

        # Get all securities with scores and user multipliers
        securities = await self._db.get_all_securities(active_only=True)
        scores = {}

        # Get current allocations and targets for diversification
        current_allocs = await self._portfolio.get_allocations()
        target_allocs = await self._portfolio.get_target_allocations()
        div_impact = await self._settings.get('diversification_impact_pct', 10) / 100

        for sec in securities:
            symbol = sec['symbol']
            user_multiplier = sec.get('user_multiplier', 1.0) or 1.0

            # Skip securities where user wants to exit (multiplier = 0)
            if user_multiplier <= 0:
                continue

            cursor = await self._db.conn.execute(
                "SELECT score FROM scores WHERE symbol = ?", (symbol,)
            )
            row = await cursor.fetchone()
            base_score = row['score'] if row and row['score'] is not None else 0

            # Apply user multiplier as conviction adjustment
            from sentinel.utils.scoring import adjust_score_for_conviction
            adjusted_score = adjust_score_for_conviction(base_score, user_multiplier)

            # Apply diversification multiplier
            if div_impact > 0:
                div_score = self._calculate_diversification_score(
                    sec, current_allocs, target_allocs
                )
                div_multiplier = 1.0 + (div_score * div_impact)
                adjusted_score = adjusted_score * div_multiplier

            # Include if score is positive OR if user has expressed positive conviction
            if adjusted_score > 0 or user_multiplier > 1.0:
                scores[symbol] = adjusted_score

        if not scores:
            return {}

        # Get constraints from settings
        max_position = await self._settings.get('max_position_pct', 20)
        min_position = await self._settings.get('min_position_pct', 2)
        cash_target = await self._settings.get('target_cash_pct', 5)

        constraints = {
            'max_position': max_position,
            'min_position': min_position,
            'cash_target': cash_target,
        }

        # Choose optimization method
        if optimization_method == 'entropy':
            from sentinel.entropy_optimizer import EntropyOptimizer
            optimizer = EntropyOptimizer()
            allocations = await optimizer.optimize(scores, constraints)

        elif optimization_method.startswith('skfolio_'):
            from sentinel.portfolio_optimizer import PortfolioOptimizer
            optimizer = PortfolioOptimizer()

            method_map = {
                'skfolio_mv': 'mean_variance',
                'skfolio_hrp': 'hierarchical',
                'skfolio_rp': 'risk_parity',
            }
            skfolio_method = method_map.get(optimization_method, 'mean_variance')

            symbols = list(scores.keys())
            allocations = await optimizer.optimize_with_skfolio(
                symbols,
                method=skfolio_method,
                expected_returns=scores,
                constraints=constraints
            )

        else:  # 'classic'
            allocations = await self._classic_allocation(scores, constraints)

        return allocations

    async def _classic_allocation(self, scores: dict, constraints: dict) -> dict:
        """Classic wavelet-based allocation (existing logic)."""
        max_position = constraints.get('max_position', 20) / 100
        min_position = constraints.get('min_position', 2) / 100
        cash_target = constraints.get('cash_target', 5) / 100

        # Filter to positive expected returns only
        positive_scores = {k: v for k, v in scores.items() if v > 0}

        if not positive_scores:
            return {}

        # Calculate allocations proportional to expected returns
        min_score = min(positive_scores.values())
        max_score = max(positive_scores.values())
        score_range = max_score - min_score if max_score != min_score else 1.0

        # Normalize scores to 0-1 range, then square to emphasize differences
        normalized = {}
        for symbol, score in positive_scores.items():
            norm = (score - min_score) / score_range if score_range > 0 else 0.5
            normalized[symbol] = (norm + 0.1) ** 2

        # Allocate proportionally
        total_weight = sum(normalized.values())
        if total_weight <= 0:
            return {}
        allocable = 1.0 - cash_target

        allocations = {}
        for symbol, weight in normalized.items():
            raw_alloc = (weight / total_weight) * allocable
            capped = max(min_position, min(max_position, raw_alloc))
            allocations[symbol] = capped

        # Renormalize to sum to allocable amount
        alloc_sum = sum(allocations.values())
        if alloc_sum > 0:
            scale = allocable / alloc_sum
            allocations = {k: v * scale for k, v in allocations.items()}

        # Cache result (10 minutes = 600 seconds)
        await self._db.cache_set('planner:ideal_portfolio', json.dumps(allocations), ttl_seconds=600)
        return allocations

    async def get_current_allocations(self) -> dict[str, float]:
        """Get current portfolio allocations by symbol (cached for 10 minutes)."""
        # Check cache first
        cached = await self._db.cache_get('planner:current_allocations')
        if cached is not None:
            return json.loads(cached)

        positions = await self._portfolio.positions()
        total = await self._portfolio.total_value()

        if total == 0:
            return {}

        allocations = {}
        for pos in positions:
            price = pos.get('current_price', 0)
            qty = pos.get('quantity', 0)
            currency = pos.get('currency', 'EUR')
            value_local = price * qty
            value_eur = await self._currency.to_eur(value_local, currency)
            allocations[pos['symbol']] = value_eur / total

        # Cache result (10 minutes = 600 seconds)
        await self._db.cache_set('planner:current_allocations', json.dumps(allocations), ttl_seconds=600)
        return allocations

    async def get_recommendations(
        self,
        min_trade_value: Optional[float] = None,
    ) -> list[TradeRecommendation]:
        """
        Generate trade recommendations to move toward ideal portfolio (cached for 5 minutes).

        Args:
            min_trade_value: Minimum trade value in EUR to recommend (if None, uses setting)

        Returns:
            List of TradeRecommendation, sorted by priority
        """
        # Get min_trade_value from settings if not provided
        if min_trade_value is None:
            settings = Settings()
            min_trade_value = await settings.get('min_trade_value', default=100.0)

        # Check cache first
        cache_key = f'planner:recommendations:{min_trade_value}'
        cached = await self._db.cache_get(cache_key)
        if cached is not None:
            # Deserialize back to TradeRecommendation objects
            return [TradeRecommendation(**r) for r in json.loads(cached)]

        ideal = await self.calculate_ideal_portfolio()
        current = await self.get_current_allocations()
        total_value = await self._portfolio.total_value()

        if total_value == 0:
            return []

        # Get all expected returns and security data
        expected_returns = {}
        security_data = {}

        # Include all ML-enabled securities so predictions run for them too
        ml_enabled_cursor = await self._db.conn.execute(
            "SELECT symbol FROM securities WHERE ml_enabled = 1 AND active = 1"
        )
        ml_enabled_rows = await ml_enabled_cursor.fetchall()
        ml_enabled_symbols = [row['symbol'] for row in ml_enabled_rows]

        all_symbols = list(set(list(ideal.keys()) + list(current.keys()) + ml_enabled_symbols))

        # Fetch all data in parallel for performance
        current_quotes = await self._broker.get_quotes(all_symbols)

        # Parallel fetch: securities, positions, scores, and historical prices
        securities_tasks = [self._db.get_security(s) for s in all_symbols]
        positions_tasks = [self._db.get_position(s) for s in all_symbols]

        securities_list, positions_list = await asyncio.gather(
            asyncio.gather(*securities_tasks),
            asyncio.gather(*positions_tasks),
        )

        # Create lookup maps
        securities_map = {all_symbols[i]: securities_list[i] for i in range(len(all_symbols))}
        positions_map = {all_symbols[i]: positions_list[i] for i in range(len(all_symbols))}

        # Fetch scores with components in parallel
        async def get_score_with_components(symbol):
            cursor = await self._db.conn.execute(
                "SELECT score, components FROM scores WHERE symbol = ?", (symbol,)
            )
            return await cursor.fetchone()

        scores_list = await asyncio.gather(*[get_score_with_components(s) for s in all_symbols])
        scores_map = {all_symbols[i]: scores_list[i] for i in range(len(all_symbols))}

        # Fetch full OHLCV historical prices (250 days for ML feature extraction)
        # Use PriceValidator to handle abnormal spikes/crashes in API data
        price_validator = PriceValidator()

        async def get_historical_ohlcv(symbol):
            cursor = await self._db.conn.execute(
                """SELECT date, open, high, low, close, volume
                   FROM prices WHERE symbol = ?
                   ORDER BY date DESC LIMIT 250""",
                (symbol,)
            )
            rows = await cursor.fetchall()
            if not rows:
                return []

            # Convert to list of dicts for validation
            price_list = [dict(row) for row in rows]

            # Ensure numeric types
            for price in price_list:
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    if col in price and price[col] is not None:
                        try:
                            price[col] = float(price[col])
                        except (ValueError, TypeError):
                            price[col] = 0.0

            # PriceValidator expects chronological order (oldest first)
            # Reverse, validate, then reverse back to DESC order
            price_list.reverse()
            validated_prices = price_validator.validate_and_interpolate(price_list)
            validated_prices.reverse()  # Back to DESC order
            return validated_prices

        hist_prices_list = await asyncio.gather(*[get_historical_ohlcv(s) for s in all_symbols])
        hist_prices_map = {all_symbols[i]: hist_prices_list[i] for i in range(len(all_symbols))}

        # Process each symbol using pre-fetched data
        from sentinel.utils.scoring import adjust_score_for_conviction
        from datetime import datetime

        for symbol in all_symbols:
            sec = securities_map.get(symbol)
            pos = positions_map.get(symbol)
            user_multiplier = sec.get('user_multiplier', 1.0) if sec else 1.0

            # Get wavelet score
            row = scores_map.get(symbol)
            wavelet_score = row['score'] if row and row['score'] is not None else 0

            # Prepare price data for feature extraction
            hist_rows = hist_prices_map.get(symbol, [])
            features = None

            if hist_rows and len(hist_rows) >= 200:
                price_df = pd.DataFrame(
                    [dict(r) for r in hist_rows],
                    columns=['date', 'open', 'high', 'low', 'close', 'volume']
                )
                # Reverse to chronological order
                price_df = price_df.iloc[::-1].reset_index(drop=True)

                # Extract features (ML predicts independently per security)
                features = await self._feature_extractor.extract_features(
                    symbol=symbol,
                    date=datetime.now().strftime('%Y-%m-%d'),
                    price_data=price_df,
                    sentiment_score=None,
                )

            # Apply ML blending if enabled for this security
            sec_ml_enabled = bool(sec.get('ml_enabled', 0)) if sec else False
            sec_ml_blend_ratio = float(sec.get('ml_blend_ratio', 0.5)) if sec else 0.5

            ml_result = await self._ml_predictor.predict_and_blend(
                symbol=symbol,
                date=datetime.now().strftime('%Y-%m-%d'),
                wavelet_score=wavelet_score,
                ml_enabled=sec_ml_enabled,
                ml_blend_ratio=sec_ml_blend_ratio,
                features=features,
            )

            # Use blended score (or wavelet if ML disabled)
            base_score = ml_result['final_score']

            # Apply user conviction adjustment
            expected_returns[symbol] = adjust_score_for_conviction(base_score, user_multiplier or 1.0)

            # Get price: prefer current quote from broker
            quote = current_quotes.get(symbol)
            price = quote.get('price', 0) if quote else 0

            # Fallback to position price if no quote
            if price <= 0 and pos:
                price = pos.get('current_price', 0)

            # Final fallback to latest historical price
            if price <= 0:
                hist_rows = hist_prices_map.get(symbol, [])
                if hist_rows:
                    price = hist_rows[0]['close'] if hist_rows[0]['close'] else 0

            # Check for price anomaly (blocks trades if current price is >10x 30-day avg)
            trade_blocked = False
            block_reason = ""
            if price > 0:
                hist_rows = hist_prices_map.get(symbol, [])
                historical_prices = [r['close'] for r in hist_rows if r['close'] and r['close'] > 0]

                if historical_prices:
                    allow_trade, reason = check_trade_blocking(price, historical_prices, symbol)
                    if not allow_trade:
                        trade_blocked = True
                        block_reason = reason

            security_data[symbol] = {
                'price': price,
                'currency': sec.get('currency', 'EUR') if sec else 'EUR',
                'lot_size': sec.get('min_lot', 1) if sec else 1,
                'current_qty': pos.get('quantity', 0) if pos else 0,
                'allow_buy': sec.get('allow_buy', 1) if sec else 1,
                'allow_sell': sec.get('allow_sell', 1) if sec else 1,
                'trade_blocked': trade_blocked,
                'block_reason': block_reason,
            }

        recommendations = []

        for symbol in all_symbols:
            current_alloc = current.get(symbol, 0)
            target_alloc = ideal.get(symbol, 0)
            delta = target_alloc - current_alloc

            # Calculate raw value delta in EUR
            raw_value_delta = delta * total_value

            # Get security data
            sec_data = security_data[symbol]
            price = sec_data['price']
            currency = sec_data['currency']
            lot_size = sec_data['lot_size']
            current_qty = sec_data['current_qty']
            allow_buy = sec_data.get('allow_buy', 1)
            allow_sell = sec_data.get('allow_sell', 1)

            # Skip if no price available
            if price <= 0:
                continue

            # Skip if trade blocked due to price anomaly
            if sec_data.get('trade_blocked'):
                continue

            # Check cool-off period
            cooloff_days = await self._settings.get('trade_cooloff_days', 30)
            is_blocked, block_reason = await self._check_cooloff_violation(
                symbol,
                'buy' if delta > 0 else 'sell',
                cooloff_days
            )
            if is_blocked:
                continue  # Skip this recommendation

            # Skip if action not allowed
            if delta > 0 and not allow_buy:
                continue
            if delta < 0 and not allow_sell:
                continue

            # Convert EUR value to local currency value
            if currency != 'EUR':
                # Get rate: 1 currency = X EUR, so local = eur / rate
                rate = await self._currency.get_rate(currency)
                if rate > 0:
                    local_value_delta = raw_value_delta / rate
                else:
                    local_value_delta = raw_value_delta
            else:
                local_value_delta = raw_value_delta

            # Calculate quantity (rounded to lot size)
            raw_qty = abs(local_value_delta) / price
            rounded_qty = (int(raw_qty) // lot_size) * lot_size

            # Skip if quantity rounds to zero
            if rounded_qty < lot_size:
                continue

            # For sells, don't exceed current position
            if delta < 0:
                rounded_qty = min(rounded_qty, current_qty)
                if rounded_qty < lot_size:
                    continue

            # Recalculate actual EUR value based on rounded quantity
            local_value = rounded_qty * price
            if currency != 'EUR':
                actual_value_eur = await self._currency.to_eur(local_value, currency)
            else:
                actual_value_eur = local_value

            # Skip if below minimum trade value
            if actual_value_eur < min_trade_value:
                continue

            expected_return = expected_returns.get(symbol, 0)

            # Determine action
            if delta > 0:
                action = 'buy'
                reason = self._generate_buy_reason(symbol, expected_return, current_alloc, target_alloc)
            else:
                action = 'sell'
                reason = self._generate_sell_reason(symbol, expected_return, current_alloc, target_alloc)

            # Calculate priority
            priority = self._calculate_priority(action, delta, expected_return)

            recommendations.append(TradeRecommendation(
                symbol=symbol,
                action=action,
                current_allocation=current_alloc,
                target_allocation=target_alloc,
                allocation_delta=delta,
                current_value_eur=current_alloc * total_value,
                target_value_eur=target_alloc * total_value,
                value_delta_eur=actual_value_eur if delta > 0 else -actual_value_eur,
                quantity=rounded_qty,
                price=price,
                currency=currency,
                lot_size=lot_size,
                expected_return=expected_return,
                priority=priority,
                reason=reason,
            ))

        # Sort: SELL first (to generate cash for buys), then by priority within each action type
        recommendations.sort(key=lambda x: (0 if x.action == 'sell' else 1, -x.priority))

        # Apply cash constraint: scale down buys to fit available budget
        recommendations = await self._apply_cash_constraint(recommendations, min_trade_value)

        # Cache result (5 minutes = 300 seconds)
        await self._db.cache_set(cache_key, json.dumps([asdict(r) for r in recommendations]), ttl_seconds=300)
        return recommendations

    def _calculate_priority(
        self,
        action: str,
        allocation_delta: float,
        expected_return: float,
    ) -> float:
        """
        Calculate priority score for a recommendation.

        High priority means we should act on this trade first.
        """
        # Base priority from allocation delta magnitude
        base = abs(allocation_delta) * 10

        if action == 'buy':
            # Buying high expected return = high priority
            return base + expected_return
        else:
            # Selling low expected return = high priority (inverted)
            return base - expected_return

    def _calculate_transaction_cost(self, value_eur: float, fixed_fee: float, pct_fee: float) -> float:
        """Calculate transaction cost for a given trade value."""
        from sentinel.utils.fees import FeeCalculator
        # Use the FeeCalculator's synchronous method with provided config
        return FeeCalculator().calculate_with_config(value_eur, fixed_fee, pct_fee)

    async def _apply_cash_constraint(
        self,
        recommendations: list[TradeRecommendation],
        min_trade_value: float,
    ) -> list[TradeRecommendation]:
        """
        Scale down buy recommendations to fit within available cash.

        Logic:
        1. Calculate available budget = current cash + net sell proceeds (after tx costs)
        2. If buys fit within budget (including tx costs), return as-is
        3. Otherwise:
           a. First pass: allocate 1 lot to each buy (highest priority first)
           b. Second pass: distribute remaining budget proportionally
        """
        # Get transaction cost settings
        fixed_fee = await self._settings.get('transaction_fee_fixed', 2.0)
        pct_fee = await self._settings.get('transaction_fee_percent', 0.2) / 100  # Convert from percentage to decimal

        # Separate sells and buys
        sells = [r for r in recommendations if r.action == 'sell']
        buys = [r for r in recommendations if r.action == 'buy']

        if not buys:
            return recommendations

        # Calculate available budget (net sell proceeds after transaction costs)
        current_cash = await self._portfolio.total_cash_eur()
        net_sell_proceeds = sum(
            abs(r.value_delta_eur) - self._calculate_transaction_cost(abs(r.value_delta_eur), fixed_fee, pct_fee)
            for r in sells
        )
        available_budget = current_cash + net_sell_proceeds

        # Calculate total buy costs (including transaction costs)
        total_buy_costs = sum(
            r.value_delta_eur + self._calculate_transaction_cost(r.value_delta_eur, fixed_fee, pct_fee)
            for r in buys
        )

        # If we can afford everything (including tx costs), return as-is
        if total_buy_costs <= available_budget:
            return recommendations

        # We need to scale down buys
        # Sort buys by priority (highest first) - they should already be sorted
        buys_by_priority = sorted(buys, key=lambda x: -x.priority)

        # First pass: allocate minimum 1 lot to each buy (highest priority first)
        remaining_budget = available_budget

        # Calculate minimum cost for each buy in EUR, including transaction costs
        # Minimum is either 1 lot OR enough lots to meet min_trade_value, whichever is larger
        buy_minimums = []
        for buy in buys_by_priority:
            # Calculate EUR value of 1 lot
            one_lot_local = buy.lot_size * buy.price
            if buy.currency != 'EUR':
                one_lot_eur = await self._currency.to_eur(one_lot_local, buy.currency)
            else:
                one_lot_eur = one_lot_local

            # Calculate minimum quantity to meet min_trade_value
            if one_lot_eur >= min_trade_value:
                min_qty = buy.lot_size
                min_eur = one_lot_eur
            elif one_lot_eur <= 0:
                # Skip if lot value is zero or negative
                continue
            else:
                # Need multiple lots to reach min_trade_value
                lots_needed = int(min_trade_value / one_lot_eur) + 1
                min_qty = lots_needed * buy.lot_size
                min_eur = lots_needed * one_lot_eur

            # Don't exceed ideal quantity
            if min_qty > buy.quantity:
                min_qty = buy.quantity
                min_local_value = min_qty * buy.price
                if buy.currency != 'EUR':
                    min_eur = await self._currency.to_eur(min_local_value, buy.currency)
                else:
                    min_eur = min_local_value

            # Add transaction cost to get true minimum cost
            min_cost_with_tx = min_eur + self._calculate_transaction_cost(min_eur, fixed_fee, pct_fee)
            # Ideal cost including transaction fees
            ideal_cost_with_tx = buy.value_delta_eur + self._calculate_transaction_cost(buy.value_delta_eur, fixed_fee, pct_fee)
            buy_minimums.append({
                'buy': buy,
                'min_qty': min_qty,
                'min_eur': min_eur,  # Trade value only
                'min_cost': min_cost_with_tx,  # Including tx cost
                'ideal_eur': buy.value_delta_eur,  # Trade value only
                'ideal_cost': ideal_cost_with_tx,  # Including tx cost
            })

        # Allocate minimums first (highest priority gets their minimum first)
        included_buys = []
        for item in buy_minimums:
            if item['min_cost'] <= remaining_budget:
                included_buys.append(item)
                remaining_budget -= item['min_cost']

        if not included_buys:
            # Can't afford even 1 lot of the highest priority buy
            return sells

        # Second pass: distribute remaining budget proportionally to ideal costs (beyond minimums)
        # Calculate total extra cost needed (ideal - minimum, including tx costs)
        total_extra_needed = sum(
            max(0, item['ideal_cost'] - item['min_cost'])
            for item in included_buys
        )

        # Build final buy list with scaled quantities
        final_buys = []
        for item in included_buys:
            buy = item['buy']
            min_eur = item['min_eur']
            min_cost = item['min_cost']
            ideal_cost = item['ideal_cost']

            # Start with minimum trade value
            allocated_eur = min_eur

            # Add proportional share of remaining budget
            if total_extra_needed > 0 and remaining_budget > 0:
                extra_needed = max(0, ideal_cost - min_cost)
                proportion = extra_needed / total_extra_needed
                # Extra allocation is budget share, but we need to subtract tx cost from it
                extra_budget = proportion * remaining_budget
                # The extra budget includes tx cost, so we need to extract just the trade value
                # extra_budget = extra_trade_value + tx_cost(extra_trade_value)
                # extra_budget = extra_trade_value * (1 + pct_fee) + fixed_fee
                # But since we're adding to an existing trade, the fixed fee is already paid
                # So: extra_budget = extra_trade_value * (1 + pct_fee)
                extra_trade_value = extra_budget / (1 + pct_fee)
                allocated_eur += extra_trade_value

            # Convert EUR allocation back to quantity
            if buy.currency != 'EUR':
                rate = await self._currency.get_rate(buy.currency)
                if rate > 0:
                    local_value = allocated_eur / rate
                else:
                    local_value = allocated_eur
            else:
                local_value = allocated_eur

            # Calculate quantity (rounded down to lot size)
            raw_qty = local_value / buy.price
            rounded_qty = (int(raw_qty) // buy.lot_size) * buy.lot_size

            if rounded_qty < buy.lot_size:
                continue  # Skip if rounds to zero

            # Recalculate actual EUR value
            actual_local = rounded_qty * buy.price
            if buy.currency != 'EUR':
                actual_eur = await self._currency.to_eur(actual_local, buy.currency)
            else:
                actual_eur = actual_local

            if actual_eur < min_trade_value:
                continue  # Skip if below minimum trade value

            # Create scaled recommendation
            final_buys.append(TradeRecommendation(
                symbol=buy.symbol,
                action='buy',
                current_allocation=buy.current_allocation,
                target_allocation=buy.target_allocation,
                allocation_delta=buy.allocation_delta,
                current_value_eur=buy.current_value_eur,
                target_value_eur=buy.target_value_eur,
                value_delta_eur=actual_eur,
                quantity=rounded_qty,
                price=buy.price,
                currency=buy.currency,
                lot_size=buy.lot_size,
                expected_return=buy.expected_return,
                priority=buy.priority,
                reason=buy.reason,
            ))

        # Sort final buys by priority
        final_buys.sort(key=lambda x: -x.priority)

        # Third pass: top-up with leftover budget
        # After rounding, we may have unused budget. Distribute extra lots to highest-priority buys.
        total_buy_cost = sum(
            b.value_delta_eur + self._calculate_transaction_cost(b.value_delta_eur, fixed_fee, pct_fee)
            for b in final_buys
        )
        leftover = available_budget - total_buy_cost

        # Try to add 1 more lot to each buy (highest priority first) while we have budget
        iterations = 0
        while leftover > 0 and iterations < 1000:  # Safety limit
            iterations += 1
            added_any = False
            for i, buy in enumerate(final_buys):
                # Calculate cost of 1 additional lot
                one_lot_local = buy.lot_size * buy.price
                if buy.currency != 'EUR':
                    one_lot_eur = await self._currency.to_eur(one_lot_local, buy.currency)
                else:
                    one_lot_eur = one_lot_local
                one_lot_cost = one_lot_eur + self._calculate_transaction_cost(one_lot_eur, fixed_fee, pct_fee)

                # Check if we can afford it (don't cap at ideal - use full budget)
                if one_lot_cost <= leftover:
                        # Add one lot
                        new_qty = buy.quantity + buy.lot_size
                        new_local_value = new_qty * buy.price
                        if buy.currency != 'EUR':
                            new_eur = await self._currency.to_eur(new_local_value, buy.currency)
                        else:
                            new_eur = new_local_value

                        # Replace buy with updated version
                        final_buys[i] = TradeRecommendation(
                            symbol=buy.symbol,
                            action='buy',
                            current_allocation=buy.current_allocation,
                            target_allocation=buy.target_allocation,
                            allocation_delta=buy.allocation_delta,
                            current_value_eur=buy.current_value_eur,
                            target_value_eur=buy.target_value_eur,
                            value_delta_eur=new_eur,
                            quantity=new_qty,
                            price=buy.price,
                            currency=buy.currency,
                            lot_size=buy.lot_size,
                            expected_return=buy.expected_return,
                            priority=buy.priority,
                            reason=buy.reason,
                        )
                        leftover -= one_lot_cost
                        added_any = True

            if not added_any:
                break  # No more lots can be added

        return sells + final_buys

    def _generate_buy_reason(
        self,
        symbol: str,
        expected_return: float,
        current_alloc: float,
        target_alloc: float,
    ) -> str:
        """Generate human-readable reason for buy recommendation."""
        underweight = (target_alloc - current_alloc) * 100

        if current_alloc == 0:
            return f"New position: {symbol} has expected return of {expected_return:.2f}"

        if expected_return > 0.3:
            return f"Underweight by {underweight:.1f}%. High expected return ({expected_return:.2f})"
        elif expected_return > 0:
            return f"Underweight by {underweight:.1f}%. Positive expected return ({expected_return:.2f})"
        else:
            return f"Underweight by {underweight:.1f}% despite neutral outlook"

    def _generate_sell_reason(
        self,
        symbol: str,
        expected_return: float,
        current_alloc: float,
        target_alloc: float,
    ) -> str:
        """Generate human-readable reason for sell recommendation."""
        overweight = (current_alloc - target_alloc) * 100

        if target_alloc == 0:
            if expected_return < 0:
                return f"Exit position: {symbol} has negative expected return ({expected_return:.2f})"
            else:
                return f"Exit position: {symbol} not in ideal portfolio"

        if expected_return < 0:
            return f"Overweight by {overweight:.1f}%. Negative expected return ({expected_return:.2f})"
        else:
            return f"Overweight by {overweight:.1f}%. Reduce to target allocation"

    async def _check_cooloff_violation(
        self,
        symbol: str,
        action: str,
        cooloff_days: int
    ) -> tuple[bool, str]:
        """
        Check if a trade would violate the cool-off period.

        Returns:
            (is_blocked, reason) tuple
            - is_blocked: True if trade should be blocked
            - reason: Human-readable explanation if blocked, empty string otherwise
        """
        from datetime import datetime

        # Get last trade for this symbol
        trades = await self._db.get_trades(symbol=symbol, limit=1)

        if not trades:
            return False, ""  # No trade history, allow trade

        last_trade = trades[0]
        last_action = last_trade['side']  # 'BUY' or 'SELL'
        last_date = datetime.fromisoformat(last_trade['executed_at'])
        current_date = datetime.now()
        days_since = (current_date - last_date).days

        # Check if action is opposite of last trade
        if action == 'buy' and last_action == 'SELL':
            if days_since < cooloff_days:
                days_remaining = cooloff_days - days_since
                return True, f"Cool-off period: {days_remaining} days remaining after last sell"
        elif action == 'sell' and last_action == 'BUY':
            if days_since < cooloff_days:
                days_remaining = cooloff_days - days_since
                return True, f"Cool-off period: {days_remaining} days remaining after last buy"

        # Same direction as last trade, or enough time has passed
        return False, ""

    async def get_rebalance_summary(self) -> dict:
        """
        Get a summary of the portfolio's alignment with ideal allocations.

        Returns dict with:
        - total_deviation: Sum of absolute allocation differences
        - needs_rebalance: True if deviation exceeds threshold
        - overweight: List of overweight positions
        - underweight: List of underweight positions
        - ideal_allocations: The calculated ideal portfolio
        """
        ideal = await self.calculate_ideal_portfolio()
        current = await self.get_current_allocations()
        threshold = await self._settings.get('rebalance_threshold_pct', 5) / 100

        total_deviation = 0
        overweight = []
        underweight = []

        all_symbols = set(list(ideal.keys()) + list(current.keys()))

        for symbol in all_symbols:
            current_alloc = current.get(symbol, 0)
            target_alloc = ideal.get(symbol, 0)
            delta = current_alloc - target_alloc

            total_deviation += abs(delta)

            if delta > 0.02:  # 2% overweight threshold
                overweight.append({
                    'symbol': symbol,
                    'current_pct': current_alloc * 100,
                    'target_pct': target_alloc * 100,
                    'delta_pct': delta * 100,
                })
            elif delta < -0.02:  # 2% underweight threshold
                underweight.append({
                    'symbol': symbol,
                    'current_pct': current_alloc * 100,
                    'target_pct': target_alloc * 100,
                    'delta_pct': delta * 100,
                })

        # Sort by absolute delta
        overweight.sort(key=lambda x: abs(x['delta_pct']), reverse=True)
        underweight.sort(key=lambda x: abs(x['delta_pct']), reverse=True)

        return {
            'total_deviation': total_deviation,
            'needs_rebalance': total_deviation > threshold,
            'overweight': overweight,
            'underweight': underweight,
            'ideal_allocations': {k: v * 100 for k, v in ideal.items()},
        }

