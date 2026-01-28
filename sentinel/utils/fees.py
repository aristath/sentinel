"""
Fee Calculator - Single source of truth for transaction fee calculations.

Usage:
    calculator = FeeCalculator(settings)
    fee = await calculator.calculate(1000.0)
    breakdown = await calculator.calculate_batch(trades)
"""


class FeeCalculator:
    """Calculates transaction fees for trades."""

    def __init__(self, settings=None):
        """
        Initialize the calculator.

        Args:
            settings: Settings instance for retrieving fee configuration.
                     If None, uses sentinel.settings.Settings.
        """
        self._settings = settings
        self._settings_instance = None

    async def _get_settings(self):
        """Lazy-load the settings provider."""
        if self._settings is not None:
            return self._settings

        if self._settings_instance is None:
            from sentinel.settings import Settings

            self._settings_instance = Settings()

        return self._settings_instance

    async def get_fee_config(self) -> tuple[float, float]:
        """
        Get current fee configuration.

        Returns:
            Tuple of (fixed_fee, percentage_fee_decimal)
        """
        settings = await self._get_settings()
        fixed_fee = await settings.get("transaction_fee_fixed", 2.0)
        pct_fee = await settings.get("transaction_fee_percent", 0.2) / 100
        return fixed_fee, pct_fee

    async def calculate(self, trade_value_eur: float) -> float:
        """
        Calculate transaction cost for a given trade value.

        Args:
            trade_value_eur: Trade value in EUR

        Returns:
            Total transaction cost in EUR
        """
        fixed_fee, pct_fee = await self.get_fee_config()
        return fixed_fee + (trade_value_eur * pct_fee)

    def calculate_with_config(self, trade_value_eur: float, fixed_fee: float, pct_fee: float) -> float:
        """
        Calculate transaction cost using provided fee configuration.

        This is a synchronous method for use in loops where settings
        have already been fetched.

        Args:
            trade_value_eur: Trade value in EUR
            fixed_fee: Fixed fee per transaction
            pct_fee: Percentage fee as decimal (e.g., 0.002 for 0.2%)

        Returns:
            Total transaction cost in EUR
        """
        return fixed_fee + (trade_value_eur * pct_fee)

    async def calculate_batch(self, trades: list[dict]) -> dict:
        """
        Calculate fees for a batch of trades.

        Args:
            trades: List of trade dicts with 'action' and 'value_eur' keys

        Returns:
            Dict with fee breakdown:
            {
                'total_fees': float,
                'buy_fees': float,
                'sell_fees': float,
                'num_buys': int,
                'num_sells': int,
                'total_buy_value': float,
                'total_sell_value': float,
            }
        """
        fixed_fee, pct_fee = await self.get_fee_config()

        num_buys = 0
        num_sells = 0
        total_buy_value = 0.0
        total_sell_value = 0.0

        for trade in trades:
            action = trade.get("action", "")
            value = abs(trade.get("value_eur", 0))

            if action == "buy":
                num_buys += 1
                total_buy_value += value
            elif action == "sell":
                num_sells += 1
                total_sell_value += value

        buy_fees = num_buys * fixed_fee + total_buy_value * pct_fee
        sell_fees = num_sells * fixed_fee + total_sell_value * pct_fee

        return {
            "total_fees": buy_fees + sell_fees,
            "buy_fees": buy_fees,
            "sell_fees": sell_fees,
            "num_buys": num_buys,
            "num_sells": num_sells,
            "total_buy_value": total_buy_value,
            "total_sell_value": total_sell_value,
        }
