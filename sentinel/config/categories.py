"""
Categories Configuration - Single source of truth for geography and industry defaults.

These defaults are combined with categories found in the database
to provide a complete list for the frontend.
"""

# Default geography options
DEFAULT_GEOGRAPHIES = [
    "US",
    "Europe",
    "Greece",
    "China",
    "Asia",
    "Global",
    "UK",
]

# Default industry options
DEFAULT_INDUSTRIES = [
    "Technology",
    "Semiconductors",
    "Aerospace",
    "Energy",
    "Finance",
    "Healthcare",
    "Consumer",
    "Industrial",
    "ETF",
    "Real Estate",
    "Materials",
    "Utilities",
    "Communications",
]

# Geography display labels (for frontend select options)
GEOGRAPHY_LABELS = {
    "US": "United States",
    "Europe": "Europe",
    "Greece": "Greece",
    "China": "China",
    "Asia": "Asia",
    "Global": "Global",
    "UK": "United Kingdom",
}

# Industry display labels (for frontend select options)
INDUSTRY_LABELS = {
    "Technology": "Technology",
    "Semiconductors": "Semiconductors",
    "Aerospace": "Aerospace & Defense",
    "Energy": "Energy",
    "Finance": "Finance",
    "Healthcare": "Healthcare",
    "Consumer": "Consumer",
    "Industrial": "Industrial",
    "ETF": "ETF",
    "Real Estate": "Real Estate",
    "Materials": "Materials",
    "Utilities": "Utilities",
    "Communications": "Communications",
}


def get_geography_options() -> list[dict]:
    """
    Get geography options formatted for frontend select components.

    Returns:
        List of dicts with 'value' and 'label' keys
    """
    return [{"value": geo, "label": GEOGRAPHY_LABELS.get(geo, geo)} for geo in DEFAULT_GEOGRAPHIES]


def get_industry_options() -> list[dict]:
    """
    Get industry options formatted for frontend select components.

    Returns:
        List of dicts with 'value' and 'label' keys
    """
    return [{"value": ind, "label": INDUSTRY_LABELS.get(ind, ind)} for ind in DEFAULT_INDUSTRIES]
