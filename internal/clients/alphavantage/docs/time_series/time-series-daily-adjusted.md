# TIME_SERIES_DAILY_ADJUSTED

Daily adjusted time series data for equities.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns daily time series data with adjustments for splits and dividend events. The adjusted close price accounts for corporate actions.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `TIME_SERIES_DAILY_ADJUSTED` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `outputsize` | string | No | Determines the amount of data returned. Valid values: `compact` (default, latest 100 data points), `full` (full-length time series) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "1. Information": "Daily Time Series with Splits and Dividend Events",
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
            "5. adjusted close": "186.2000",
            "6. volume": "3456789",
            "7. dividend amount": "0.0000",
            "8. split coefficient": "1.0"
        },
        "2024-01-14": {
            "1. open": "184.5000",
            "2. high": "185.5000",
            "3. low": "184.0000",
            "4. close": "185.0000",
            "5. adjusted close": "185.0000",
            "6. volume": "3214567",
            "7. dividend amount": "1.6500",
            "8. split coefficient": "1.0"
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
| `Time Series.*.4. close` | string | Closing price (unadjusted) |
| `Time Series.*.5. adjusted close` | string | Adjusted closing price (accounts for splits and dividends) |
| `Time Series.*.6. volume` | string | Trading volume |
| `Time Series.*.7. dividend amount` | string | Dividend amount paid on ex-dividend date |
| `Time Series.*.8. split coefficient` | string | Split coefficient (e.g., "2.0" for 2-for-1 split) |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol=IBM&outputsize=full&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const symbol = 'IBM';
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol=${symbol}&outputsize=full&apikey=${apiKey}`;

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
    'function': 'TIME_SERIES_DAILY_ADJUSTED',
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

- Adjusted close prices are useful for calculating returns over long periods
- The adjusted close accounts for stock splits and dividends
- Use `outputsize=full` to get the complete historical time series
- Dividend amounts are shown on ex-dividend dates
- Split coefficients show the ratio (e.g., "2.0" means 2-for-1 split)
