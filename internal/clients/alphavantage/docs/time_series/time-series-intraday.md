# TIME_SERIES_INTRADAY

Intraday time series data for equities.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API provides intraday time series data for equities, including open, high, low, close prices, and volume. Data is updated in real-time during market hours.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `TIME_SERIES_INTRADAY` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min` |
| `adjusted` | boolean | No | Whether to return adjusted data. Default: `true` |
| `extended_hours` | boolean | No | Whether to include extended hours data. Default: `true` |
| `outputsize` | string | No | Determines the amount of data returned. Valid values: `compact` (default, latest 100 data points), `full` (full-length time series) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "Intraday (1min) open, high, low, close prices and volume",
        "2. Symbol": "IBM",
        "3. Last Refreshed": "2024-01-15 16:00:00",
        "4. Interval": "1min",
        "5. Output Size": "Compact",
        "6. Time Zone": "US/Eastern"
    },
    "Time Series (1min)": {
        "2024-01-15 16:00:00": {
            "1. open": "185.0000",
            "2. high": "185.1000",
            "3. low": "184.9000",
            "4. close": "185.0500",
            "5. volume": "12345"
        },
        "2024-01-15 15:59:00": {
            "1. open": "184.9500",
            "2. high": "185.0000",
            "3. low": "184.9000",
            "4. close": "185.0000",
            "5. volume": "11234"
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
| `Meta Data.3. Last Refreshed` | string | Last refresh timestamp |
| `Meta Data.4. Interval` | string | Data interval |
| `Meta Data.5. Output Size` | string | Output size setting |
| `Meta Data.6. Time Zone` | string | Time zone of the data |
| `Time Series (Xmin)` | object | Time series data keyed by timestamp |
| `Time Series.*.1. open` | string | Opening price |
| `Time Series.*.2. high` | string | Highest price |
| `Time Series.*.3. low` | string | Lowest price |
| `Time Series.*.4. close` | string | Closing price |
| `Time Series.*.5. volume` | string | Trading volume |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=IBM&interval=5min&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const symbol = 'IBM';
const interval = '5min';
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=${symbol}&interval=${interval}&apikey=${apiKey}`;

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
    'function': 'TIME_SERIES_INTRADAY',
    'symbol': 'IBM',
    'interval': '5min',
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

- Intraday data is only available during market hours
- The `1min` interval provides the most granular data but requires premium for real-time access
- Historical intraday data may be limited based on your subscription tier
- Use `outputsize=full` to get the complete historical intraday time series
