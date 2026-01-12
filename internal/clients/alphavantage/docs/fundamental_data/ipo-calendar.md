# IPO_CALENDAR

Calendar of upcoming initial public offerings (IPOs).

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API provides the calendar of upcoming initial public offerings (IPOs) for the next 3 months. Returns data in CSV format for efficiency.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `IPO_CALENDAR` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### CSV Response Example

```csv
symbol,name,ipoDate,priceRangeLow,priceRangeHigh,currency,exchange
NEWCO,New Company Inc.,2024-02-15,18.00,20.00,USD,NASDAQ
STARTUP,Startup Corp.,2024-02-20,25.00,28.00,USD,NYSE
```

### CSV Fields

| Field | Description |
|-------|-------------|
| `symbol` | Expected stock symbol |
| `name` | Company name |
| `ipoDate` | Expected IPO date (YYYY-MM-DD) |
| `priceRangeLow` | Low end of expected price range |
| `priceRangeHigh` | High end of expected price range |
| `currency` | Currency code |
| `exchange` | Exchange where IPO will occur |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=IPO_CALENDAR&apikey=YOUR_API_KEY"
```

### Python (Parsing CSV)

```python
import requests
import csv
from io import StringIO

url = 'https://www.alphavantage.co/query'
params = {
    'function': 'IPO_CALENDAR',
    'apikey': 'YOUR_API_KEY'
}

response = requests.get(url, params=params)
csv_data = response.text

# Parse CSV
reader = csv.DictReader(StringIO(csv_data))
for row in reader:
    print(f"{row['symbol']} ({row['name']}): IPO on {row['ipoDate']} at ${row['priceRangeLow']}-${row['priceRangeHigh']}")
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns data in CSV format (not JSON)
- Shows IPOs for the next 3 months
- Includes expected price ranges when available
- Updated regularly as new IPOs are announced
- Useful for IPO tracking and investment research
