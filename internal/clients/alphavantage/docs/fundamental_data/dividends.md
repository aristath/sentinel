# DIVIDENDS

Historical dividend data for a company.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns historical dividend data for a specified company, including dividend amounts and ex-dividend dates.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `DIVIDENDS` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "symbol": "IBM",
    "name": "International Business Machines Corporation",
    "dividends": [
        {
            "exDate": "2024-02-08",
            "paymentDate": "2024-03-09",
            "amount": "1.65"
        },
        {
            "exDate": "2023-11-08",
            "paymentDate": "2023-12-09",
            "amount": "1.65"
        },
        {
            "exDate": "2023-08-08",
            "paymentDate": "2023-09-09",
            "amount": "1.65"
        },
        {
            "exDate": "2023-05-08",
            "paymentDate": "2023-06-09",
            "amount": "1.65"
        }
    ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | string | Stock symbol |
| `name` | string | Company name |
| `dividends` | array | Array of dividend records |
| `dividends[].exDate` | string | Ex-dividend date (YYYY-MM-DD) |
| `dividends[].paymentDate` | string | Payment date (YYYY-MM-DD) |
| `dividends[].amount` | string | Dividend amount per share |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=DIVIDENDS&symbol=IBM&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const symbol = 'IBM';
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=DIVIDENDS&symbol=${symbol}&apikey=${apiKey}`;

fetch(url)
  .then(response => response.json())
  .then(data => {
    console.log(data.dividends);
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
    'function': 'DIVIDENDS',
    'symbol': 'IBM',
    'apikey': 'YOUR_API_KEY'
}

response = requests.get(url, params=params)
data = response.json()
print(data['dividends'])
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns historical dividend payments
- Includes ex-dividend dates and payment dates
- Dividend amounts are per share
- Useful for dividend yield calculations and dividend history analysis
- Data typically goes back several years
