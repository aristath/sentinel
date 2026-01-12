# SMA (Simple Moving Average)

Simple Moving Average technical indicator.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Simple Moving Average (SMA) values for a given equity. SMA is calculated by taking the arithmetic mean of a given set of prices over a specified time period.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `SMA` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each SMA value (e.g., `60` for 60-period SMA) |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Simple Moving Average (SMA)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "daily",
        "5: Time Period": 60,
        "6: Series Type": "close",
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: SMA": {
        "2024-01-15": {
            "SMA": "185.2345"
        },
        "2024-01-14": {
            "SMA": "185.1234"
        }
    }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `Meta Data` | object | Metadata about the request |
| `Meta Data.1: Symbol` | string | Stock symbol |
| `Meta Data.2: Indicator` | string | Indicator name |
| `Meta Data.3: Last Refreshed` | string | Last refresh timestamp |
| `Meta Data.4: Interval` | string | Data interval |
| `Meta Data.5: Time Period` | string | Time period used for calculation |
| `Meta Data.6: Series Type` | string | Price type used |
| `Meta Data.7: Time Zone` | string | Time zone of the data |
| `Technical Analysis: SMA` | object | SMA values keyed by date/timestamp |
| `Technical Analysis: SMA.*.SMA` | string | Simple Moving Average value |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=SMA&symbol=IBM&interval=daily&time_period=60&series_type=close&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const symbol = 'IBM';
const interval = 'daily';
const timePeriod = 60;
const seriesType = 'close';
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=SMA&symbol=${symbol}&interval=${interval}&time_period=${timePeriod}&series_type=${seriesType}&apikey=${apiKey}`;

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
    'function': 'SMA',
    'symbol': 'IBM',
    'interval': 'daily',
    'time_period': 60,
    'series_type': 'close',
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

- SMA is one of the most commonly used technical indicators
- Common time periods: 20, 50, 100, 200 days
- Longer time periods provide smoother but slower-responding averages
- Use `series_type=close` for most standard SMA calculations
