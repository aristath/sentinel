# EARNINGS_ESTIMATES

Earnings estimates and analyst data for a company.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns annual and quarterly EPS and revenue estimates along with analyst data for a specified company.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `EARNINGS_ESTIMATES` |
| `symbol` | string | Yes | The stock ticker symbol (e.g., `IBM`, `MSFT`) |
| `apikey` | string | Yes | Your Alpha Vantage API key |

## Response Format

### JSON Response Example

```json
{
    "symbol": "IBM",
    "name": "International Business Machines Corporation",
    "annualEstimates": [
        {
            "fiscalDateEnding": "2024-12-31",
            "estimatedEPS": "7.50",
            "estimatedRevenue": "62000000000",
            "numberOfAnalysts": "25"
        },
        {
            "fiscalDateEnding": "2025-12-31",
            "estimatedEPS": "8.00",
            "estimatedRevenue": "64000000000",
            "numberOfAnalysts": "22"
        }
    ],
    "quarterlyEstimates": [
        {
            "fiscalDateEnding": "2024-03-31",
            "estimatedEPS": "1.80",
            "estimatedRevenue": "15000000000",
            "numberOfAnalysts": "28"
        },
        {
            "fiscalDateEnding": "2024-06-30",
            "estimatedEPS": "1.85",
            "estimatedRevenue": "15200000000",
            "numberOfAnalysts": "27"
        }
    ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | string | Stock symbol |
| `name` | string | Company name |
| `annualEstimates` | array | Annual earnings estimates |
| `annualEstimates[].fiscalDateEnding` | string | Fiscal year end date |
| `annualEstimates[].estimatedEPS` | string | Estimated earnings per share |
| `annualEstimates[].estimatedRevenue` | string | Estimated revenue |
| `annualEstimates[].numberOfAnalysts` | string | Number of analysts providing estimates |
| `quarterlyEstimates` | array | Quarterly earnings estimates |
| `quarterlyEstimates[].fiscalDateEnding` | string | Fiscal quarter end date |
| `quarterlyEstimates[].estimatedEPS` | string | Estimated earnings per share |
| `quarterlyEstimates[].estimatedRevenue` | string | Estimated revenue |
| `quarterlyEstimates[].numberOfAnalysts` | string | Number of analysts providing estimates |

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=EARNINGS_ESTIMATES&symbol=IBM&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Returns both annual and quarterly estimates
- Includes EPS and revenue estimates
- Shows number of analysts providing estimates
- Updated as analysts revise their estimates
- Useful for comparing estimates to actual results
