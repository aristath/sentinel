"""
Currency Configuration - Single source of truth for supported currencies.

This consolidates currency definitions from currency.py and currency_exchange.py.
"""

# All currencies supported by the system
SUPPORTED_CURRENCIES = [
    "EUR",  # Base currency
    "USD",
    "GBP",
    "HKD",
    "CHF",
    "JPY",
    "CNY",
    "CAD",
    "AUD",
    "SGD",
    "NOK",
    "SEK",
    "DKK",
    "PLN",
    "CZK",
]

# Currencies for rate fetching (excluding EUR which is the base)
RATE_FETCH_CURRENCIES = [c for c in SUPPORTED_CURRENCIES if c != "EUR"]

# Direct currency pairs available on Tradernet for FX operations (MONEY market)
# Format: (from_currency, to_currency) -> (symbol, action)
#
# BUY/SELL semantics follow standard forex convention:
#   For instrument BASE/QUOTE: BUY = buy base (give quote), SELL = sell base (give quote)
#   Verified against actively-traded HKD/EUR and HKD/USD pairs.
#
# NOTE: The old ITS_MONEY symbols (EURUSD_T0.ITS etc.) had zero volume and
# inverted BUY/SELL. Replaced with actively-traded MONEY market symbols.
DIRECT_PAIRS = {
    # EUR <-> USD (base=EUR, quote=USD)
    ("EUR", "USD"): ("EUR/USD", "SELL"),  # sell EUR → get USD
    ("USD", "EUR"): ("EUR/USD", "BUY"),  # buy EUR → give USD
    # EUR <-> GBP (base=EUR, quote=GBP)
    ("EUR", "GBP"): ("EUR/GBP", "SELL"),  # sell EUR → get GBP
    ("GBP", "EUR"): ("EUR/GBP", "BUY"),  # buy EUR → give GBP
    # GBP <-> USD (base=GBP, quote=USD)
    ("GBP", "USD"): ("GBP/USD", "SELL"),  # sell GBP → get USD
    ("USD", "GBP"): ("GBP/USD", "BUY"),  # buy GBP → give USD
    # HKD <-> EUR (base=HKD, quote=EUR)
    ("EUR", "HKD"): ("HKD/EUR", "BUY"),  # buy HKD → give EUR
    ("HKD", "EUR"): ("HKD/EUR", "SELL"),  # sell HKD → get EUR
    # HKD <-> USD (base=HKD, quote=USD)
    ("USD", "HKD"): ("HKD/USD", "BUY"),  # buy HKD → give USD
    ("HKD", "USD"): ("HKD/USD", "SELL"),  # sell HKD → get USD
}

# Default exchange rates (fallbacks when API fails)
DEFAULT_RATES = {
    "EUR": 1.0,
    "USD": 0.85,
    "GBP": 1.15,
    "HKD": 0.11,
    "CHF": 1.08,
    "JPY": 0.0054,
}

# Geography to currency mapping
GEOGRAPHY_CURRENCIES = {
    "EU": "EUR",
    "EUROPE": "EUR",
    "GREECE": "EUR",
    "US": "USD",
    "USA": "USD",
    "ASIA": "HKD",
    "CHINA": "HKD",
    "UK": "GBP",
    "GLOBAL": "USD",  # Most global ETFs trade in USD
}


def get_currency_for_geography(geography: str) -> str:
    """
    Get the trading currency for a stock based on its geography.

    Args:
        geography: Stock geography code (EU, US, ASIA, UK, Greece, Europe, China)

    Returns:
        Currency code (EUR, USD, HKD, GBP)
    """
    geography_upper = (geography or "").upper()
    return GEOGRAPHY_CURRENCIES.get(geography_upper, "EUR")
