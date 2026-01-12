# SECTOR

Real-time and historical sector performance data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns real-time and historical sector performances calculated from S&P 500 incumbents. Shows which sectors are performing best and worst.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `SECTOR` |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "Meta Data": {
        "Information": "US Sector Performance (S&P 500 Incumbents)",
        "Last Refreshed": "2024-01-15 16:00:00"
    },
    "Rank A: Real-Time Performance": {
        "Information Technology": "2.50%",
        "Health Care": "1.80%",
        "Communication Services": "1.20%",
        "Consumer Discretionary": "0.90%",
        "Financials": "0.50%",
        "Industrials": "0.30%",
        "Consumer Staples": "-0.20%",
        "Energy": "-0.50%",
        "Utilities": "-0.80%",
        "Real Estate": "-1.20%",
        "Materials": "-1.50%"
    },
    "Rank B: 1 Day Performance": {
        "Information Technology": "3.20%",
        "Health Care": "2.10%",
        "Communication Services": "1.50%"
    },
    "Rank C: 5 Day Performance": {
        "Information Technology": "5.80%",
        "Health Care": "4.20%",
        "Communication Services": "3.10%"
    },
    "Rank D: 1 Month Performance": {
        "Information Technology": "12.50%",
        "Health Care": "8.90%",
        "Communication Services": "7.20%"
    },
    "Rank E: 3 Month Performance": {
        "Information Technology": "25.30%",
        "Health Care": "18.50%",
        "Communication Services": "15.20%"
    },
    "Rank F: Year-to-Date (YTD) Performance": {
        "Information Technology": "18.50%",
        "Health Care": "12.30%",
        "Communication Services": "10.80%"
    },
    "Rank G: 1 Year Performance": {
        "Information Technology": "35.20%",
        "Health Care": "22.10%",
        "Communication Services": "18.50%"
    },
    "Rank H: 3 Year Performance": {
        "Information Technology": "85.50%",
        "Health Care": "45.20%",
        "Communication Services": "38.90%"
    },
    "Rank I: 5 Year Performance": {
        "Information Technology": "150.30%",
        "Health Care": "78.50%",
        "Communication Services": "65.20%"
    },
    "Rank J: 10 Year Performance": {
        "Information Technology": "320.50%",
        "Health Care": "145.20%",
        "Communication Services": "128.50%"
    }
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=SECTOR&apikey=YOUR_API_KEY"
```

### JavaScript

```javascript
const apiKey = 'YOUR_API_KEY';

const url = `https://www.alphavantage.co/query?function=SECTOR&apikey=${apiKey}`;

fetch(url)
  .then(response => response.json())
  .then(data => {
    console.log('Real-Time Performance:', data['Rank A: Real-Time Performance']);
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
    'function': 'SECTOR',
    'apikey': 'YOUR_API_KEY'
}

response = requests.get(url, params=params)
data = response.json()
print('Real-Time Performance:', data['Rank A: Real-Time Performance'])
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Based on S&P 500 sector classifications
- Returns performance across multiple time periods
- Real-time performance updated during market hours
- Sectors are ranked by performance within each time period
- Useful for sector rotation strategies and market analysis
