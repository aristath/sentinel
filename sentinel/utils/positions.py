"""
Position Calculator - Single source of truth for position value calculations.

Usage:
    calculator = PositionCalculator()
    value_eur = await calculator.calculate_value_eur(100, 150.0, 'USD')
    allocation = calculator.calculate_allocation(15000.0, 100000.0)
    totals = await calculator.calculate_portfolio_values(positions)
"""


class PositionCalculator:
    """Calculates position values and allocations."""

    def __init__(self, currency_converter=None):
        """
        Initialize the calculator.

        Args:
            currency_converter: Object with async to_eur(amount, currency) method.
                               If None, creates a Currency instance.
        """
        self._converter = currency_converter
        self._currency_instance = None

    async def _get_converter(self):
        """Lazy-load the currency converter."""
        if self._converter is not None:
            return self._converter
        if self._currency_instance is None:
            from sentinel.currency import Currency

            self._currency_instance = Currency()
        return self._currency_instance

    async def calculate_value_local(self, quantity: float, price: float) -> float:
        """
        Calculate position value in local currency.

        Args:
            quantity: Number of shares/units
            price: Price per share in local currency

        Returns:
            Total value in local currency
        """
        return quantity * price

    async def calculate_value_eur(self, quantity: float, price: float, currency: str) -> float:
        """
        Calculate position value in EUR.

        Args:
            quantity: Number of shares/units
            price: Price per share in local currency
            currency: Currency code of the price

        Returns:
            Total value in EUR
        """
        local_value = quantity * price
        converter = await self._get_converter()
        return await converter.to_eur(local_value, currency)

    def calculate_allocation(self, value_eur: float, total_eur: float) -> float:
        """
        Calculate allocation percentage.

        Args:
            value_eur: Position value in EUR
            total_eur: Total portfolio value in EUR

        Returns:
            Allocation as a decimal (e.g., 0.15 for 15%)
        """
        if total_eur <= 0:
            return 0.0
        return value_eur / total_eur

    async def calculate_portfolio_values(self, positions: list[dict]) -> dict:
        """
        Calculate total portfolio values from a list of positions.

        Args:
            positions: List of position dicts with keys:
                      - quantity: Number of shares
                      - current_price: Current price per share
                      - currency: Currency code

        Returns:
            Dict with:
            - total_value_eur: Total portfolio value in EUR
            - positions_with_values: List of positions with value_eur added
            - allocations: Dict of symbol -> allocation decimal
        """
        total_value_eur = 0.0
        positions_with_values = []

        # First pass: calculate values
        for pos in positions:
            qty = pos.get("quantity", 0)
            price = pos.get("current_price", 0)
            currency = pos.get("currency", "EUR")

            value_eur = await self.calculate_value_eur(qty, price, currency)

            pos_with_value = {**pos, "value_eur": value_eur}
            positions_with_values.append(pos_with_value)
            total_value_eur += value_eur

        # Second pass: calculate allocations
        allocations = {}
        for pos in positions_with_values:
            symbol = pos.get("symbol", "")
            if symbol:
                allocations[symbol] = self.calculate_allocation(pos["value_eur"], total_value_eur)

        return {
            "total_value_eur": total_value_eur,
            "positions_with_values": positions_with_values,
            "allocations": allocations,
        }

    def calculate_profit(self, quantity: float, current_price: float, avg_cost: float) -> tuple[float, float]:
        """
        Calculate profit/loss for a position.

        Args:
            quantity: Number of shares/units
            current_price: Current price per share
            avg_cost: Average cost per share

        Returns:
            Tuple of (profit_pct, profit_value)
            - profit_pct: Percentage profit/loss
            - profit_value: Absolute profit/loss in local currency
        """
        if avg_cost <= 0:
            return 0.0, 0.0

        profit_pct = ((current_price - avg_cost) / avg_cost) * 100
        profit_value = (current_price - avg_cost) * quantity

        return profit_pct, profit_value
