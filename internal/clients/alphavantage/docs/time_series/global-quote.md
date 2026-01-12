# GLOBAL_QUOTE

Latest price and volume information for a stock symbol.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API retrieves the latest price and volume information for a specific stock symbol in a compact format.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `GLOBAL_QUOTE` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Global Quote": {
        "01. symbol": "IBM",
        "02. open": "185.0000",
        "03. high": "186.5000",
        "04. low": "184.5000",
        "05. price": "186.2000",
        "06. volume": "3456789",
        "07. latest trading day": "2024-01-15",
        "08. previous close": "185.0000",
        "09. change": "1.2000",
        "10. change percent": "0.6486%"
    }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `Global Quote.01. symbol` | string | Stock symbol |
| `Global Quote.02. open` | string | Opening price |
| `Global Quote.03. high` | string | Highest price |
| `Global Quote.04. low` | string | Lowest price |
| `Global Quote.05. price` | string | Current/latest price |
| `Global Quote.06. volume` | string | Trading volume |
| `Global Quote.07. latest trading day` | string | Date of latest trading day |
| `Global Quote.08. previous close` | string | Previous closing price |
| `Global Quote.09. change` | string | Price change from previous close |
| `Global Quote.10. change percent` | string | Percentage change from previous close |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=IBM&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const symbol = 'IBM';
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=${symbol}&apikey=${apiKey}`;

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
    'function': 'GLOBAL_QUOTE',
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

- Returns the most recent trading day's data
- Compact format ideal for quick price lookups
- More efficient than fetching full time series for single price checks
- Price is the latest/closing price for the day
