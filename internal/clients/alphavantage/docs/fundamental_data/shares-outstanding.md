# SHARES_OUTSTANDING

Shares outstanding data for a company.

## API Tier

**Free Tier Available**: Yes  
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns the number of shares outstanding for a specified company. Shares outstanding data is also available in the OVERVIEW endpoint, but this endpoint provides dedicated access to this metric.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `SHARES_OUTSTANDING` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "symbol": "IBM",
    "name": "International Business Machines Corporation",
    "sharesOutstanding": "900000000",
    "lastRefreshed": "2024-01-15",
    "currency": "USD"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | string | Stock symbol |
| `name` | string | Company name |
| `sharesOutstanding` | string | Number of shares outstanding |
| `lastRefreshed` | string | Last refresh date |
| `currency` | string | Currency code |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=SHARES_OUTSTANDING&symbol=IBM&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const symbol = 'IBM';
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=SHARES_OUTSTANDING&symbol=${symbol}&apikey=${apiKey}`;

fetch(url)
  .then(response => response.json())
  .then(data => {
    console.log(`Shares Outstanding: ${data.sharesOutstanding}`);
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
    'function': 'SHARES_OUTSTANDING',
    'symbol': 'IBM',
    'apikey': 'YOUR_API_KEY'
}

response = requests.get(url, params=params)
data = response.json()
print(f"Shares Outstanding: {data['sharesOutstanding']}")
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns current shares outstanding count
- Updated quarterly after earnings reports
- Also available in OVERVIEW endpoint
- Useful for calculating market capitalization (price × shares outstanding)
- Shares outstanding can change due to stock splits, buybacks, or new issuances
