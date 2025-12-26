"""Domain-specific exceptions."""


class DomainError(Exception):
    """Base exception for domain errors."""

    pass


class StockNotFoundError(DomainError):
    """Raised when a stock is not found."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        super().__init__(f"Stock not found: {symbol}")


class InsufficientFundsError(DomainError):
    """Raised when there are insufficient funds for a trade."""

    def __init__(self, required: float, available: float):
        self.required = required
        self.available = available
        super().__init__(
            f"Insufficient funds: required {required:.2f}, available {available:.2f}"
        )


class InvalidTradeError(DomainError):
    """Raised when a trade is invalid."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Invalid trade: {message}")


class CurrencyConversionError(DomainError):
    """Raised when currency conversion fails."""

    def __init__(self, from_currency: str, to_currency: str, reason: str = ""):
        self.from_currency = from_currency
        self.to_currency = to_currency
        self.reason = reason
        message = f"Cannot convert {from_currency} to {to_currency}"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class ValidationError(DomainError):
    """Raised when domain validation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Validation error: {message}")
