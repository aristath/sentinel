# TIME_SERIES_WEEKLY_ADJUSTED

Weekly adjusted time series data for equities.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns weekly time series data with adjustments for splits and dividend events. The adjusted close price accounts for corporate actions.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `TIME_SERIES_WEEKLY_ADJUSTED` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "Weekly Adjusted Prices (open, high, low, close) and Volumes",
        "2. Symbol": "IBM",
        "3. Last Refreshed": "2024-01-12",
        "4. Time Zone": "US/Eastern"
    },
    "Weekly Adjusted Time Series": {
        "2024-01-12": {
            "1. open": "185.0000",
            "2. high": "188.5000",
            "3. low": "183.5000",
            "4. close": "187.2000",
            "5. adjusted close": "187.2000",
            "6. volume": "12345678",
            "7. dividend amount": "0.0000"
        },
        "2024-01-05": {
            "1. open": "184.0000",
            "2. high": "186.0000",
            "3. low": "182.0000",
            "4. close": "185.0000",
            "5. adjusted close": "185.0000",
            "6. volume": "11234567",
            "7. dividend amount": "1.6500"
        }
    }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `Meta Data` | object | Metadata about the request |
| `Meta Data.1. Information` | string | Description of the data |
| `Meta Data.2. Symbol` | string | Stock symbol |
| `Meta Data.3. Last Refreshed` | string | Last refresh date |
| `Meta Data.4. Time Zone` | string | Time zone of the data |
| `Weekly Adjusted Time Series` | object | Weekly adjusted time series data keyed by date |
| `Weekly Adjusted Time Series.*.1. open` | string | Opening price (first trading day of week) |
| `Weekly Adjusted Time Series.*.2. high` | string | Highest price during the week |
| `Weekly Adjusted Time Series.*.3. low` | string | Lowest price during the week |
| `Weekly Adjusted Time Series.*.4. close` | string | Closing price (last trading day of week, unadjusted) |
| `Weekly Adjusted Time Series.*.5. adjusted close` | string | Adjusted closing price (accounts for splits and dividends) |
| `Weekly Adjusted Time Series.*.6. volume` | string | Total trading volume for the week |
| `Weekly Adjusted Time Series.*.7. dividend amount` | string | Dividend amount paid during the week |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=TIME_SERIES_WEEKLY_ADJUSTED&symbol=IBM&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const symbol = 'IBM';
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=TIME_SERIES_WEEKLY_ADJUSTED&symbol=${symbol}&apikey=${apiKey}`;

fetch(url)
  .then(response => response.json())
  .then(data => {
    console.log(data);
  })
  .catch(error => {
    console.error('Error:', error);
  });
```

### Python

```python
import requests

url = 'https://www.alphavantage.co/query'
params = {
    'function': 'TIME_SERIES_WEEKLY_ADJUSTED',
    'symbol': 'IBM',
    'apikey': 'YOUR_API_KEY'
}

response = requests.get(url, params=params)
data = response.json()
print(data)
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Weekly data is aggregated from daily adjusted data
- The date represents the end of the trading week (typically Friday)
- Adjusted close prices account for stock splits and dividends
- Use adjusted close for calculating long-term returns
- Dividend amounts are shown for the week in which the ex-dividend date falls
