# EARNINGS_CALENDAR

Upcoming earnings announcement dates.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API retrieves upcoming earnings announcement dates for publicly traded companies. Returns data in CSV format for efficiency.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `EARNINGS_CALENDAR` |
| `symbol` | string | No | Stock symbol to filter earnings for a specific company (e.g., `AAPL`) |
| `horizon` | string | No | Time horizon for earnings data. Valid values: `3month` (default), `6month`, `12month` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### CSV Response Example

```csv
symbol,name,reportDate,fiscalDateEnding,estimate,currency
AAPL,Apple Inc.,2024-01-25,2023-12-31,2.10,USD
MSFT,Microsoft Corporation,2024-01-23,2023-12-31,2.78,USD
IBM,International Business Machines Corporation,2024-01-24,2023-12-31,3.80,USD
```

### CSV Fields

| Field | Description |
|-------|-------------|
| `symbol` | Stock symbol |
| `name` | Company name |
| `reportDate` | Expected earnings report date (YYYY-MM-DD) |
| `fiscalDateEnding` | Fiscal period end date (YYYY-MM-DD) |
| `estimate` | Estimated EPS |
| `currency` | Currency code |

## Examples

### cURL

```bash
# Get earnings calendar for next 3 months
curl "https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&horizon=3month&apikey=YOUR_API_KEY"

# Get earnings calendar for specific company
curl "https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&symbol=AAPL&apikey=YOUR_API_KEY"
```

### Python (Parsing CSV)

```python
import requests
import csv
from io import StringIO

url = 'https://www.alphavantage.co/query'
params = {
    'function': 'EARNINGS_CALENDAR',
    'horizon': '3month',
    'apikey': 'YOUR_API_KEY'
}

response = requests.get(url, params=params)
csv_data = response.text

# Parse CSV
reader = csv.DictReader(StringIO(csv_data))
for row in reader:
    print(f"{row['symbol']}: {row['reportDate']} - Estimate: {row['estimate']}")
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns data in CSV format (not JSON)
- Can filter by specific symbol
- Time horizons: 3, 6, or 12 months
- Includes estimated EPS when available
- Updated regularly as companies announce earnings dates
- Useful for earnings trading strategies
