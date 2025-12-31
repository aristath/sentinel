"""Recommendation factory for creating recommendation data structures."""

from typing import Optional

from app.shared.domain.value_objects.currency import Currency
from app.domain.value_objects.trade_side import TradeSide


class RecommendationFactory:
    """Factory for creating recommendation data structures."""

    @classmethod
    def create_buy_recommendation(
        cls,
        symbol: str,
        name: str,
        quantity: int,
        estimated_price: float,
        estimated_value: float,
        reason: str,
        country: Optional[str] = None,
        industry: Optional[str] = None,
        currency: Optional[Currency] = None,
        priority: Optional[float] = None,
        current_portfolio_score: Optional[float] = None,
        new_portfolio_score: Optional[float] = None,
        amount: Optional[float] = None,
    ) -> dict:
        """Create buy recommendation data.

        Args:
            symbol: Stock symbol
            name: Stock name
            quantity: Number of shares to buy
            estimated_price: Estimated price per share
            estimated_value: Total trade value in EUR
            reason: Reason for recommendation
            country: Stock country (e.g., "United States", "Germany")
            industry: Stock industry (optional)
            currency: Stock currency (optional, defaults to EUR)
            priority: Priority score (optional)
            current_portfolio_score: Portfolio score before trade (optional)
            new_portfolio_score: Portfolio score after trade (optional)
            amount: Display amount (optional, defaults to estimated_value)

        Returns:
            Dictionary with recommendation data ready for repository
        """
        if currency is None:
            currency = Currency.EUR

        # Calculate score change if both scores provided
        score_change = None
        if current_portfolio_score is not None and new_portfolio_score is not None:
            score_change = new_portfolio_score - current_portfolio_score

        return {
            "symbol": symbol.upper(),
            "name": name,
            "side": TradeSide.BUY,
            "quantity": quantity,
            "estimated_price": estimated_price,
            "estimated_value": estimated_value,
            "amount": amount or estimated_value,  # For display
            "reason": reason,
            "country": country,
            "industry": industry,
            "currency": currency,
            "priority": priority,
            "current_portfolio_score": current_portfolio_score,
            "new_portfolio_score": new_portfolio_score,
            "score_change": score_change,
        }

    @classmethod
    def create_sell_recommendation(
        cls,
        symbol: str,
        name: str,
        quantity: int,
        estimated_price: float,
        estimated_value: float,
        reason: str,
        country: Optional[str] = None,
        industry: Optional[str] = None,
        currency: Optional[Currency] = None,
    ) -> dict:
        """Create sell recommendation data.

        Args:
            symbol: Stock symbol
            name: Stock name
            quantity: Number of shares to sell
            estimated_price: Estimated price per share
            estimated_value: Total trade value in EUR
            reason: Reason for recommendation
            country: Stock country (e.g., "United States", "Germany")
            industry: Stock industry (optional)
            currency: Stock currency (optional, defaults to EUR)

        Returns:
            Dictionary with recommendation data ready for repository
        """
        if currency is None:
            currency = Currency.EUR

        return {
            "symbol": symbol.upper(),
            "name": name,
            "side": TradeSide.SELL,
            "quantity": quantity,
            "estimated_price": estimated_price,
            "estimated_value": estimated_value,
            "amount": estimated_value,  # For display
            "reason": reason,
            "country": country,
            "industry": industry,
            "currency": currency,
        }
