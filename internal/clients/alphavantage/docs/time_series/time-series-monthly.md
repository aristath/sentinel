# TIME_SERIES_MONTHLY

Monthly time series data for equities.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns monthly time series data for a specified stock symbol, including open, high, low, close prices, and volume aggregated by month.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `TIME_SERIES_MONTHLY` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "Monthly Prices (open, high, low, close) and Volumes",
        "2. Symbol": "IBM",
        "3. Last Refreshed": "2024-01-31",
        "4. Time Zone": "US/Eastern"
    },
    "Monthly Time Series": {
        "2024-01-31": {
            "1. open": "185.0000",
            "2. high": "192.5000",
            "3. low": "180.5000",
            "4. close": "190.2000",
            "5. volume": "45678901"
        },
        "2023-12-29": {
            "1. open": "180.0000",
            "2. high": "188.0000",
            "3. low": "175.0000",
            "4. close": "185.0000",
            "5. volume": "41234567"
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
| `Monthly Time Series` | object | Monthly time series data keyed by date (end of month) |
| `Monthly Time Series.*.1. open` | string | Opening price (first trading day of month) |
| `Monthly Time Series.*.2. high` | string | Highest price during the month |
| `Monthly Time Series.*.3. low` | string | Lowest price during the month |
| `Monthly Time Series.*.4. close` | string | Closing price (last trading day of month) |
| `Monthly Time Series.*.5. volume` | string | Total trading volume for the month |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY&symbol=IBM&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const symbol = 'IBM';
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY&symbol=${symbol}&apikey=${apiKey}`;

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
    'function': 'TIME_SERIES_MONTHLY',
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

- Monthly data is aggregated from daily data
- The date represents the last trading day of the month
- Open is the first trading day's open, close is the last trading day's close
- High and low represent the highest and lowest prices during the entire month
- Volume is the sum of all daily volumes for the month
- Useful for long-term trend analysis
