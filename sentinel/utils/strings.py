"""String utilities."""


def parse_csv_field(value: str | None) -> list[str]:
    """Parse a comma-separated string into a list of stripped, non-empty values.

    Args:
        value: Comma-separated string, or None/empty

    Returns:
        List of stripped non-empty strings
    """
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
