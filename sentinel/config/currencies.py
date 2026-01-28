"""
Currency Configuration - Single source of truth for supported currencies.

This consolidates currency definitions from currency.py and currency_exchange.py.
"""

# All currencies supported by the system
SUPPORTED_CURRENCIES = [
    'EUR',  # Base currency
    'USD',
    'GBP',
    'HKD',
    'CHF',
    'JPY',
    'CNY',
    'CAD',
    'AUD',
    'SGD',
    'NOK',
    'SEK',
    'DKK',
    'PLN',
    'CZK',
]

# Currencies for rate fetching (excluding EUR which is the base)
RATE_FETCH_CURRENCIES = [c for c in SUPPORTED_CURRENCIES if c != 'EUR']

# Direct currency pairs available on Tradernet for FX operations
# Format: (from_currency, to_currency) -> (symbol, action)
DIRECT_PAIRS = {
    # EUR <-> USD (ITS_MONEY market)
    ("EUR", "USD"): ("EURUSD_T0.ITS", "BUY"),
    ("USD", "EUR"): ("EURUSD_T0.ITS", "SELL"),

    # EUR <-> GBP (ITS_MONEY market)
    ("EUR", "GBP"): ("EURGBP_T0.ITS", "BUY"),
    ("GBP", "EUR"): ("EURGBP_T0.ITS", "SELL"),

    # GBP <-> USD (ITS_MONEY market)
    ("GBP", "USD"): ("GBPUSD_T0.ITS", "BUY"),
    ("USD", "GBP"): ("GBPUSD_T0.ITS", "SELL"),

    # HKD <-> EUR (MONEY market, EXANTE)
    ("EUR", "HKD"): ("HKD/EUR", "BUY"),
    ("HKD", "EUR"): ("HKD/EUR", "SELL"),

    # HKD <-> USD (MONEY market, EXANTE)
    ("USD", "HKD"): ("HKD/USD", "BUY"),
    ("HKD", "USD"): ("HKD/USD", "SELL"),
}

# Symbols for rate lookups (base_currency -> quote_currency)
RATE_SYMBOLS = {
    ("EUR", "USD"): "EURUSD_T0.ITS",
    ("EUR", "GBP"): "EURGBP_T0.ITS",
    ("GBP", "USD"): "GBPUSD_T0.ITS",
    ("HKD", "EUR"): "HKD/EUR",
    ("HKD", "USD"): "HKD/USD",
}

# Default exchange rates (fallbacks when API fails)
DEFAULT_RATES = {
    'EUR': 1.0,
    'USD': 0.85,
    'GBP': 1.15,
    'HKD': 0.11,
    'CHF': 1.08,
    'JPY': 0.0054,
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
