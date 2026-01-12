# SUGAR

Sugar price data.

## API Tier

**Free Tier Available**: Yes
**Premium Required**: No (but premium offers higher rate limits)

## Description

This API returns time series data for sugar prices.

## Endpoint

```
https://www.alphavantage.co/query
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `function` | string | Yes | Must be `SUGAR` |
| `interval` | string | Yes | Time interval. Valid values: `daily`, `weekly`, `monthly` |
| `apikey` | string | Yes | Your Alpha Vantage API key |
| `datatype` | string | No | Output format. Valid values: `json` (default), `csv` |

## Response Format

### JSON Response Example

```json
{
    "name": "Sugar Prices",
    "interval": "daily",
    "unit": "USD per pound",
    "data": [
        {
            "date": "2024-01-15",
            "value": "0.25"
        },
        {
            "date": "2024-01-14",
            "value": "0.24"
        }
    ]
}
```

## Examples

### cURL

```bash
curl "https://www.alphavantage.co/query?function=SUGAR&interval=daily&apikey=YOUR_API_KEY"
```

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- Sugar prices in USD per pound
- Available intervals: daily, weekly, monthly
- Updated daily
