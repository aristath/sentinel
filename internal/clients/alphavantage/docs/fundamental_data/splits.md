# SPLITS

Historical stock split data for a company.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns historical stock split data for a specified company, including split ratios and execution dates.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `SPLITS` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "symbol": "AAPL",
    "name": "Apple Inc.",
    "splits": [
        {
            "exDate": "2020-08-31",
            "declaredDate": "2020-07-30",
            "ratio": "4.0",
            "toFactor": "4",
            "forFactor": "1"
        },
        {
            "exDate": "2014-06-09",
            "declaredDate": "2014-04-23",
            "ratio": "7.0",
            "toFactor": "7",
            "forFactor": "1"
        }
    ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | string | Stock symbol |
| `name` | string | Company name |
| `splits` | array | Array of stock split records |
| `splits[].exDate` | string | Ex-split date (YYYY-MM-DD) |
| `splits[].declaredDate` | string | Date split was declared (YYYY-MM-DD) |
| `splits[].ratio` | string | Split ratio (e.g., "4.0" for 4-for-1 split) |
| `splits[].toFactor` | string | Number of shares after split |
| `splits[].forFactor` | string | Number of shares before split |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=SPLITS&symbol=AAPL&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const symbol = 'AAPL';
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=SPLITS&symbol=${symbol}&apikey=${apiKey}`;

fetch(url)
  .then(response => response.json())
  .then(data => {
    console.log(data.splits);
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
    'function': 'SPLITS',
    'symbol': 'AAPL',
    'apikey': 'YOUR_API_KEY'
}

response = requests.get(url, params=params)
data = response.json()
print(data['splits'])
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns historical stock splits
- Split ratio indicates shares after split (e.g., 4.0 = 4-for-1 split)
- Includes ex-split date and declaration date
- Useful for adjusting historical price data
- Data typically goes back many years
