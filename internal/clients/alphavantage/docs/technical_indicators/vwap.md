# VWAP (Volume Weighted Average Price)

Volume Weighted Average Price technical indicator.

## API Tier

**Free Tier Available**: Yes  
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the Volume Weighted Average Price (VWAP) values for a given equity. VWAP is the average price a security has traded at throughout the day, based on both volume and price.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `VWAP` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `interval` | string | Yes | Time interval between data points. Valid values: `1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly` |
| `time_period` | integer | Yes | Number of data points used to calculate each VWAP value (default: `10`) |
| `series_type` | string | Yes | Desired price type in the time series. Valid values: `close`, `open`, `high`, `low` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1: Symbol": "IBM",
        "2: Indicator": "Volume Weighted Average Price (VWAP)",
        "3: Last Refreshed": "2024-01-15 16:00:00",
        "4: Interval": "5min",
        "5: Time Period": 10,
        "6: Series Type": "close",
        "7: Time Zone": "US/Eastern"
    },
    "Technical Analysis: VWAP": {
        "2024-01-15 16:00:00": {
            "VWAP": "185.4567"
        },
        "2024-01-15 15:55:00": {
            "VWAP": "185.3456"
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
| `Technical Analysis: VWAP` | object | VWAP values keyed by date/timestamp |
| `Technical Analysis: VWAP.*.VWAP` | string | Volume Weighted Average Price value |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=VWAP&symbol=IBM&interval=5min&time_period=10&series_type=close&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const symbol = 'IBM';
const interval = '5min';
const timePeriod = 10;
const seriesType = 'close';
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=VWAP&symbol=${symbol}&interval=${interval}&time_period=${timePeriod}&series_type=${seriesType}&apikey=${apiKey}`;

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
    'function': 'VWAP',
    'symbol': 'IBM',
    'interval': '5min',
    'time_period': 10,
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

- VWAP gives more weight to prices with higher volume
- Commonly used for intraday trading
- Standard time period is 10 periods
- Use `series_type=close` for most standard VWAP calculations
- VWAP is often used as a benchmark for institutional trading
- Formula: VWAP = Σ(Price × Volume) / Σ(Volume)
