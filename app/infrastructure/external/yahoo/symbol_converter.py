"""Yahoo Finance symbol conversion utilities.

Converts between Tradernet symbol format and Yahoo Finance format.
"""


def get_yahoo_symbol(tradernet_symbol: str, yahoo_override: str = None) -> str:
    """
    Convert Tradernet symbol format to Yahoo Finance format.

    Uses explicit override if provided, otherwise applies conventions:
    - US stocks (.US): Strip suffix (AAPL.US -> AAPL)
    - Greek stocks (.GR): Convert to Athens (.GR -> .AT)
    - Other suffixes: Keep as-is

    Args:
        tradernet_symbol: Symbol in Tradernet format
        yahoo_override: Explicit Yahoo symbol (used for Asian stocks with different formats)

    Returns:
        Yahoo Finance compatible symbol
    """
    if yahoo_override:
        return yahoo_override

    symbol = tradernet_symbol.upper()

    # US stocks: strip .US suffix
    if symbol.endswith(".US"):
        return symbol[:-3]

    # Greek stocks: .GR -> .AT (Athens Exchange)
    if symbol.endswith(".GR"):
        return symbol[:-3] + ".AT"

    return symbol
