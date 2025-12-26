"""Stock factory for creating Stock domain objects."""

from typing import Optional

from app.domain.exceptions import ValidationError
from app.domain.models import Stock
from app.domain.value_objects.currency import Currency


class StockFactory:
    """Factory for creating Stock domain objects."""

    # Geography to currency mapping (with fallback to EUR for unknown)
    GEOGRAPHY_CURRENCY_MAP = {
        "EU": Currency.EUR,
        "US": Currency.USD,
        "ASIA": Currency.HKD,
        "GREECE": Currency.EUR,  # Greek stocks trade in EUR
    }

    @classmethod
    def create_from_api_request(cls, data: dict) -> Stock:
        """Create Stock from API request data.

        Args:
            data: Dictionary with stock data from API request
                - symbol: str (required)
                - name: str (required)
                - geography: str (required, must be EU/US/ASIA)
                - industry: str (optional)
                - min_lot: int (optional, defaults to 1)
                - allow_buy: bool (optional, defaults to True)
                - allow_sell: bool (optional, defaults to False)
                - yahoo_symbol: str (optional)

        Returns:
            Stock domain object

        Raises:
            ValidationError: If validation fails
        """
        symbol = data.get("symbol", "").strip().upper()
        if not symbol:
            raise ValidationError("Symbol cannot be empty")

        name = data.get("name", "").strip()
        if not name:
            raise ValidationError("Name cannot be empty")

        geography = data.get("geography", "").strip().upper()
        if not geography:
            raise ValidationError("Geography cannot be empty")

        # Set currency based on geography (fallback to EUR for unknown)
        currency = cls.GEOGRAPHY_CURRENCY_MAP.get(geography, Currency.EUR)

        # Validate and set min_lot
        min_lot = data.get("min_lot", 1)
        if min_lot < 1:
            min_lot = 1

        return Stock(
            symbol=symbol,
            name=name,
            geography=geography,
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
    ) -> Stock:
        """Create Stock with industry detection.

        Args:
            data: Dictionary with stock data
            industry: Detected industry (optional, will use data['industry'] if not provided)

        Returns:
            Stock domain object
        """
        stock_data = data.copy()
        if industry:
            stock_data["industry"] = industry
        return cls.create_from_api_request(stock_data)

    @classmethod
    def create_from_import(cls, data: dict) -> Stock:
        """Create Stock from import data (bulk imports).

        Args:
            data: Dictionary with stock data from import
                - symbol: str (required)
                - name: str (required)
                - geography: str (required)
                - industry: str (optional)
                - yahoo_symbol: str (optional)
                - currency: str or Currency (optional, will be inferred from geography if not provided)
                - min_lot: int (optional, defaults to 1)

        Returns:
            Stock domain object
        """
        # Normalize symbol and geography
        symbol = data.get("symbol", "").strip().upper()
        geography = data.get("geography", "").strip().upper()

        # Handle currency - can be string or Currency enum
        currency = data.get("currency")
        if currency is None:
            currency = cls.GEOGRAPHY_CURRENCY_MAP.get(geography, Currency.EUR)
        elif isinstance(currency, str):
            currency = Currency.from_string(currency)

        return Stock(
            symbol=symbol,
            name=data.get("name", "").strip(),
            geography=geography,
            yahoo_symbol=data.get("yahoo_symbol"),
            industry=data.get("industry"),
            priority_multiplier=data.get("priority_multiplier", 1.0),
            min_lot=max(1, data.get("min_lot", 1)),
            active=data.get("active", True),
            allow_buy=data.get("allow_buy", True),
            allow_sell=data.get("allow_sell", False),
            currency=currency,
        )
