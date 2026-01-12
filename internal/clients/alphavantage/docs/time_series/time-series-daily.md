# TIME_SERIES_DAILY

Daily time series data for equities.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns daily time series data for a specified stock symbol, including open, high, low, close prices, and volume.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `TIME_SERIES_DAILY` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `outputsize` | string | No | Determines the amount of data returned. Valid values: `compact` (default, latest 100 data points), `full` (full-length time series) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "Daily Prices (open, high, low, close) and Volumes",
        "2. Symbol": "IBM",
        "3. Last Refreshed": "2024-01-15",
        "4. Output Size": "Compact",
        "5. Time Zone": "US/Eastern"
    },
    "Time Series (Daily)": {
        "2024-01-15": {
            "1. open": "185.0000",
            "2. high": "186.5000",
            "3. low": "184.5000",
            "4. close": "186.2000",
            "5. volume": "3456789"
        },
        "2024-01-14": {
            "1. open": "184.5000",
            "2. high": "185.5000",
            "3. low": "184.0000",
            "4. close": "185.0000",
            "5. volume": "3214567"
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
| `Meta Data.4. Output Size` | string | Output size setting |
| `Meta Data.5. Time Zone` | string | Time zone of the data |
| `Time Series (Daily)` | object | Daily time series data keyed by date |
| `Time Series.*.1. open` | string | Opening price |
| `Time Series.*.2. high` | string | Highest price |
| `Time Series.*.3. low` | string | Lowest price |
| `Time Series.*.4. close` | string | Closing price |
| `Time Series.*.5. volume` | string | Trading volume |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=IBM&outputsize=full&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const symbol = 'IBM';
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=${symbol}&outputsize=full&apikey=${apiKey}`;

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
    'function': 'TIME_SERIES_DAILY',
    'symbol': 'IBM',
    'outputsize': 'full',
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

- Daily data includes all trading days
- Use `outputsize=full` to get the complete historical time series (20+ years of data)
- Data is updated daily after market close
