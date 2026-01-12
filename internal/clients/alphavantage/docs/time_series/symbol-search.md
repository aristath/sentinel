# SYMBOL_SEARCH

Search for stock symbols based on keywords.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns best-matching symbols and market information based on keywords. Useful for finding stock symbols when you know the company name.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `SYMBOL_SEARCH` |
| `keywords` | string | Yes | Text string to search for (e.g., `Microsoft`, `Apple`, `IBM`) |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "bestMatches": [
        {
            "1. symbol": "MSFT",
            "2. name": "Microsoft Corporation",
            "3. type": "Equity",
            "4. region": "United States",
            "5. marketOpen": "09:30",
            "6. marketClose": "16:00",
            "7. timezone": "UTC-05",
            "8. currency": "USD",
            "9. matchScore": "1.0000"
        },
        {
            "1. symbol": "MSFT.MX",
            "2. name": "Microsoft Corporation",
            "3. type": "Equity",
            "4. region": "Mexico",
            "5. marketOpen": "08:30",
            "6. marketClose": "15:00",
            "7. timezone": "UTC-06",
            "8. currency": "MXN",
            "9. matchScore": "0.8000"
        }
    ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `bestMatches` | array | Array of matching symbols |
| `bestMatches[].1. symbol` | string | Stock symbol |
| `bestMatches[].2. name` | string | Company name |
| `bestMatches[].3. type` | string | Security type (e.g., `Equity`, `ETF`) |
| `bestMatches[].4. region` | string | Region/Country |
| `bestMatches[].5. marketOpen` | string | Market open time |
| `bestMatches[].6. marketClose` | string | Market close time |
| `bestMatches[].7. timezone` | string | Timezone |
| `bestMatches[].8. currency` | string | Currency code |
| `bestMatches[].9. matchScore` | string | Match score (0-1, higher is better) |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords=Microsoft&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const keywords = 'Microsoft';
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords=${keywords}&apikey=${apiKey}`;

fetch(url)
  .then(response => response.json())
  .then(data => {
    console.log(data.bestMatches);
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
    'function': 'SYMBOL_SEARCH',
    'keywords': 'Microsoft',
    'apikey': 'YOUR_API_KEY'
}

response = requests.get(url, params=params)
data = response.json()
print(data['bestMatches'])
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns multiple matches sorted by relevance (matchScore)
- Can search by company name or symbol
- Returns symbols from multiple markets/regions
- Match score indicates relevance (1.0 = exact match)
- Useful for symbol lookup and validation
