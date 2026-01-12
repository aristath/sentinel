# MARKET_STATUS

Current market status of major trading venues worldwide.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API provides the current market status (open or closed) of major trading venues worldwide, including US, European, and Asian markets.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `MARKET_STATUS` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "markets": [
        {
            "market": "NYSE",
            "market_type": "Equity",
            "region": "United States",
            "primary_exchanges": "NYSE, NASDAQ",
            "local_open": "09:30",
            "local_close": "16:00",
            "current_status": "open",
            "notes": ""
        },
        {
            "market": "LSE",
            "market_type": "Equity",
            "region": "United Kingdom",
            "primary_exchanges": "LSE",
            "local_open": "08:00",
            "local_close": "16:30",
            "current_status": "closed",
            "notes": ""
        },
        {
            "market": "TSE",
            "market_type": "Equity",
            "region": "Japan",
            "primary_exchanges": "TSE",
            "local_open": "09:00",
            "local_close": "15:00",
            "current_status": "closed",
            "notes": ""
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=MARKET_STATUS&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=MARKET_STATUS&apikey=${apiKey}`;

fetch(url)
  .then(response => response.json())
  .then(data => {
    console.log(data.markets);
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
    'function': 'MARKET_STATUS',
    'apikey': 'YOUR_API_KEY'
}

response = requests.get(url, params=params)
data = response.json()
print(data['markets'])
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns status for major global markets
- Status values: `open`, `closed`
- Includes market hours in local time
- Updated in real-time
- Useful for determining if markets are currently trading
