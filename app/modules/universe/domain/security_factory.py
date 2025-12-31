"""Security factory for creating Security domain objects."""

from typing import Optional

from app.domain.exceptions import ValidationError
from app.domain.models import Security
from app.shared.domain.value_objects.currency import Currency


class SecurityFactory:
    """Factory for creating Security domain objects."""

    @classmethod
    def create_from_api_request(cls, data: dict) -> Security:
        """Create Security from API request data.

        Args:
            data: Dictionary with security data from API request
                - symbol: str (required)
                - name: str (required)
                - country: str (optional, auto-detected from Yahoo Finance)
                - fullExchangeName: str (optional, auto-detected from Yahoo Finance)
                - industry: str (optional)
                - min_lot: int (optional, defaults to 1)
                - allow_buy: bool (optional, defaults to True)
                - allow_sell: bool (optional, defaults to False)
                - yahoo_symbol: str (optional)
                - currency: Currency (optional, synced from Tradernet)

        Returns:
            Security domain object

        Raises:
            ValidationError: If validation fails
        """
        symbol = data.get("symbol", "").strip().upper()
        if not symbol:
            raise ValidationError("Symbol cannot be empty")

        name = data.get("name", "").strip()
        if not name:
            raise ValidationError("Name cannot be empty")

        # Validate and set min_lot
        min_lot = data.get("min_lot", 1)
        if min_lot < 1:
            min_lot = 1

        # Currency is synced from Tradernet, not inferred from geography
        currency = data.get("currency")
        if currency and isinstance(currency, str):
            currency = Currency.from_string(currency)

        return Security(
            symbol=symbol,
            name=name,
            country=data.get("country"),
            fullExchangeName=data.get("fullExchangeName"),
            yahoo_symbol=data.get("yahoo_symbol"),
            industry=data.get("industry"),
            priority_multiplier=1.0,
            min_lot=min_lot,
            active=True,
            allow_buy=data.get("allow_buy", True),
            allow_sell=data.get("allow_sell", False),
            currency=currency,
        )

    @classmethod
    def create_with_industry_detection(
        cls, data: dict, industry: Optional[str] = None
    ) -> Security:
        """Create Security with industry detection.

        Args:
            data: Dictionary with security data
            industry: Detected industry (optional, will use data['industry'] if not provided)

        Returns:
            Security domain object
        """
        security_data = data.copy()
        if industry:
            security_data["industry"] = industry
        return cls.create_from_api_request(security_data)

    @classmethod
    def create_from_import(cls, data: dict) -> Security:
        """Create Security from import data (bulk imports).

        Args:
            data: Dictionary with security data from import
                - symbol: str (required)
                - name: str (required)
                - country: str (optional, auto-detected from Yahoo Finance)
                - fullExchangeName: str (optional, auto-detected from Yahoo Finance)
                - industry: str (optional)
                - yahoo_symbol: str (optional)
                - currency: str or Currency (optional, synced from Tradernet)
                - min_lot: int (optional, defaults to 1)

        Returns:
            Security domain object
        """
        # Normalize symbol
        symbol = data.get("symbol", "").strip().upper()

        # Handle currency - can be string or Currency enum
        currency = data.get("currency")
        if currency is None:
            currency = None  # Will be synced from Tradernet
        elif isinstance(currency, str):
            currency = Currency.from_string(currency)

        return Security(
            symbol=symbol,
            name=data.get("name", "").strip(),
            country=data.get("country"),
            fullExchangeName=data.get("fullExchangeName"),
            yahoo_symbol=data.get("yahoo_symbol"),
            industry=data.get("industry"),
            priority_multiplier=data.get("priority_multiplier", 1.0),
            min_lot=max(1, data.get("min_lot", 1)),
            active=data.get("active", True),
            allow_buy=data.get("allow_buy", True),
            allow_sell=data.get("allow_sell", False),
            currency=currency,
        )


# Backward compatibility alias
StockFactory = SecurityFactory
